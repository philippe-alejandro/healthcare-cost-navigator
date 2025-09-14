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
