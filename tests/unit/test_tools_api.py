from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import types

import app.main as main
from app import agent
from app.tools import DECLARATIONS, ToolBox
from tests.fakes import MemoryStore

TODAY = date(2026, 9, 26)
RECALLS = [{"recall_number": "F-1", "report_date": "2026-09-10", "status": "Ongoing", "classification": "Class I",
            "recalling_firm": "Greenleaf Farms", "product_description": "Greenleaf Baby Spinach 5 oz",
            "reason_for_recall": "Listeria", "distribution_pattern": "Nationwide", "code_info": "Lot 1"},
           {"recall_number": "F-2", "report_date": "2025-01-01", "status": "Ongoing", "classification": "Class I",
            "recalling_firm": "Old", "product_description": "Spinach", "reason_for_recall": "Old"}]


def stocked(**kw):
    s = MemoryStore(**kw)
    for name, days, cat in [("Eggs", 12, "Dairy & eggs"), ("Baby spinach", 2, "Produce"), ("Garlic", 40, "Produce"),
                            ("Heavy cream", -1, "Dairy & eggs"), ("Basmati rice", 300, "Grains & bread")]:
        s.add_raw(name, category=cat, expires_on=TODAY + timedelta(days=days), quantity=12 if name == "Eggs" else None)
    return s


def box(store=None):
    return ToolBox(store or stocked(), TODAY)


def test_every_declared_tool_has_a_handler():
    assert {d.name for d in DECLARATIONS} == set(box().handlers)


def test_list_pantry_and_expiring_filter():
    b = box()
    assert b.call("list_pantry", {})["result"]["count"] == 5
    soon = b.call("list_pantry", {"expiring_within_days": 3})["result"]
    assert {i["name"] for i in soon["items"]} == {"Baby spinach", "Heavy cream"}
    assert b.cards[0]["soon"] == 2


def test_add_items_with_expiry_words():
    b = box()
    out = b.call("add_pantry_items", {"items": [{"name": "milk", "expires": "5 days", "category": "Dairy & eggs"},
                                                {"name": "apples", "quantity": 6}]})["result"]
    assert out["added"][0] == {"name": "Milk", "expires_on": "2026-10-01"} and len(b.items()) == 7


def test_add_items_rejects_bad_input():
    b = box()
    assert "error" in b.call("add_pantry_items", {"items": []})
    assert "error" in b.call("add_pantry_items", {"items": [{"name": "milk", "expires": "someday"}]})


def test_use_part_then_all():
    b = box()
    assert b.call("use_pantry_item", {"name": "eggs", "quantity": 2})["result"]["remaining"] == 10
    assert b.call("use_pantry_item", {"name": "garlic"})["result"]["used_up"] is True
    assert all(i["name"] != "Garlic" for i in b.items())
    assert "error" in b.call("use_pantry_item", {"name": "salmon"})


def test_suggest_prefers_expiring_spinach():
    out = box().call("suggest_recipes", {"use_expiring": True})["result"]
    assert out["recipes"][0]["title"] == "Garlicky Spinach Scrambled Eggs"
    assert "baby spinach" in out["recipes"][0]["uses_expiring"]


def test_suggest_with_query_diet_and_time():
    out = box().call("suggest_recipes", {"query": "something warm", "diets": ["vegetarian"], "max_minutes": 35})["result"]
    titles = [r["title"] for r in out["recipes"]]
    assert titles and "Red Lentil Soup" in titles
    assert all("vegetarian" in r["diets"] and r["minutes"] <= 35 for r in out["recipes"])


def test_get_recipe_shows_missing_and_expired():
    out = box().call("get_recipe", {"title": "creamy tomato soup"})["result"]
    assert "heavy cream" in out["expired"] and "canned tomatoes" in out["missing"]


def test_recalls_match_and_skip_old():
    b = box(stocked(recalls=RECALLS))
    out = b.call("check_recalls", {})["result"]
    assert [m["item"] for m in out["possible_matches"]] == ["Baby spinach"]
    assert out["recalls_in_bigquery_last_year"] == 1


def test_recalls_not_set_up_gives_helpful_error():
    assert "isn't set up" in box().call("check_recalls", {})["error"]


def test_add_recipe_and_duplicate():
    b = box()
    ok = b.call("add_recipe", {"title": "Mom's Dal", "ingredients": ["Red lentils", "Onion"], "steps": "Cook.", "minutes": 30})
    assert ok["result"]["saved"] == "Mom's Dal"
    assert "already" in b.call("add_recipe", {"title": "mom's dal", "ingredients": ["x"], "steps": "y", "minutes": 5})["error"]


# ---------------------------------------------------------------- agent + API
def calls(*pairs):
    fcs = [types.FunctionCall(name=n, args=a) for n, a in pairs]
    return SimpleNamespace(function_calls=fcs, text=None, candidates=[SimpleNamespace(
        content=types.Content(role="model", parts=[types.Part(function_call=f) for f in fcs]))])


def say(t):
    return SimpleNamespace(function_calls=None, text=t, candidates=[])


