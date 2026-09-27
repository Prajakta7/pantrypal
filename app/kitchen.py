"""Pure kitchen logic: expiry, pantry ↔ recipe matching, ranking. Fully unit-tested."""
import re
from datetime import date, timedelta

from app.text import normalize, words

CATEGORIES = ["Produce", "Dairy & eggs", "Meat & fish", "Grains & bread", "Dals & lentils", "Spices & masalas",
              "Dry fruits & seeds", "Canned & jarred", "Frozen", "Snacks", "Condiments", "Other"]
# Main diets, from strictest: vegetarian ⊂ eggetarian ⊂ non-veg (chicken & eggs). Then allergy filters.
DIETS = ["vegetarian", "eggetarian", "non_veg", "gluten_free", "dairy_free", "nut_free"]
MAIN_DIETS = ["vegetarian", "eggetarian", "non_veg"]
DIET_NAMES = {"vegetarian": "Vegetarian", "eggetarian": "Eggetarian", "non_veg": "Non-veg (chicken & eggs)",
              "gluten_free": "Gluten-free", "dairy_free": "Dairy-free", "nut_free": "Nut-free"}
SOON_DAYS = 3

# Assumed to be in every kitchen, so never listed as missing. Spices are NOT assumed:
# they're tracked in the pantry like everything else.
STAPLES = {"salt", "water", "warm water", "hot water", "oil", "cooking oil", "vegetable oil", "olive oil", "sugar", "ice"}

# Words that describe a kind of the same food: pantry "Rice" covers "basmati rice",
# pantry "Jeera" covers "cumin seeds", but pantry "Milk" does NOT cover "coconut milk".
VARIETY = {"basmati", "jasmine", "arborio", "sona", "masoori", "brown", "white", "red", "yellow", "cherry", "roma",
           "grape", "greek", "whole", "wheat", "sharp", "mild", "unsalted", "salted", "sweet", "russet", "gold",
           "english", "extra", "virgin", "dark", "light", "black", "seed", "powder", "ground", "kashmiri", "split",
           "flour", "rolled", "steel", "baby", "button", "low", "fat", "leaf"}

# ---------------------------------------------------------------- diets
# Ingredient words that rule a diet out for certain. Used to label the starter recipes and as a
# safety net on AI labels: if a recipe lists chicken, no model can call it vegetarian.
# vegetarian = no meat, fish or eggs · eggetarian = vegetarian + eggs · non_veg = eggs and chicken, no other meat
_CHICKEN = {"chicken"}
# Meat and fish other than chicken: ruled out even for the non-veg (chicken & eggs) diet
_OTHER_MEAT = {"beef", "pork", "lamb", "mutton", "goat", "fish", "prawn", "shrimp", "bacon", "ham", "turkey",
               "sausage", "salami", "anchovy", "crab", "keema", "gelatin", "tuna", "salmon"}
_EGG = {"egg", "anda", "mayonnaise"}
_DAIRY = {"milk", "butter", "cheese", "cheddar", "parmesan", "mozzarella", "feta", "cream", "yogurt", "ghee",
          "paneer", "khoya", "malai", "buttermilk", "lassi"}
_NOT_DAIRY = {"coconut milk", "coconut cream", "cream of tartar", "almond milk", "oat milk", "soy milk", "peanut butter", "almond butter", "cocoa butter"}
_GLUTEN = {"pasta", "noodle", "tortilla", "bread", "wheat", "semolina", "flour", "soy sauce", "oat", "barley",
           "couscous", "cracker", "pita", "naan", "roti", "bun", "asafoetida", "seitan"}
_NOT_GLUTEN = {"rice flour", "corn flour", "besan", "jowar flour", "ragi flour", "bajra flour", "millet flour", "quinoa flour", "almond flour", "coconut flour", "tamari"}
_NUTS = {"peanut", "cashew", "almond", "walnut", "pistachio", "pecan", "hazelnut", "pesto", "pine nut", "brazil nut", "macadamia"}


def _has(ingredients: list[str], words_or_phrases: set[str], except_: set[str] = frozenset()) -> bool:
    for ing in ingredients:
        t = normalize(ing)
        for x in except_:
            t = t.replace(x, " ")
        ws = words(t, drop_generic=False)
        for w in words_or_phrases:
            if (" " in w and w in t) or w in ws:
                return True
    return False


def ruled_out(ingredients: list[str]) -> set[str]:
    """Diets that an ingredient list definitely breaks (by keyword)."""
    out = set()
    if _has(ingredients, _OTHER_MEAT):
        out |= {"vegetarian", "eggetarian", "non_veg"}
    if _has(ingredients, _CHICKEN):
        out |= {"vegetarian", "eggetarian"}
    if _has(ingredients, _EGG):
        out.add("vegetarian")
    if _has(ingredients, _DAIRY, _NOT_DAIRY):
        out.add("dairy_free")
    if _has(ingredients, _GLUTEN, _NOT_GLUTEN):
        out.add("gluten_free")
    if _has(ingredients, _NUTS):
        out.add("nut_free")
    return out


def rule_labels(ingredients: list[str]) -> dict:
    """All diet labels from keywords alone (starter recipes, reviewed by hand)."""
    out = ruled_out(ingredients)
    return {d: d not in out for d in DIETS}


# ---------------------------------------------------------------- expiry

def days_left(item: dict, today: date) -> int | None:
    exp = item.get("expires_on")
    return (exp - today).days if exp else None


