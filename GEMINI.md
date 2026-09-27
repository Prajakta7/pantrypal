# Project context for AI-assisted development

**PantryPal** is a kitchen assistant. Gemini uses function calling to manage a pantry and recipes in AlloyDB and to check pantry items against FDA food recalls that AlloyDB reads from BigQuery.

- `app/kitchen.py`: pure logic (freshness, expiry parsing, ingredient matching, recipe ranking, diet rules). Keep it free of I/O and tested.
- `app/text.py`: word normalization, including Hindi/Indian food names (`SYNONYMS`). Add new names there.
- `app/recalls.py`: openFDA record cleanup and pantry-to-recall matching. A recall only matches when it names the item as the product, not as an ingredient.
- `app/store.py`: all SQL, parameterized. `tests/fakes.py` mirrors its interface in memory; keep them in sync.
- `app/tools.py`: tool declarations and `ToolBox`. `test_every_declared_tool_has_a_handler` checks they match.
- `app/agent.py`: system prompt and the tool loop.
- `frontend/index.html`: single-file UI. "Used it" buttons call `/api/pantry/used` directly, without Gemini.

Rules: user text is always a bound SQL parameter; "today" comes from the browser's time zone; optional AI steps (embedding fallback, diet labels, Jev) run in savepoints and never fail a request; recall messages never say a food is safe; the saved diet applies to every suggestion and keyword rules override AI labels that contradict an ingredient; `make test` needs no cloud.
