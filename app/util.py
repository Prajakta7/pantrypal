"""Small shared helpers: time zones, search queries, rank fusion, chat history."""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STOPWORDS = {"a", "an", "and", "are", "can", "could", "for", "i", "in", "is", "me", "my", "of", "on",
             "or", "recipe", "recipes", "something", "some", "the", "to", "what", "with", "make", "cook",
             "want", "have", "tonight", "dinner", "lunch", "any", "that", "use"}


def today_in(tz_name: str | None, fallback: str = "UTC", now: datetime | None = None) -> tuple[date, str]:
    for name in (tz_name, fallback, "UTC"):
        if not name:
            continue
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            continue
        return (now or datetime.now(zone)).astimezone(zone).date(), name
    return date.today(), "UTC"


def or_query(text: str) -> str:
    kept = []
    for w in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(w) > 2 and w not in STOPWORDS and w not in kept:
            kept.append(w)
    return " or ".join(f'"{w}"' for w in kept[:12])


def rrf_fuse(ranked_lists: list[list], k: int = 60) -> list:
    scores: dict = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return [i for i, _ in sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))]


def clean_history(messages: list[dict], max_messages: int = 20, max_chars: int = 4000) -> list[dict]:
    out = [{"role": m["role"], "text": str(m.get("text", ""))[:max_chars].strip()}
           for m in messages
           if m.get("role") in ("user", "assistant") and str(m.get("text", "")).strip()][-max_messages:]
    while out and out[0]["role"] != "user":
        out.pop(0)
    if not out or out[-1]["role"] != "user":
        raise ValueError("The last message must be from the user.")
    return out