def freshness(item: dict, today: date) -> str:
    d = days_left(item, today)
    if d is None:
        return "no_date"
    if d < 0:
        return "expired"
    return "soon" if d <= SOON_DAYS else "ok"


def resolve_expiry(value, today: date) -> date | None:
    """'2026-10-04', 'tomorrow', '5 days', '2 weeks', 3 → a date (None if empty)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        if not -30 <= n <= 3650:
            raise ValueError("That expiry is out of range.")
        return today + timedelta(days=n)
    s = str(value).strip().lower()
    if s in ("today",):
        return today
    if s in ("tomorrow",):
        return today + timedelta(days=1)
    m = re.fullmatch(r"(?:in\s+)?(\d{1,4})\s*(day|days|week|weeks|month|months)", s)
    if m:
        n = int(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2).rstrip("s")]
        return today + timedelta(days=n)
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        raise ValueError(f"Couldn't understand the expiry '{value}'. Use YYYY-MM-DD or e.g. '5 days'.")
    if abs((d - today).days) > 3650:
        raise ValueError("That expiry is out of range.")
    return d


# ---------------------------------------------------------------- matching

def is_staple(ingredient: str) -> bool:
    return " ".join((ingredient or "").lower().split()) in STAPLES


# A recipe asking for the general kind is satisfied by any specific one: "berries" ← "Blueberries"
KINDS = {"berry": {"blueberry", "strawberry", "raspberry", "blackberry", "mulberry"},
         "millet": {"ragi", "jowar", "bajra", "foxtail", "kodo"}}


def covers(item_name: str, ingredient: str) -> bool:
    """Does a pantry item satisfy a recipe ingredient?"""
    have, need = words(item_name), words(ingredient)
    have |= {kind for kind, kinds in KINDS.items() if have & kinds}
    if not have or not need:
        return False
    if need <= have:                    # pantry is as or more specific: "Cherry tomatoes" → "tomatoes"
        return True
    extra = need - have                 # pantry is more general: "Rice" → "basmati rice"
    return have <= need and extra <= VARIETY


def find_item(name: str, items: list[dict]) -> dict | None:
    """Best pantry item for what the user said ('2 eggs' → Eggs)."""
    q = " ".join((name or "").lower().split())
    for it in items:
        if it["name"].lower() == q:
            return it
    wanted = words(q)
    best = [it for it in items if wanted and (wanted <= words(it["name"]) or words(it["name"]) <= wanted)]
    if best:
        return sorted(best, key=lambda it: (it.get("expires_on") or date.max))[0]  # use the oldest first
    return None


def recipe_match(recipe: dict, items: list[dict], today: date) -> dict:
    have, missing, expired, use_soon = [], [], [], []
    for ing in recipe["ingredients"]:
        if is_staple(ing):
            continue
        matches = [it for it in items if covers(it["name"], ing)]
        fresh = [it for it in matches if freshness(it, today) != "expired"]
        if fresh:
            have.append(ing)
            for it in fresh:            # name YOUR item ("cherry tomatoes"), not the ingredient
                n = it["name"].lower()
                if freshness(it, today) == "soon" and n not in use_soon:
                    use_soon.append(n)
        elif matches:
            expired.append(ing)
        else:
            missing.append(ing)
    counted = len(have) + len(missing) + len(expired)
    return {"have": have, "missing": missing, "expired": expired, "uses_expiring": use_soon,
            "have_count": len(have), "total": counted,
            "ratio": round(len(have) / counted, 3) if counted else 1.0}


def diet_ok(recipe: dict, diets: list[str]) -> bool:
    return all(recipe.get(d) is True for d in diets)


def avoided(recipe: dict, avoid: list[str]) -> list[str]:
    """Ingredients in the recipe that the user avoids ('mushroom' matches 'button mushrooms')."""
    hits = []
    for a in avoid or []:
        want = words(a)
        if want and any(want <= words(ing, drop_generic=False) | words(ing) for ing in recipe["ingredients"]):
            hits.append(a)
    return hits


def diet_conflicts(recipe: dict, diets: list[str], avoid: list[str]) -> list[str]:
    """Human-readable reasons a recipe doesn't fit the user's saved diet ([] = fits)."""
    out = [DIET_NAMES[d] for d in diets if recipe.get(d) is not True]
    return out + [f"has {a}" for a in avoided(recipe, avoid)]


def rank(recipes: list[dict], matches: dict, use_expiring: bool = False) -> list[dict]:
    """Order recipes: search relevance first (position in `recipes`), then what you can make.

    Score = relevance (0..1 by position) + how much you already have
            + a bonus for using food that expires soon.
    """
    n = max(1, len(recipes))
    def score(i_r):
        i, r = i_r
        m = matches[r["recipe_id"]]
        rel = 1 - i / n
        return rel * 0.5 + m["ratio"] * 0.4 + (0.3 if use_expiring else 0.1) * min(1, len(m["uses_expiring"]))
    return [r for _, r in sorted(enumerate(recipes), key=score, reverse=True)]


def find_recipe(title: str, recipes: list[dict]) -> dict | None:
    q = (title or "").strip().lower()
    for r in recipes:
        if r["title"].lower() == q:
            return r
    want = words(q)
    scored = [(len(want & words(r["title"])), r) for r in recipes]
    scored = [(s, r) for s, r in scored if s]
    return max(scored, key=lambda x: x[0])[1] if scored else None
