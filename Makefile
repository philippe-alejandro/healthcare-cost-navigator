SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help up down logs dev ps migrate etl build

help:
	@echo "Available targets:"
	@echo "  up       - Build and start all services"
	@echo "  down     - Stop and remove services and volumes"
	@echo "  logs     - Tail logs for api and db"
	@echo "  dev      - Run services in the foreground"
	@echo "  ps       - Show service status"
	@echo "  migrate  - Run Alembic migrations (if configured)"
	@echo "  etl      - Run ETL script inside api container"
	@echo "  build    - Build the api image"

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api db

dev:
	docker compose up --build

ps:
	docker compose ps

build:
	docker compose build api

migrate:
	# Requires Alembic to be configured later
	docker compose exec -T api alembic upgrade head || true

etl:
	# Run ETL once implemented
	docker compose exec -T api python etl/etl.py || true

