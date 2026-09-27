# How PantryPal works

## Data

| Where | Table | Holds |
|---|---|---|
| AlloyDB | `pantry_items` | What you have: quantity, category, optional brand, expiry date, and when you used it up |
| AlloyDB | `recipes` | Ingredients, steps, eight diet labels, an auto-updating keyword index (`tsvector`) and an embedding |
| AlloyDB | `preferences` | Your saved diet and the ingredients you avoid (one row) |
| BigQuery | `pantrypal.food_recalls` | FDA food recalls from the past year, loaded from openFDA by `make recalls` |
| AlloyDB | `food_recalls` (foreign table) | A live view of the BigQuery table through `bigquery_fdw`. It stores no data |

Demo items are marked `source = 'demo'`, so they can be removed in one step without touching your own items.

## A chat message

1. The browser sends the conversation and its **time zone**, so "expires tomorrow" means your tomorrow.
2. The system prompt includes today's date and how many items are in the pantry.
3. Gemini calls tools, up to 5 rounds. "I bought milk and eggs" becomes one `add_pantry_items` call with both items.
4. Each tool validates its input (known category, sensible quantity and date) and runs parameterized SQL.
5. Results go back to Gemini, which writes a short reply. The tools also produce the visual cards.

## The tools

| Tool | What it does |
|---|---|
| `list_pantry` | Items by category, with what expires soon first |
| `add_pantry_items` | Adds items; accepts dates like "5 days" or "2026-10-02" |
| `use_pantry_item` | Marks an item used, or lowers its quantity |
| `suggest_recipes` | Hybrid search plus ranking by what you have and what expires soon, filtered by your saved diet |
| `set_diet` | Saves your diet ("I'm vegetarian", "we eat eggs but no meat", "we eat chicken", "no mushrooms") |
| `get_recipe` | Full recipe, with each ingredient marked have, missing or expired |
| `check_recalls` | Compares your pantry with ongoing FDA recalls from BigQuery |
| `add_recipe` | Saves your own recipe; AlloyDB labels its diets with `ai.if()` |

## AlloyDB AI in this project

**Auto embeddings.** `ai.initialize_embeddings(..., incremental_refresh_mode => 'transactional')` keeps recipe embeddings up to date as rows change. If it isn't set up, the app calls `ai.embedding()` itself.

**Hybrid search.** Recipe search runs vector search (pgvector `<=>`) and keyword search (`tsvector`) and merges them with Reciprocal Rank Fusion, so both descriptions ("something warm with chickpeas") and exact words ("curry") find recipes.

**AI functions.** `ai.if()` answers yes/no questions in SQL. New recipes get diet labels this way, using Jev if it's registered or the default Gemini model otherwise. `sql/04_ai_tags.sql` and `sql/07_jev_setup.sql` compare AI labels with the hand-checked starter labels.

**BigQuery interoperability.** `bigquery_fdw` (Preview) lets AlloyDB query BigQuery with plain SQL. Filters, counts and `LIMIT` are pushed down, so BigQuery does the scanning and AlloyDB gets only the matching rows. `sql/05_bigquery_recalls.sql` includes a federated join between the pantry and recalls.

## Diets and Indian food names

| Diet | Means |
|---|---|
| 🟢 Vegetarian | No meat, fish or eggs |
| 🟡 Eggetarian | Vegetarian, eggs allowed |
| 🔴 Non-veg | Chicken and eggs allowed; no other meat or fish |
| Gluten-free, dairy-free, nut-free | Optional extras. Hing counts as gluten, because most hing is mixed with wheat flour |

You pick one main diet; if more than one is sent, the strictest is kept.

Your saved diet applies to every suggestion. You can ask for recipes outside it ("something with chicken for guests"), but ingredients you avoid are always left out.

Starter labels were checked by hand. New recipes are labeled with `ai.if()`, and then keyword rules act as a safety net: if a recipe lists chicken, eggs or atta, the matching labels are set to false whatever the model said.

Alternative names are mapped before matching, so "Haldi" in your pantry covers "turmeric" in a recipe, "Curd" covers "yogurt", "Jeera" covers "cumin seeds", "Masoor dal" covers "red lentils", "Lauki" covers "bottle gourd" and "Blueberries" covers "berries". Millet flours (ragi, jowar) count as gluten-free. Only salt, sugar, water and cooking oil are assumed; spices are tracked, so a recipe tells you when you're out of hing.

## Recall matching

Each recall is matched to a pantry item by name, on a copy of the product description:

- The item's main word must be **the product itself**, not an ingredient. "Milk" doesn't match "Whole Milk Greek Yogurt", but "Greek yogurt" does.
- If you recorded a brand, the brand must also match the recall. Otherwise the match is shown as **Check the brand**.
- Matches are sorted brand matches first, then by severity (Class I is the most serious).

Recall messages never say a food is safe. A name match is a prompt to check the package, not a verdict.

## Design choices

**Recipes rank by what you can actually make.** The score combines search relevance, the share of ingredients you have, and a bonus for using food that expires soon.

**"Used it" and the diet picker skip the AI.** They call `/api/pantry/used` and `/api/diet` directly, so they're instant and cost nothing.

**Optional AI steps never break a request.** Embedding fallback and diet labels run in database savepoints. If they fail, the recipe is still saved.

**Recalls live in your own BigQuery dataset.** Loading from openFDA into a dataset in the same region as AlloyDB keeps the data fresh on your schedule and avoids cross-region queries.
