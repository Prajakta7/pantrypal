"""FDA food recalls: cleaning openFDA records and matching them to your pantry.

Data: openFDA food enforcement reports (https://open.fda.gov/apis/food/enforcement/),
updated weekly. scripts/load_recalls.py loads them into BigQuery; AlloyDB reads
that BigQuery table live through the bigquery_fdw extension.
"""
import re

from app.text import FORM, ordered_words, words

FIELDS = ["recall_number", "report_date", "recall_initiation_date", "status", "classification",
          "recalling_firm", "product_description", "reason_for_recall", "distribution_pattern",
          "code_info", "state"]
LIMITS = {"product_description": 2000, "reason_for_recall": 1000, "distribution_pattern": 500, "code_info": 1000}

CLASS_MEANING = {
    "Class I": "Most serious: the product could cause serious health problems or death.",
    "Class II": "The product could cause temporary or treatable health problems.",
    "Class III": "The product is unlikely to cause health problems but breaks FDA rules.",
}
CLASS_ORDER = {"Class I": 0, "Class II": 1, "Class III": 2}


def iso_date(value) -> str | None:
    """openFDA dates are YYYYMMDD strings → YYYY-MM-DD (sorts correctly as text)."""
    s = str(value or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def normalize(record: dict) -> dict | None:
    """One openFDA record → one row for BigQuery (None if unusable)."""
    if not record.get("recall_number") or not record.get("product_description"):
        return None
    row = {}
    for f in FIELDS:
        v = record.get(f)
        if f in ("report_date", "recall_initiation_date"):
            v = iso_date(v)
        elif v is not None:
            v = " ".join(str(v).split())[: LIMITS.get(f, 300)]
        row[f] = v or None
    return row


def dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r and r["recall_number"] not in seen:
            seen.add(r["recall_number"])
            out.append(r)
    return out


def names_the_product(item_name: str, description: str) -> bool:
    """Is the item's main word the product itself, not a description of something else?

    'Milk' is the product in 'Whole milk, 1 gallon' but only describes it in
    'Whole Milk Greek Yogurt' or 'Milk Chocolate Bar'. So the main (last) word of
    the pantry item must end a product name, or be followed only by form words
    ('Spinach, cut leaf').
    """
    item_words = ordered_words(item_name)
    if not item_words:
        return False
    head = item_words[-1]
    for segment in re.split(r"[,;:()\n]|\s-\s", description.lower()):
        toks = ordered_words(segment)
        for i, w in enumerate(toks):
            if w == head and all(t in FORM for t in toks[i + 1:]):
                return True
    return False


def match_level(item: dict, recall: dict) -> str | None:
    """'brand' if name and brand match, 'check_brand' if only the name matches, else None.

    Every significant word of the pantry item's name must appear in the recalled
    product's description ('Baby spinach' matches '... Spinach 10 oz bag').
    If you recorded a brand and it doesn't appear, it's someone else's product.
    """
    name = words(item.get("name", ""))
    if not name:
        return None
    description = recall.get("product_description", "") or ""
    if not name <= words(description) or not names_the_product(item.get("name", ""), description):
        return None
    brand = words(item.get("brand") or "", drop_generic=False)
    if brand:
        seller = words((recall.get("product_description") or "") + " " + (recall.get("recalling_firm") or ""),
                       drop_generic=False)
        return "brand" if brand <= seller else None
    return "check_brand"


def match_pantry(items: list[dict], recalls: list[dict], per_item: int = 3, limit: int = 12) -> list[dict]:
    """Possible recall matches for pantry items, most serious and most certain first."""
    out = []
    for item in items:
        found = []
        for r in recalls:
            level = match_level(item, r)
            if level:
                found.append({"item": item.get("name"), "item_id": item.get("item_id"), "level": level,
                              "meaning": CLASS_MEANING.get(r.get("classification"), ""), **{f: r.get(f) for f in FIELDS}})
        found.sort(key=lambda m: m.get("report_date") or "", reverse=True)          # newest first…
        found.sort(key=lambda m: (m["level"] != "brand", CLASS_ORDER.get(m.get("classification"), 3)))  # …within rank
        out.extend(found[:per_item])
    out.sort(key=lambda m: (m["level"] != "brand", CLASS_ORDER.get(m.get("classification"), 3)))
    return out[:limit]
