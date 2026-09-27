from datetime import date, timedelta

import pytest

from app import kitchen as K
from app.text import singular, words
from tests.fakes import starter_recipes

TODAY = date(2026, 9, 26)


def item(name, days=None, **kw):
    return {"item_id": hash(name) % 1000, "name": name, "expires_on": TODAY + timedelta(days=days) if days is not None else None, **kw}


class TestWords:
    @pytest.mark.parametrize("w,s", [("tomatoes", "tomato"), ("berries", "berry"), ("eggs", "egg"),
                                     ("peaches", "peach"), ("hummus", "hummus"), ("glass", "glass")])
    def test_singular(self, w, s):
        assert singular(w) == s

    def test_words_drop_packaging(self):
        assert words("Organic Baby Spinach 5 oz bag") == {"spinach"}
        assert words("scallions") == {"green", "onion"}


class TestCovers:
    @pytest.mark.parametrize("pantry,ingredient,ok", [
        ("Rice", "basmati rice", True), ("Basmati rice", "rice", True), ("Cherry tomatoes", "tomatoes", True),
        ("Milk", "coconut milk", False), ("Onions", "green onion", False), ("Onions", "red onion", True),
        ("Chicken thighs", "chicken broth", False), ("Cheddar cheese", "parmesan", False),
        ("Canned chickpeas", "canned chickpeas", True)])
    def test_matching(self, pantry, ingredient, ok):
        assert K.covers(pantry, ingredient) is ok


class TestExpiry:
    def test_freshness(self):
        assert K.freshness(item("Milk", -1), TODAY) == "expired"
        assert K.freshness(item("Milk", 2), TODAY) == "soon"
        assert K.freshness(item("Milk", 9), TODAY) == "ok"
        assert K.freshness(item("Rice"), TODAY) == "no_date"

    @pytest.mark.parametrize("value,days", [("tomorrow", 1), ("5 days", 5), ("in 2 weeks", 14), (3, 3),
                                            ("2026-10-01", 5), ("", None), (None, None)])
    def test_resolve(self, value, days):
        d = K.resolve_expiry(value, TODAY)
        assert (d - TODAY).days == days if days is not None else d is None

    @pytest.mark.parametrize("bad", ["someday", "2099-01-01", 99999])
    def test_resolve_rejects(self, bad):
        with pytest.raises(ValueError):
            K.resolve_expiry(bad, TODAY)


def test_recipe_match_counts_have_missing_expired_and_staples():
    recipe = {"ingredients": ["eggs", "baby spinach", "garlic", "butter", "salt", "black pepper"]}
    items = [item("Eggs", 10), item("Baby spinach", 1), item("Butter", -2)]
    m = K.recipe_match(recipe, items, TODAY)
    # salt is a staple; spices like black pepper are tracked, so they can be missing
    assert m["have"] == ["eggs", "baby spinach"] and m["missing"] == ["garlic", "black pepper"]
    assert m["expired"] == ["butter"] and m["uses_expiring"] == ["baby spinach"] and m["total"] == 5


def test_find_item_prefers_exact_then_oldest():
    items = [item("Eggs", 10), item("Duck eggs", 3), item("Egg noodles", 100)]
    assert K.find_item("eggs", items)["name"] == "Eggs"
    assert K.find_item("egg", items)["name"] == "Duck eggs"
    assert K.find_item("salmon", items) is None


def test_rank_prefers_what_you_have_and_expiring_food():
    recipes = starter_recipes()
    items = [item("Eggs", 10), item("Baby spinach", 1), item("Garlic", 30), item("Butter", 20)]
    matches = {r["recipe_id"]: K.recipe_match(r, items, TODAY) for r in recipes}
    top = K.rank(recipes, matches, use_expiring=True)[0]
    assert top["title"] == "Garlicky Spinach Scrambled Eggs"


