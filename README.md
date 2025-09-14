# Healthcare Cost Navigator

Minimal FastAPI service to search hospitals by MS-DRG, view costs and ratings, and ask natural-language questions.

## Quick start (Docker)

1. Copy env
```bash
cp .env.example .env || cp env.example .env
```
2. Start services
```bash
make up
```
3. Visit API docs: http://localhost:8000/docs

4. Run DB migrations
```bash
make migrate
```

5. Seed data (place CMS CSV at data/sample_prices_ny.csv first)
```bash
make etl
```

Note: The repo includes a small `data/zipcodes.csv` (NY sample) for ZIP centroids. For broader coverage, replace with a larger ZIP centroid file.

## Commands
```bash
make up        # start db+api
make logs      # tail logs
make down      # stop and remove
make migrate   # run migrations (once implemented)
make etl       # run ETL (once implemented)
```

## Tech
- Python 3.11, FastAPI, async SQLAlchemy, PostgreSQL, Alembic, OpenAI

## Roadmap
- [ ] DB schema + migrations
- [ ] ETL script for CMS CSV + mock ratings
- [ ] GET /providers (DRG, ZIP, radius)
- [ ] POST /ask (NL → structured intent → SQL)

## Usage examples (cURL)

- Providers (cheapest by average_covered_charges):
```bash
curl -s "http://localhost:8000/providers?drg=470&zip=10001&radius_km=40&limit=10&sort=cost" | jq .
```

- Providers (best ratings):
```bash
curl -s "http://localhost:8000/providers?drg=knee%20replacement&zip=10032&radius_km=40&limit=5&sort=rating" | jq .
```

- Ask: cheapest within 25 miles
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who is cheapest for DRG 470 within 25 miles of 10001?"}' | jq .
```

- Ask: best ratings near a ZIP
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who has the best ratings for heart surgery near 10032?"}' | jq .
```

- Ask: out-of-scope
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What\'s the weather today?"}' | jq .
```

## Example prompts for the AI assistant
- Find the cheapest hospital for DRG 470 within 30 miles of 10001.
- Which hospitals have the best ratings for knee replacement near 10032?
- Top 5 hospitals by lowest total payments for DRG 291 near 11201.
- Show providers offering heart bypass near 10016 within 20 miles.
- Compare ratings for DRG 460 around 10019.

## Architecture decisions & trade-offs
- Database normalized into `providers`, `drgs`, `prices`, `star_ratings`, `zip_codes`.
- Radius search via SQL Haversine using stored lat/lon from ZIP centroids for performance and simplicity.
- DRG search: numeric code match when provided; fallback to description ILIKE; can upgrade to `pg_trgm` similarity.
- ETL upserts `drgs` and `providers`, loads `prices`, updates provider lat/lon from `zip_codes`, and generates deterministic mock ratings.
- AI `/ask` uses OpenAI to parse NL to structured JSON; executes only parameterized SQL from a fixed template for safety. If no API key, falls back to regex parser.

## Data seeding
- Place the CMS sample at `data/sample_prices_ny.csv`.
- The ETL uses a minimal `data/zipcodes.csv` (NY ZIPs). For broader results, provide a larger centroid dataset (ZIP,city,state,latitude,longitude) and set `ZIP_CSV` env var or replace the file.

## Notes for the demo video
- Show `/providers` query in the browser and via cURL.
- Show `/ask` with both cost and rating intents.
- Mention improvements you would make with more time: better fuzzy search, full ZIP dataset, real Medicare ratings, caching, pagination, and tests.

## Dataset-specific examples (using MedicareData.csv)

- Cheapest DRG 470 near 10001 (40 km):
```bash
curl -s "http://localhost:8000/providers?drg=470&zip=10001&radius_km=40&limit=5&sort=cost" | jq .
```

- Top ratings for DRG 470 near 10032 (40 km):
```bash
curl -s "http://localhost:8000/providers?drg=470&zip=10032&radius_km=40&limit=5&sort=rating" | jq .
```

- NL query to /ask (cheapest DRG 470 within 25 miles of 10001):
```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who is cheapest for DRG 470 within 25 miles of 10001?"}' | jq .
```
