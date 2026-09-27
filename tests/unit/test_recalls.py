import json
from datetime import date
from pathlib import Path

from app import recalls as RC
from scripts_loader import windows

FIX = json.loads((Path(__file__).parents[1] / "fixtures" / "openfda_sample.json").read_text())["results"]
ROWS = RC.dedupe([RC.normalize(r) for r in FIX])


def test_normalize_and_dedupe():
    assert [r["recall_number"] for r in ROWS] == ["F-0001-2026", "F-0002-2026", "F-0003-2025"]
    first = ROWS[0]
    assert first["report_date"] == "2026-09-10" and first["classification"] == "Class I"
    assert RC.normalize({"recall_number": "X"}) is None


def test_name_match_without_brand_asks_to_check():
    m = RC.match_pantry([{"item_id": 1, "name": "Baby spinach"}], ROWS)
    assert len(m) == 1 and m[0]["level"] == "check_brand" and m[0]["recall_number"] == "F-0001-2026"


def test_brand_match_is_strong_and_other_brands_are_ignored():
    mine = RC.match_pantry([{"item_id": 1, "name": "Spinach", "brand": "Greenleaf Farms"}], ROWS)
    other = RC.match_pantry([{"item_id": 1, "name": "Spinach", "brand": "Valley Fresh"}], ROWS)
    assert mine[0]["level"] == "brand" and other == []


def test_unrelated_items_do_not_match():
    assert RC.match_pantry([{"item_id": 1, "name": "Bananas"}, {"item_id": 2, "name": "Milk"}], ROWS) == []


def test_serious_matches_first():
    m = RC.match_pantry([{"item_id": 1, "name": "Greek yogurt"}, {"item_id": 2, "name": "Spinach"}], ROWS)
    assert [x["classification"] for x in m] == ["Class I", "Class II"]


def test_loader_windows_cover_the_range_without_gaps():
    w = list(windows(1, date(2026, 9, 26)))
    assert w[0][1] == date(2026, 9, 26) and w[-1][0] == date(2025, 9, 26)
    assert all((a[0] - b[1]).days == 1 for a, b in zip(w, w[1:]))       # back-to-back windows


def test_main_word_must_be_the_product():
    yes = ["Whole milk, 1 gallon", "Spinach, cut leaf, 16 oz", "Greenleaf Baby Spinach 5 oz clamshell",
           "Kale and Spinach, 10 oz"]
    no = ["Whole Milk Greek Yogurt", "Milk Chocolate Bar", "Spinach and Artichoke Dip", "Cheddar cheese crackers"]
    assert all(RC.names_the_product("Milk" if "ilk" in d else "Spinach" if "pinach" in d else "Cheddar cheese", d) for d in yes)
    assert not any(RC.names_the_product("Milk" if "ilk" in d else "Spinach" if "pinach" in d else "Cheddar cheese", d) for d in no)