def test_diet_filter_and_find_recipe():
    recipes = starter_recipes()
    veg = [r["title"] for r in recipes if K.diet_ok(r, ["vegetarian"])]
    assert "Red Lentil Soup" in veg and "Shakshuka" not in veg
    assert K.find_recipe("lentil soup", recipes)["title"] == "Red Lentil Soup"
    assert K.find_recipe("xyz", recipes) is None


def test_indian_names_match_english_ingredients():
    assert K.covers("Haldi", "turmeric (haldi)") and K.covers("Jeera", "cumin seeds (jeera)")
    assert K.covers("Dhania powder", "coriander powder (dhania)") and K.covers("Hari mirch", "green chilies")
    assert K.covers("Curd", "yogurt (dahi)") and K.covers("Masoor dal", "red lentils")
    assert K.covers("Kadi patta", "curry leaves (kadi patta)") and K.covers("Red chilli powder", "red chili powder")
    assert K.covers("Besan", "besan (gram flour)") and not K.covers("Canned chickpeas", "besan (gram flour)")
    assert not K.covers("Dhania powder", "cilantro (hara dhania)")      # powder isn't fresh leaves
    assert not K.covers("Bell peppers", "black pepper")


def test_diet_rules_for_indian_diets():
    lab = K.rule_labels
    assert lab(["eggs", "onion"])["eggetarian"] and not lab(["eggs"])["vegetarian"]
    chicken = lab(["chicken thighs", "eggs"])
    assert chicken["non_veg"] and not chicken["eggetarian"] and not chicken["vegetarian"]
    assert not lab(["mutton"])["non_veg"] and not lab(["fish fillets"])["non_veg"]      # chicken only
    assert lab(["moong dal", "asafoetida (hing)"])["vegetarian"] and not lab(["asafoetida (hing)"])["gluten_free"]
    assert lab(["coconut milk", "peanut butter"])["dairy_free"] and not lab(["peanut butter"])["nut_free"]
    assert lab(["besan (gram flour)"])["gluten_free"] and not lab(["whole wheat flour (atta)"])["gluten_free"]
    assert not lab(["ghee"])["dairy_free"] and not lab(["paneer"])["dairy_free"]


def test_starter_labels_are_consistent():
    for r in starter_recipes():
        if r["vegetarian"]:
            assert r["eggetarian"], r["title"]
        if r["eggetarian"]:
            assert r["non_veg"], r["title"]
        for d in K.ruled_out(r["ingredients"]):
            assert r[d] is False, (r["title"], d)


def test_avoid_and_conflicts():
    r = {"ingredients": ["button mushrooms", "eggs"], "vegetarian": False, "eggetarian": True}
    assert K.avoided(r, ["mushroom", "coconut"]) == ["mushroom"]
    assert K.diet_conflicts(r, ["vegetarian"], ["mushroom"]) == ["Vegetarian", "has mushroom"]
    assert K.diet_conflicts(r, ["eggetarian"], []) == []


def test_meal_plan_names_and_kinds():
    assert K.covers("Blueberries", "berries") and not K.covers("Berries", "blueberries")
    assert K.covers("Jowar atta", "jowar flour") and K.covers("Nachni flour", "ragi flour")
    assert K.covers("Lauki", "bottle gourd (lauki)") and K.covers("Tindora", "ivy gourd (tindora)")
    assert K.covers("Meal maker", "soya chunks") and K.covers("Roasted channa", "roasted chana")
    assert not K.covers("Roasted chana", "chana dal") and K.covers("Pudina", "mint leaves (pudina)")
    assert K.covers("Flaxseeds", "flaxseed powder") and K.covers("Moringa", "drumsticks")
    lab = K.rule_labels
    assert lab(["jowar flour"])["gluten_free"] and lab(["ragi flour", "buttermilk"])["gluten_free"]
    assert not lab(["rolled oats"])["gluten_free"] and not lab(["brazil nuts"])["nut_free"]
    assert lab(["moong sprouts", "hummus"])["vegetarian"]
