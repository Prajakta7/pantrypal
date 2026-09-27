"""All SQL lives here; every user value is a bound parameter.

tests/fakes.py implements the same interface in memory for tests.
"""
from datetime import date

from sqlalchemy import text

from app import kitchen as K
from app.config import settings
from app.util import or_query, rrf_fuse

ITEM_COLS = "item_id, name, brand, category, quantity, unit, expires_on, added_on, source"
RECIPE_COLS = ("recipe_id, title, cuisine, minutes, servings, ingredients, steps, "
               + ", ".join(K.DIETS) + ", tagged_by, source")
RECALL_COLS = ("recall_number, report_date, status, classification, recalling_firm, product_description, "
               "reason_for_recall, distribution_pattern, code_info")
DIET_QUESTIONS = {
    "vegetarian": "Is this recipe vegetarian in the Indian sense (no meat, poultry, fish or eggs)?",
    "eggetarian": "Is this recipe free of meat, poultry and fish (eggs are allowed)?",
    "non_veg": "Is this recipe free of all meat and fish other than chicken (chicken and eggs are allowed)?",
    "gluten_free": ("Is this recipe gluten-free as written (no wheat, atta, maida, semolina, regular pasta, bread, "
                    "tortillas, regular soy sauce or hing, which is usually mixed with wheat flour)?"),
    "dairy_free": "Is this recipe dairy-free (no milk, butter, ghee, paneer, cheese, cream or yogurt)?",
    "nut_free": "Is this recipe free of peanuts and tree nuts (including pesto made with nuts)?",
}


def _item(r) -> dict:
    d = dict(r)
    d["quantity"] = float(d["quantity"]) if d["quantity"] is not None else None
    return d


