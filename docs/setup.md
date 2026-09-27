# Setup guide

Everything runs in **Google Cloud Shell**. Total time: about 1 to 1.5 hours, mostly waiting for resources.

## 1. Create the database

```bash
gcloud config set project YOUR_PROJECT_ID
git clone https://github.com/Prajakta7/pantrypal.git && cd pantrypal
DB_PASSWORD='<choose a password>' make alloydb        # AlloyDB 30-day free trial, ~15-20 min
```

In the console, open **AlloyDB → pantrypal-cluster → AlloyDB Studio** and sign in as `postgres`. Run `CREATE DATABASE pantrypal;`, reconnect to the `pantrypal` database, then run:

1. [`sql/01_schema.sql`](../sql/01_schema.sql): pantry and recipe tables
2. [`sql/02_recipes.sql`](../sql/02_recipes.sql): 112 starter recipes, 78 of them Indian
3. [`sql/03_auto_embeddings.sql`](../sql/03_auto_embeddings.sql): automatic recipe embeddings for search by meaning
4. *(optional)* [`sql/04_ai_tags.sql`](../sql/04_ai_tags.sql): see how `ai.if()` diet labels compare with the hand-checked ones

## 2. Load FDA recalls into BigQuery

```bash
make recalls        # ~2-5 min
```

This downloads the past year of FDA food recalls from openFDA, loads them into the BigQuery table `pantrypal.food_recalls`, and lets AlloyDB read BigQuery.

## 3. Connect AlloyDB to BigQuery

Replace `<YOUR_PROJECT_ID>` in [`sql/05_bigquery_recalls.sql`](../sql/05_bigquery_recalls.sql) and run it in AlloyDB Studio. The test queries at the end should return recall counts.

## 4. Deploy and open

```bash
DB_PASSWORD='<password>' make deploy
make open        # then Web Preview → Preview on port 8080
```

The app is private: only people signed in to your Google Cloud project can open it.

## Try it with demo data

Run [`sql/06_demo_pantry.sql`](../sql/06_demo_pantry.sql) for a demo Indian kitchen (68 items, including a spice rack, millets, dry fruits and seeds) with expiry dates relative to today. To remove them, click **Clear** next to "Demo pantry" in the header, or run [`sql/06b_clear_demo.sql`](../sql/06b_clear_demo.sql). Items you add yourself are kept.

## Set your diet

Tap the diet button at the top, or just tell PantryPal ("I'm vegetarian", "we're eggetarian, no mushrooms", "we eat chicken"). Every recipe suggestion follows it.

## Options

**Keep recalls fresh.** openFDA updates weekly. Run `make recalls` again; it replaces the BigQuery table and the app sees the new data right away.

**Label diets with Jev.** Get a key at [typesafe.ai](https://typesafe.ai), run `TYPESAFE_API_KEY='<key>' make jev-secret`, replace `<YOUR_PROJECT_ID>` in [`sql/07_jev_setup.sql`](../sql/07_jev_setup.sql), and run it in AlloyDB Studio. New recipes are then labeled with Jev instead of the default Gemini model.

**Gemini model.** If the default isn't available, redeploy with `GEMINI_MODEL='<current Gemini Flash model>'`.

## Commands

| Command | What it does |
|---|---|
| `make test` | Run unit tests (no cloud needed) |
| `make alloydb` | Create the AlloyDB free trial cluster |
| `make recalls` | Load or refresh FDA recalls in BigQuery |
| `make deploy` | Deploy the app to Cloud Run |
| `make open` | Open your private app on `localhost:8080` |
| `make cleanup` | Delete all cloud resources (erases your data) |

## Troubleshooting

| Problem | Fix |
|---|---|
| "Permission denied" or "API not enabled" | Wait 1–2 minutes and try again. |
| "No rule to make target" | Run `cd ~/pantrypal` first. |
| `CREATE EXTENSION bigquery_fdw` fails | The extension is in Preview. Check that the instance has the `alloydb.iam_authentication` flag on (set by `make alloydb`). |
| Recall check says "isn't set up yet" | Run step 2 and step 3. |
| Recall queries return permission errors | `make recalls` grants BigQuery roles to the AlloyDB service agent; wait a few minutes after it runs. |
| "PantryPal hit an error" in chat | Check the Gemini model name (see Options). |

The AlloyDB free trial lasts 30 days. Before it ends, run `make cleanup` or upgrade the cluster to keep your data.
