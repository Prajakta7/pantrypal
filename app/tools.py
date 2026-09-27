"""The tools Gemini can call, plus the visual cards each one produces."""
import time
from datetime import timedelta

from google.genai import types

from app import kitchen as K
from app import recalls as RC

S, T = types.Schema, types.Type
ITEM = S(type=T.OBJECT, required=["name"], properties={
    "name": S(type=T.STRING, description="Food name as the user says it, e.g. 'Baby spinach', 'Haldi', 'Toor dal'"),
    "quantity": S(type=T.NUMBER, description="How many or how much"),
    "unit": S(type=T.STRING, description="e.g. bag, lb, carton; omit for countable items"),
    "category": S(type=T.STRING, enum=K.CATEGORIES,
                  description="Spices and masalas (haldi, jeera, garam masala) go in 'Spices & masalas'; dals in 'Dals & lentils'"),
    "expires": S(type=T.STRING, description="YYYY-MM-DD, or e.g. '5 days'. Estimate typical shelf life if not given "
                                            "(ground spices: about 6 months)"),
    "brand": S(type=T.STRING, description="Only if the user said it; improves recall checks"),
})
DECLARATIONS = [
    types.FunctionDeclaration(
        name="list_pantry",
        description="What's in the pantry, soonest-expiring first. Optionally only one category or items expiring soon.",
        parameters=S(type=T.OBJECT, properties={
            "category": S(type=T.STRING, enum=K.CATEGORIES),
            "expiring_within_days": S(type=T.INTEGER, description="Only items expiring within this many days"),
        }),
    ),
    types.FunctionDeclaration(
        name="add_pantry_items",
        description="Add groceries to the pantry. Add every item the user mentions in one call.",
        parameters=S(type=T.OBJECT, required=["items"], properties={"items": S(type=T.ARRAY, items=ITEM)}),
    ),
    types.FunctionDeclaration(
        name="use_pantry_item",
        description="Record that the user used or finished an item. Without quantity, the item is used up.",
        parameters=S(type=T.OBJECT, required=["name"], properties={
            "name": S(type=T.STRING, description="Item name"),
            "quantity": S(type=T.NUMBER, description="How much was used, in the item's unit"),
        }),
    ),
    types.FunctionDeclaration(
        name="suggest_recipes",
        description=("Suggest recipes from the collection, ranked by what the user asked for and what's in "
                     "their pantry. Shows which ingredients they have and which are missing."),
        parameters=S(type=T.OBJECT, properties={
            "query": S(type=T.STRING, description="What they feel like, e.g. 'something warm', 'quick pasta'"),
            "max_minutes": S(type=T.INTEGER),
            "diets": S(type=T.ARRAY, items=S(type=T.STRING, enum=K.DIETS),
                       description="Extra diet filters for this search. The saved diet always applies too"),
            "use_expiring": S(type=T.BOOLEAN, description="Prefer recipes that use food expiring soon"),
            "ignore_saved_diet": S(type=T.BOOLEAN, description=(
                "Only if the user explicitly asks for recipes outside their saved diet (e.g. for guests). "
                "Ingredients they avoid are still left out")),
        }),
    ),
    types.FunctionDeclaration(
        name="set_diet",
        description=("Save the user's diet so every recipe suggestion follows it. Pass the COMPLETE new lists "
                     "(they replace the old ones). Pick ONE main diet: vegetarian = no meat, fish or eggs; "
                     "eggetarian = vegetarian plus eggs; non_veg = eggs and chicken, but no other meat or fish. "
                     "Add gluten_free, dairy_free or nut_free if needed. Use empty lists to clear."),
        parameters=S(type=T.OBJECT, required=["diets"], properties={
            "diets": S(type=T.ARRAY, items=S(type=T.STRING, enum=K.DIETS)),
            "avoid": S(type=T.ARRAY, items=S(type=T.STRING),
                       description="Ingredients to leave out, e.g. 'mushroom', 'coconut', 'beef'"),
        }),
    ),
    types.FunctionDeclaration(
        name="get_recipe",
        description="Full recipe with steps, and which ingredients the user has or needs to buy.",
        parameters=S(type=T.OBJECT, required=["title"], properties={"title": S(type=T.STRING)}),
    ),
    types.FunctionDeclaration(
        name="check_recalls",
        description=("Check pantry items against ongoing FDA food recalls from the last year "
                     "(data in BigQuery, read live by AlloyDB)."),
    ),
    types.FunctionDeclaration(
        name="add_recipe",
        description="Save the user's own recipe to the collection. Diet labels are added by AI.",
        parameters=S(type=T.OBJECT, required=["title", "ingredients", "steps", "minutes"], properties={
            "title": S(type=T.STRING),
            "ingredients": S(type=T.ARRAY, items=S(type=T.STRING), description="Plain ingredient names"),
            "steps": S(type=T.STRING),
            "minutes": S(type=T.INTEGER),
            "cuisine": S(type=T.STRING),
            "servings": S(type=T.INTEGER),
        }),
    ),
]
TOOL = types.Tool(function_declarations=DECLARATIONS)