class AlloyStore:
    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------ pantry
    def active_items(self) -> list[dict]:
        rows = self.conn.execute(text(f"""
            SELECT {ITEM_COLS} FROM pantry_items WHERE used_on IS NULL
            ORDER BY expires_on NULLS LAST, name
        """)).mappings().all()
        return [_item(r) for r in rows]

    def add_items(self, items: list[dict]) -> list[dict]:
        out = []
        for it in items:
            row = self.conn.execute(text(f"""
                INSERT INTO pantry_items (name, brand, category, quantity, unit, expires_on, added_on, source)
                VALUES (:name, :brand, :category, :quantity, :unit, :expires_on, :added_on, 'app')
                RETURNING {ITEM_COLS}
            """), it).mappings().one()
            out.append(_item(row))
        return out

    def use_item(self, item_id: int, used_all: bool, remaining: float | None, today: date) -> None:
        if used_all:
            self.conn.execute(text("UPDATE pantry_items SET used_on = :d WHERE item_id = :id"),
                              {"d": today, "id": item_id})
        else:
            self.conn.execute(text("UPDATE pantry_items SET quantity = :q WHERE item_id = :id"),
                              {"q": remaining, "id": item_id})

    # ------------------------------------------------------------ recipes
    def all_recipes(self) -> list[dict]:
        rows = self.conn.execute(text(f"SELECT {RECIPE_COLS} FROM recipes ORDER BY title")).mappings().all()
        return [dict(r) | {"ingredients": list(r["ingredients"])} for r in rows]

    def search_recipes(self, query: str) -> list[int]:
        """Recipe ids by relevance: meaning (embeddings) + keywords, fused with RRF."""
        by_meaning = self._try("""
            SELECT recipe_id FROM recipes WHERE embedding IS NOT NULL
            ORDER BY embedding <=> ai.embedding(:model, :q)::vector LIMIT 15
        """, {"model": settings.embedding_model, "q": query}, rows=True) or []
        by_keyword = []
        tsq = or_query(query)
        if tsq:
            by_keyword = self.conn.execute(text("""
                SELECT recipe_id FROM recipes WHERE search_tsv @@ websearch_to_tsquery('english', :q)
                ORDER BY ts_rank_cd(search_tsv, websearch_to_tsquery('english', :q)) DESC LIMIT 15
            """), {"q": tsq}).mappings().all()
        return rrf_fuse([[r["recipe_id"] for r in by_meaning], [r["recipe_id"] for r in by_keyword]])

    def add_recipe(self, r: dict) -> dict:
        search_text = (f"{r['title']}. {r.get('cuisine') or ''} dish, {r['minutes']} minutes. "
                       f"Ingredients: {', '.join(r['ingredients'])}. {r['steps']}")
        row = self.conn.execute(text(f"""
            INSERT INTO recipes (title, cuisine, minutes, servings, ingredients, steps, source, search_text)
            VALUES (:title, :cuisine, :minutes, :servings, :ingredients, :steps, 'app', :search_text)
            RETURNING recipe_id, (embedding IS NULL) AS needs_embedding
        """), {**r, "search_text": search_text}).mappings().one()
        rid = row["recipe_id"]
        if row["needs_embedding"]:     # auto embeddings not set up yet: compute it here
            self._try("UPDATE recipes SET embedding = ai.embedding(:m, search_text)::vector WHERE recipe_id = :id",
                      {"m": settings.embedding_model, "id": rid})
        self._label(rid)
        return next(x for x in self.all_recipes() if x["recipe_id"] == rid)

    def _label(self, recipe_id: int) -> None:
        """Diet labels with ai.if: Jev if registered, otherwise AlloyDB's default Gemini model."""
        model = ", model_id => 'jev-model'" if self.jev_available() else ""
        sets = ",\n".join(
            f"{col} = ai.if(prompt => 'Recipe: ' || title || '. Ingredients: ' || "
            f"array_to_string(ingredients, ', ') || '. {q.replace(chr(39), chr(39) * 2)}'{model})"
            for col, q in DIET_QUESTIONS.items())
        tagger = "jev" if model else "gemini"
        ok = self._try(f"UPDATE recipes SET {sets}, tagged_by = '{tagger}' WHERE recipe_id = :id", {"id": recipe_id},
                       setup="SET LOCAL google_ml_integration.enable_preview_ai_functions = 'on'")
        if ok:
            # Safety net: an ingredient like chicken or onion rules a diet out, whatever the model said
            ings = self.conn.execute(text("SELECT ingredients FROM recipes WHERE recipe_id = :id"),
                                     {"id": recipe_id}).scalar_one()
            out = sorted(K.ruled_out(list(ings)))
            if out:
                self.conn.execute(text(f"UPDATE recipes SET {', '.join(f'{d} = false' for d in out)} "
                                       "WHERE recipe_id = :id"), {"id": recipe_id})

    # ------------------------------------------------------------ recalls (BigQuery via bigquery_fdw)
    def recent_recalls(self, since: str) -> tuple[list[dict], int]:
        """Ongoing recalls reported since a date, read live from BigQuery.

        The WHERE filters are pushed down, so BigQuery only returns matching rows.
        """
        params = {"since": since}
        rows = self.conn.execute(text(f"""
            SELECT {RECALL_COLS} FROM food_recalls
            WHERE status = 'Ongoing' AND report_date >= :since
        """), params).mappings().all()
        total = self.conn.execute(text("SELECT count(*) FROM food_recalls WHERE report_date >= :since"),
                                  params).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ------------------------------------------------------------ saved diet
    def get_prefs(self) -> dict:
        row = self.conn.execute(text("SELECT diets, avoid FROM preferences WHERE id = 1")).mappings().first()
        return {"diets": list(row["diets"]), "avoid": list(row["avoid"])} if row else {"diets": [], "avoid": []}

    def set_prefs(self, diets: list[str], avoid: list[str]) -> dict:
        self.conn.execute(text("""
            INSERT INTO preferences (id, diets, avoid, updated_at) VALUES (1, :d, :a, now())
            ON CONFLICT (id) DO UPDATE SET diets = EXCLUDED.diets, avoid = EXCLUDED.avoid, updated_at = now()
        """), {"d": diets, "a": avoid})
        return {"diets": diets, "avoid": avoid}

    # ------------------------------------------------------------ status & demo
    def status(self) -> dict:
        row = self.conn.execute(text("""
            SELECT (SELECT count(*) FROM pantry_items WHERE used_on IS NULL) AS items,
                   (SELECT count(*) FROM pantry_items WHERE used_on IS NULL AND source = 'demo') AS demo_items,
                   (SELECT count(*) FROM recipes) AS recipes
        """)).mappings().one()
        return dict(row)

    def clear_demo(self) -> int:
        return self.conn.execute(text("DELETE FROM pantry_items WHERE source = 'demo'")).rowcount

    # ------------------------------------------------------------ helpers
    def jev_available(self) -> bool:
        return bool(self._try("SELECT count(*) FROM google_ml.model_info_view WHERE model_id = 'jev-model'",
                              {}, scalar=True))

    def _try(self, sql, params, rows=False, scalar=False, setup=None):
        """Run an optional AI step in a savepoint: failure returns None, never breaks the request."""
        try:
            with self.conn.begin_nested():
                if setup:
                    self.conn.execute(text(setup))
                result = self.conn.execute(text(sql), params)
                if rows:
                    return [dict(r) for r in result.mappings().all()]
                if scalar:
                    return result.scalar()
                return True
        except Exception:
            return None
