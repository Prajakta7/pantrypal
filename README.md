# 🥕 PantryPal

**A kitchen assistant built on AlloyDB AI, BigQuery and Gemini.** Tell it what you bought, in English or Hinglish, and it keeps track of your pantry and spice rack, suggests recipes that fit your diet and use up food before it expires, and checks your pantry against FDA food recalls.

## Features

- **Chat to update your pantry:** "I bought palak, 200 g paneer and a box of haldi" adds all three with estimated expiry dates
- **Indian food names:** haldi, jeera, dhania, hing, dahi, atta, ragi, jowar, lauki, tindora, makhana and more match their English names in recipes
- **Spice rack:** spices and masalas are tracked like everything else, so recipes show which ones you're missing
- **Your diet, saved:** vegetarian, eggetarian or non-veg (chicken & eggs), plus gluten-free, dairy-free, nut-free and ingredients you avoid. Every suggestion follows it, and each recipe shows the familiar 🟢 veg / 🟡 egg / 🔴 non-veg mark
- **Use it up:** recipe ideas ranked by what you already have and what expires soonest
- **Search recipes by meaning:** "something light for a rainy evening"
- **Recall check:** compares your pantry with a year of FDA food recalls, queried from BigQuery through AlloyDB
- **Shopping list:** copy the missing ingredients for any recipe

## How it works

```
You ──▶ FastAPI ──▶ Gemini (picks tools: pantry, recipes, recalls…)
                       │
                       ▼
                 AlloyDB for PostgreSQL
                 • pantry and recipes
                 • auto embeddings + keyword index, fused with RRF
                 • ai.if() labels diets on new recipes
                 • your saved diet filters every suggestion
                 • bigquery_fdw reads FDA recalls from BigQuery
                       │
                       ▼
          Gemini answers using only your real data
```

More detail in [docs/how-it-works.md](docs/how-it-works.md).

## Tech stack

**AI:** Gemini (function calling) · AlloyDB AI (auto embeddings, `ai.if`) · optional TypeSafe AI Jev  
**Data:** AlloyDB for PostgreSQL · pgvector · BigQuery · openFDA  
**Backend:** Python · FastAPI  
**Cloud:** Cloud Run · Secret Manager  
**Tests:** 63 unit tests with pytest

## Quick start

```bash
git clone https://github.com/Prajakta7/pantrypal.git && cd pantrypal
DB_PASSWORD='<password>' make alloydb     # AlloyDB free trial
make recalls                              # FDA recalls → BigQuery
DB_PASSWORD='<password>' make deploy
make open
```

A few SQL files run in AlloyDB Studio. Full instructions: [docs/setup.md](docs/setup.md).

## Data

- **Recipes:** 112 original starter recipes, 78 of them Indian: everyday dishes (dal tadka, poha, palak paneer, khichdi) plus the dishes from my 30-day healthy meal plan (CCFA tea, egg pesarattu, ragi moong dal idli, spinach besan chilla, jowar roti, gongura chicken pulao, black sesame laddoo…). Diet labels are hand-checked. Recipes you add get AI labels.
- **Recalls:** real FDA food enforcement reports from the [openFDA API](https://open.fda.gov/apis/food/enforcement/), loaded into your own BigQuery dataset. Run `make recalls` weekly to refresh.
- **Pantry:** starts empty. An optional **demo pantry** (an Indian kitchen: spice rack, millets, dry fruits and seeds) is available for trying it out; the app labels it clearly and removes it with one click.

Recall matches are based on product names and can be wrong. Always check the brand and lot codes on your package against the notice. Diet labels can be wrong too: most hing contains wheat flour, and some cheeses use animal rennet.

## Why I built it

I attended a hands-on AlloyDB AI workshop with Google Cloud and wanted to apply AI search, AI functions and AlloyDB–BigQuery interoperability to something I'd use every day.