def item_json(it: dict, today) -> dict:
    exp = it.get("expires_on")
    return {"item_id": it["item_id"], "name": it["name"], "brand": it.get("brand"), "category": it["category"],
            "quantity": it.get("quantity"), "unit": it.get("unit"),
            "expires_on": exp.isoformat() if exp else None, "days_left": K.days_left(it, today),
            "freshness": K.freshness(it, today)}


class ToolBox:
    def __init__(self, store, today):
        self.store = store
        self.today = today
        self.calls: list[dict] = []
        self.cards: list[dict] = []
        self._items = None
        self._recipes = None
        self._prefs = None
        self.handlers = {d.name: getattr(self, d.name) for d in DECLARATIONS}

    def call(self, name: str, args: dict) -> dict:
        started = time.perf_counter()
        entry = {"name": name, "args": args, "ok": True}
        try:
            if name not in self.handlers:
                raise ValueError(f"Unknown tool {name}")
            return {"result": self.handlers[name](**args)}
        except TypeError:
            entry["ok"] = False
            return {"error": f"Invalid arguments for {name}"}
        except Exception as e:
            entry["ok"] = False
            return {"error": str(e)[:300]}
        finally:
            entry["ms"] = round((time.perf_counter() - started) * 1000)
            self.calls.append(entry)

    # ------------------------------------------------------------ data
    def items(self) -> list[dict]:
        if self._items is None:
            self._items = self.store.active_items()
        return self._items

    def recipes(self) -> list[dict]:
        if self._recipes is None:
            self._recipes = self.store.all_recipes()
        return self._recipes

    def prefs(self) -> dict:
        if self._prefs is None:
            self._prefs = self.store.get_prefs()
        return self._prefs

    def diet_card(self) -> dict:
        p = self.prefs()
        return {"type": "diet", "diets": p["diets"], "names": [K.DIET_NAMES[d] for d in p["diets"]],
                "avoid": p["avoid"]}

    def pantry_card(self, items=None, title="Your pantry") -> dict:
        items = self.items() if items is None else items
        js = [item_json(i, self.today) for i in items]
        return {"type": "pantry", "title": title, "items": js,
                "soon": sum(1 for i in js if i["freshness"] in ("soon", "expired"))}

    def recipe_json(self, r: dict) -> dict:
        m = K.recipe_match(r, self.items(), self.today)
        return {k: r[k] for k in ("recipe_id", "title", "cuisine", "minutes", "servings", "ingredients", "steps",
                                  "tagged_by", "source")} | {"diets": [d for d in K.DIETS if r.get(d) is True],
                                                             "labeled": r.get("tagged_by") is not None, "match": m,
                                                             "conflicts": K.diet_conflicts(r, self.prefs()["diets"],
                                                                                           self.prefs()["avoid"])}

    # ------------------------------------------------------------ tools
    def list_pantry(self, category: str | None = None, expiring_within_days: int | None = None) -> dict:
        items = self.items()
        title = "Your pantry"
        if category in K.CATEGORIES:
            items, title = [i for i in items if i["category"] == category], category
        if expiring_within_days is not None:
            n = max(0, min(60, int(expiring_within_days)))
            items = [i for i in items if (K.days_left(i, self.today) is not None and K.days_left(i, self.today) <= n)]
            title = "Use soon"
        card = self.pantry_card(items, title)
        self.cards.append(card)
        return {"count": len(card["items"]), "items": [
            {k: i[k] for k in ("name", "quantity", "unit", "days_left", "freshness")} for i in card["items"]]}

    def add_pantry_items(self, items: list) -> dict:
        if not items:
            raise ValueError("No items to add.")
        clean = []
        for raw in list(items)[:30]:
            raw = dict(raw)
            name = " ".join(str(raw.get("name") or "").split())[:60]
            if not name:
                continue
            q = raw.get("quantity")
            q = float(q) if q not in (None, "") else None
            if q is not None and not 0 <= q <= 10000:
                raise ValueError(f"The quantity for {name} looks wrong.")
            cat = raw.get("category") if raw.get("category") in K.CATEGORIES else "Other"
            clean.append({"name": name[:1].upper() + name[1:], "brand": (str(raw.get("brand") or "").strip()[:60] or None),
                          "category": cat, "quantity": q, "unit": (str(raw.get("unit") or "").strip()[:20] or None),
                          "expires_on": K.resolve_expiry(raw.get("expires"), self.today), "added_on": self.today})
        if not clean:
            raise ValueError("No items to add.")
        added = self.store.add_items(clean)
        self._items = None
        self.cards.append({"type": "added", "items": [item_json(i, self.today) for i in added]})
        return {"added": [{"name": i["name"], "expires_on": i["expires_on"].isoformat() if i["expires_on"] else None}
                          for i in added]}

    def use_pantry_item(self, name: str, quantity=None) -> dict:
        it = K.find_item(name, self.items())
        if it is None:
            raise ValueError(f"'{name}' isn't in the pantry.")
        used_all, remaining = True, None
        if quantity not in (None, "") and it.get("quantity") is not None:
            remaining = round(it["quantity"] - float(quantity), 2)
            used_all = remaining <= 0
        self.store.use_item(it["item_id"], used_all, remaining, self.today)
        self._items = None
        self.cards.append({"type": "used", "name": it["name"], "used_all": used_all, "remaining": remaining,
                           "unit": it.get("unit")})
        return {"item": it["name"], "used_up": used_all, "remaining": remaining}

    def set_diet(self, diets: list, avoid: list | None = None) -> dict:
        bad = [d for d in (diets or []) if d not in K.DIETS]
        if bad:
            raise ValueError(f"Unknown diet: {', '.join(bad)}")
        ds = [d for d in K.DIETS if d in (diets or [])]
        main = [d for d in ds if d in K.MAIN_DIETS]
        if len(main) > 1:                # keep the strictest main diet
            ds = [main[0]] + [d for d in ds if d not in K.MAIN_DIETS]
        av = []
        for a in avoid or []:
            a = " ".join(str(a).lower().split())[:40]
            if a and a not in av:
                av.append(a)
        self._prefs = self.store.set_prefs(ds, av[:20])
        self.cards.append(self.diet_card() | {"saved": True})
        return {"saved_diets": [K.DIET_NAMES[d] for d in ds], "avoid": av[:20]}

    def suggest_recipes(self, query: str | None = None, max_minutes: int | None = None, diets: list | None = None,
                        use_expiring: bool | None = False, ignore_saved_diet: bool | None = False) -> dict:
        recipes = self.recipes()
        q = str(query or "").strip()[:200]
        if q:
            order = self.store.search_recipes(q)
            by_id = {r["recipe_id"]: r for r in recipes}
            recipes = [by_id[i] for i in order if i in by_id] + [r for r in recipes if r["recipe_id"] not in order]
        saved = self.prefs()
        diets = [d for d in (diets or []) if d in K.DIETS]
        if not ignore_saved_diet:
            diets = [d for d in K.DIETS if d in diets or d in saved["diets"]]
        if saved["avoid"]:
            recipes = [r for r in recipes if not K.avoided(r, saved["avoid"])]
        unlabeled = sum(1 for r in recipes if r.get("tagged_by") is None) if diets else 0
        if diets:
            recipes = [r for r in recipes if K.diet_ok(r, diets)]
        if max_minutes:
            recipes = [r for r in recipes if r["minutes"] <= int(max_minutes)]
        matches = {r["recipe_id"]: K.recipe_match(r, self.items(), self.today) for r in recipes}
        top = K.rank(recipes, matches, bool(use_expiring))[:4]
        cards = [self.recipe_json(r) for r in top]
        self.cards.append({"type": "recipes", "query": q, "diets": diets, "diet_names": [K.DIET_NAMES[d] for d in diets],
                           "avoid": saved["avoid"], "max_minutes": max_minutes, "use_expiring": bool(use_expiring),
                           "ignored_saved_diet": bool(ignore_saved_diet and saved["diets"]), "recipes": cards})
        return {"recipes": [{"title": c["title"], "minutes": c["minutes"], "have": c["match"]["have"],
                             "missing": c["match"]["missing"], "uses_expiring": c["match"]["uses_expiring"],
                             "diets": c["diets"], "fits_saved_diet": not c["conflicts"]} for c in cards],
                "diet_applied": [K.DIET_NAMES[d] for d in diets], "avoiding": saved["avoid"],
                "note": f"{unlabeled} recipes have no diet labels yet" if unlabeled else None}

    def get_recipe(self, title: str) -> dict:
        r = K.find_recipe(title, self.recipes())
        if r is None:
            raise ValueError(f"No recipe called '{title}'.")
        card = self.recipe_json(r)
        self.cards.append({"type": "recipe", "recipe": card})
        return {k: card[k] for k in ("title", "minutes", "servings", "ingredients", "steps", "diets")} | {
            "missing": card["match"]["missing"], "expired": card["match"]["expired"],
            "does_not_fit_saved_diet": card["conflicts"] or None}

    def check_recalls(self) -> dict:
        since = (self.today - timedelta(days=365)).isoformat()
        try:
            recalls, total = self.store.recent_recalls(since)
        except Exception:
            raise ValueError("The recall check isn't set up yet (BigQuery table or bigquery_fdw missing). "
                             "See docs/setup.md, step 3.")
        items = self.items()
        found = RC.match_pantry(items, recalls)
        card = {"type": "recalls", "checked_items": len(items), "recalls_checked": total,
                "ongoing": len(recalls), "since": since, "matches": found}
        self.cards.append(card)
        return {"items_checked": len(items), "recalls_in_bigquery_last_year": total,
                "possible_matches": [{k: m[k] for k in ("item", "level", "classification", "product_description",
                                                         "reason_for_recall", "report_date")} for m in found],
                "note": "Name-only matches need the user to check the brand and lot codes on their package."}

    def add_recipe(self, title: str, ingredients: list, steps: str, minutes: int, cuisine: str | None = None,
                   servings: int | None = None) -> dict:
        t = " ".join(str(title or "").split())[:80]
        ings = [" ".join(str(i).split())[:60].lower() for i in (ingredients or []) if str(i).strip()][:30]
        if not t or not ings or not str(steps or "").strip():
            raise ValueError("A recipe needs a title, ingredients and steps.")
        if any(r["title"].lower() == t.lower() for r in self.recipes()):
            raise ValueError(f"'{t}' is already in the collection.")
        r = self.store.add_recipe({"title": t, "ingredients": ings, "steps": str(steps).strip()[:3000],
                                   "minutes": max(1, min(1440, int(minutes))), "cuisine": (cuisine or None),
                                   "servings": int(servings) if servings else 2})
        self._recipes = None
        card = self.recipe_json(r)
        self.cards.append({"type": "recipe", "recipe": card, "added": True})
        return {"saved": t, "diets": card["diets"], "labeled_by": r.get("tagged_by")}
