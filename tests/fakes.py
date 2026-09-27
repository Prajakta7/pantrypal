"""In-memory store with the same interface as app.store.AlloyStore (for tests and previews)."""
import json
from pathlib import Path

from app.kitchen import DIETS
from app.text import words

FIX = Path(__file__).parent / "fixtures"


def starter_recipes() -> list[dict]:
    out = []
    for i, r in enumerate(json.loads((FIX / "recipes.json").read_text()), 1):
        out.append({"recipe_id": i, "title": r["title"], "cuisine": r["cuisine"], "minutes": r["minutes"],
                    "servings": r["servings"], "ingredients": r["ingredients"], "steps": r["steps"],
                    **r["labels"], "tagged_by": "starter", "source": "starter"})
    return out


class MemoryStore:
    # A few related words stand in for embeddings in recipe search
    RELATED = {"warm": {"soup", "curry", "risotto"}, "cozy": {"soup", "risotto"}, "quick": {"eggs", "salad"},
               "breakfast": {"oats", "pancakes", "eggs", "yogurt"}, "protein": {"chicken", "egg", "chickpea", "paneer", "dal", "moong", "tofu"},
               "comfort": {"khichdi", "dal", "soup"}, "spicy": {"masala", "curry"}}

    def __init__(self, recipes=True, recalls=None):
        self.items: list[dict] = []
        self.recipes = starter_recipes() if recipes else []
        self.recalls = recalls          # None = BigQuery not set up
        self.next_id = 1
        self.prefs = {"diets": [], "avoid": []}

    def add_raw(self, name, source="app", **kw):
        it = {"item_id": self.next_id, "name": name, "brand": kw.get("brand"), "category": kw.get("category", "Other"),
              "quantity": kw.get("quantity"), "unit": kw.get("unit"), "expires_on": kw.get("expires_on"),
              "added_on": kw.get("added_on"), "source": source, "used_on": None}
        self.items.append(it)
        self.next_id += 1
        return it

    def active_items(self):
        act = [dict(i) for i in self.items if i["used_on"] is None]
        return sorted(act, key=lambda i: (i["expires_on"] is None, i["expires_on"] or 0, i["name"]))

    def add_items(self, items):
        return [dict(self.add_raw(i["name"], **{k: v for k, v in i.items() if k != "name"})) for i in items]

    def use_item(self, item_id, used_all, remaining, today):
        it = next(i for i in self.items if i["item_id"] == item_id)
        if used_all:
            it["used_on"] = today
        else:
            it["quantity"] = remaining

    def all_recipes(self):
        return [dict(r) for r in sorted(self.recipes, key=lambda r: r["title"])]

    def search_recipes(self, query):
        q = words(query)
        for w in list(q):
            q |= self.RELATED.get(w, set())
        scored = []
        for r in self.recipes:
            text = words(r["title"] + " " + " ".join(r["ingredients"]) + " " + r["cuisine"])
            s = len(q & text)
            if s:
                scored.append((s, r["recipe_id"]))
        return [rid for s, rid in sorted(scored, key=lambda x: -x[0])]

    def add_recipe(self, r):
        rec = {"recipe_id": len(self.recipes) + 1, **r, **{d: None for d in DIETS}, "tagged_by": None,
               "source": "app"}
        self.recipes.append(rec)
        return dict(rec)

    def recent_recalls(self, since):
        if self.recalls is None:
            raise RuntimeError('relation "food_recalls" does not exist')
        rows = [r for r in self.recalls if (r.get("report_date") or "") >= since]
        return [r for r in rows if r.get("status") == "Ongoing"], len(rows)

    def get_prefs(self):
        return {k: list(v) for k, v in self.prefs.items()}

    def set_prefs(self, diets, avoid):
        self.prefs = {"diets": list(diets), "avoid": list(avoid)}
        return self.get_prefs()

    def status(self):
        act = [i for i in self.items if i["used_on"] is None]
        return {"items": len(act), "demo_items": sum(i["source"] == "demo" for i in act), "recipes": len(self.recipes)}

    def clear_demo(self):
        n = sum(i["source"] == "demo" for i in self.items)
        self.items = [i for i in self.items if i["source"] != "demo"]
        return n
