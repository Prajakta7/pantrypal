"""Download recent FDA food recalls from openFDA into a newline-delimited JSON file.

    python3 scripts/load_recalls.py --years 2 --out recalls.ndjson

Runs in Cloud Shell (standard library only). scripts/02_load_recalls.sh calls
this, then loads the file into BigQuery with `bq load`.
openFDA allows about 1,000 requests a day without an API key; this uses a few dozen.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.recalls import dedupe, normalize  # noqa: E402

API = "https://api.fda.gov/food/enforcement.json"
PAGE = 1000          # openFDA maximum per request
MAX_SKIP = 25000     # openFDA maximum offset, so large ranges are split into windows


def windows(years: int, today: date, days: int = 91):
    """Date ranges of about 3 months, newest first, covering the last N years."""
    end = today
    start_limit = today - timedelta(days=365 * years)
    while end > start_limit:
        start = max(start_limit, end - timedelta(days=days))
        yield start, end
        end = start - timedelta(days=1)


def fetch_window(start: date, end: date) -> list[dict]:
    out, skip = [], 0
    while skip <= MAX_SKIP:
        url = (f"{API}?search=report_date:[{start:%Y%m%d}+TO+{end:%Y%m%d}]"
               f"&limit={PAGE}&skip={skip}")
        try:
            with urllib.request.urlopen(url, timeout=60) as res:
                data = json.load(res)
        except urllib.error.HTTPError as e:
            if e.code == 404:          # openFDA returns 404 when nothing matches
                return out
            raise
        results = data.get("results", [])
        out.extend(results)
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += PAGE
        if not results or skip >= total:
            return out
        time.sleep(0.3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--out", default="recalls.ndjson")
    args = ap.parse_args()

    raw = []
    for start, end in windows(args.years, date.today()):
        batch = fetch_window(start, end)
        print(f"  {start} → {end}: {len(batch)} recalls")
        raw.extend(batch)
        time.sleep(0.3)
    rows = dedupe([normalize(r) for r in raw])
    with open(args.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(rows)} recalls to {args.out}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