class FakeGemini:
    def __init__(self, script):
        self.script, self.seen, self.models = list(script), [], self

    def generate_content(self, model, contents, config):
        self.seen.append(config)
        return self.script.pop(0)


def test_agent_runs_tools_and_prompt_mentions_expiring():
    b = box()
    g = FakeGemini([calls(("suggest_recipes", {"use_expiring": True})), say("Try the eggs!")])
    out = agent.run_chat(g, "m", [{"role": "user", "text": "what should I cook?"}], b)
    assert out["reply"] == "Try the eggs!" and out["cards"][0]["type"] == "recipes"
    assert "5 items; 2 expire" in g.seen[0].system_instruction


def api(monkeypatch, store, script=None):
    class Engine:
        @contextmanager
        def begin(self):
            yield None
        connect = begin
    monkeypatch.setattr(main, "get_engine", lambda: Engine())
    monkeypatch.setattr(main, "make_store", lambda conn: store)
    monkeypatch.setattr(main, "get_client", lambda: FakeGemini(script or [say("Hi!")]))
    return TestClient(main.app)


def test_pantry_used_and_clear_demo(monkeypatch):
    s = stocked()
    s.add_raw("Demo milk", source="demo", expires_on=TODAY)
    c = api(monkeypatch, s)
    body = c.get("/api/pantry", params={"tz": "America/Chicago"}).json()
    assert len(body["card"]["items"]) == 6 and body["status"]["demo_items"] == 1
    after = c.post("/api/pantry/used", json={"item_id": 1}).json()
    assert len(after["card"]["items"]) == 5
    assert c.post("/api/pantry/used", json={"item_id": 999}).status_code == 404
    cleared = c.post("/api/demo/clear").json()
    assert cleared["removed"] == 1 and cleared["status"]["demo_items"] == 0


def test_chat_endpoint(monkeypatch):
    script = [calls(("list_pantry", {})), say("Here's your pantry.")]
    body = api(monkeypatch, stocked(), script).post("/api/chat", json={"messages": [{"role": "user", "text": "pantry?"}]}).json()
    assert body["reply"] == "Here's your pantry." and body["cards"][0]["type"] == "pantry"


def test_saved_diet_applies_to_every_suggestion():
    b = box()
    b.call("set_diet", {"diets": ["eggetarian"], "avoid": ["Peanuts"]})
    assert b.store.get_prefs() == {"diets": ["eggetarian"], "avoid": ["peanuts"]}
    out = b.call("suggest_recipes", {"query": "rice"})["result"]
    assert out["diet_applied"] == ["Eggetarian"] and out["recipes"]
    assert all("eggetarian" in r["diets"] for r in out["recipes"])
    assert "Lemon Rice" not in [r["title"] for r in out["recipes"]]          # has peanuts
    guests = b.call("suggest_recipes", {"query": "chicken", "ignore_saved_diet": True})["result"]
    assert any("Chicken" in r["title"] for r in guests["recipes"])
    assert all(not r["fits_saved_diet"] for r in guests["recipes"] if "Chicken" in r["title"])


def test_get_recipe_warns_when_it_breaks_the_diet():
    b = box()
    b.call("set_diet", {"diets": ["vegetarian"]})
    out = b.call("get_recipe", {"title": "Masala Omelette"})["result"]
    assert out["does_not_fit_saved_diet"] == ["Vegetarian"]


def test_set_diet_rejects_unknown_diet():
    assert "Unknown diet" in box().call("set_diet", {"diets": ["paleo"]})["error"]


def test_diet_api_round_trip(monkeypatch):
    client = api(monkeypatch, stocked())
    r = client.post("/api/diet", json={"diets": ["eggetarian", "nut_free"], "avoid": ["mushroom"]})
    assert r.status_code == 200 and r.json()["names"] == ["Eggetarian", "Nut-free"]
    assert client.get("/api/diet").json()["avoid"] == ["mushroom"]
    assert client.post("/api/diet", json={"diets": ["keto"]}).status_code == 400


def test_prompt_includes_saved_diet():
    b = box()
    b.call("set_diet", {"diets": ["non_veg"], "avoid": ["mushroom"]})
    prompt = agent.system_prompt(b, False)
    assert "Saved diet: Non-veg (chicken & eggs). Ingredients they avoid: mushroom." in prompt
    assert "Saved diet: none saved" in agent.system_prompt(box(), False)


def test_only_one_main_diet_is_kept():
    b = box()
    out = b.call("set_diet", {"diets": ["non_veg", "vegetarian", "nut_free"]})["result"]
    assert out["saved_diets"] == ["Vegetarian", "Nut-free"]          # the strictest main diet wins
    chicken = b.call("suggest_recipes", {"query": "chicken"})["result"]["recipes"]
    assert not any("Chicken" in r["title"] for r in chicken)
    b.call("set_diet", {"diets": ["non_veg"]})
    chicken = b.call("suggest_recipes", {"query": "chicken"})["result"]["recipes"]
    assert any("Chicken" in r["title"] for r in chicken)
