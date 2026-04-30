# Single-source Docker workflow for the dev stack. Run `make help` for the
# full list. Works on macOS / Linux out of the box; on Windows install
# `make` via WSL or chocolatey.
#
# Convention: every target prints what it's doing, so a fresh contributor
# can `make up && make seed` and be reading the logs within 60 seconds.

COMPOSE := docker compose -f docker-compose.dev.yml
PROD_COMPOSE := docker compose

.PHONY: help up down reset restart rebuild build logs logs-backend logs-worker logs-frontend logs-db ps seed seed-landmarks seed-historical reembed migrate shell-backend shell-worker shell-db psql test clean prod-up prod-down

# --------------------------------------------------------------------------
# Help — `make` with no args lists every target.
# --------------------------------------------------------------------------

help:  ## Show this help
	@echo ""
	@echo "Legal Citation Graph — dev workflow"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

.DEFAULT_GOAL := help

# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------

up:  ## Bring the dev stack up in the background
	$(COMPOSE) up -d
	@echo ""
	@echo "  Frontend  http://localhost:3000"
	@echo "  API       http://localhost:8001"
	@echo "  API docs  http://localhost:8001/docs"
	@echo "  Postgres  localhost:5432  (citations / citations)"
	@echo ""
	@echo "  Tail all logs with: make logs"

down:  ## Stop the stack (db + uploaded PDFs preserved)
	$(COMPOSE) down

reset:  ## Stop the stack AND wipe everything (db, volumes, uploaded PDFs)
	@echo "  About to delete the dev DB and all anonymous volumes."
	@read -p "  Continue? [y/N] " ans && [ "$$ans" = "y" ] || (echo "  aborted" && exit 1)
	$(COMPOSE) down -v

restart:  ## Restart every service without rebuilding
	$(COMPOSE) restart

rebuild:  ## Rebuild backend + worker images, then bring stack up
	$(COMPOSE) build backend worker
	$(COMPOSE) up -d
	@echo "  Rebuilt + restarted. make logs to follow."

rebuild-frontend:  ## Rebuild frontend image AND wipe its anonymous node_modules volume (run after package.json changes)
	$(COMPOSE) rm -fsv frontend
	$(COMPOSE) up -d --build frontend
	@echo "  Frontend rebuilt with fresh node_modules. Refresh the browser."

rebuild-all:  ## Rebuild every image and wipe the frontend's anonymous volumes (preserves db + corpus)
	$(COMPOSE) rm -fsv frontend
	$(COMPOSE) build backend worker frontend
	$(COMPOSE) up -d
	@echo "  All images rebuilt. db + corpus preserved."

build:  ## Rebuild every image (backend, worker, frontend, seed)
	$(COMPOSE) build

# --------------------------------------------------------------------------
# Logs
# --------------------------------------------------------------------------

logs:  ## Tail logs from all services
	$(COMPOSE) logs -f

logs-backend:  ## Tail backend (API) logs
	$(COMPOSE) logs -f backend

logs-worker:  ## Tail ARQ worker logs (PDF / embed jobs)
	$(COMPOSE) logs -f worker

logs-frontend:  ## Tail Next.js dev server logs
	$(COMPOSE) logs -f frontend

logs-db:  ## Tail Postgres logs
	$(COMPOSE) logs -f db

ps:  ## Show running containers
	$(COMPOSE) ps

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

seed:  ## Seed the corpus with 200 SCOTUS opinions (uses CourtListener API key from .env)
	$(COMPOSE) --profile seed run --rm seed

seed-tech:  ## Seed 200 SCOTUS opinions filtered to technology / digital / surveillance topics
	$(COMPOSE) --profile seed run --rm seed \
		python scripts/seed.py --count 200 --court scotus \
		--topic "technology OR internet OR computer OR digital OR surveillance"

seed-landmarks:  ## Seed ~40 curated SCOTUS landmark cases (Marbury → Carpenter)
	$(COMPOSE) --profile seed run --rm seed \
		python scripts/seed.py --landmarks

seed-historical:  ## Seed SCOTUS opinions spread across decades (use --year-min/--year-max via SEED_ARGS)
	$(COMPOSE) --profile seed run --rm seed \
		python scripts/seed.py --spread --count 200 $(SEED_ARGS)

reseed:  ## Wipe corpus + re-seed with 200 SCOTUS (asks for y/N before wiping)
	@echo "  About to delete all corpus data and re-seed."
	@read -p "  Continue? [y/N] " ans && [ "$$ans" = "y" ] || (echo "  aborted" && exit 1)
	$(COMPOSE) down -v
	$(COMPOSE) up -d
	@echo "  Waiting 8s for backend to finish migrating…"
	@sleep 8
	$(COMPOSE) --profile seed run --rm seed

reembed:  ## Re-embed every document with the current embedding model
	$(COMPOSE) exec backend python scripts/reembed_corpus.py --all

migrate:  ## Run alembic upgrade head against the dev database
	$(COMPOSE) exec backend alembic upgrade head

# --------------------------------------------------------------------------
# Shells
# --------------------------------------------------------------------------

shell-backend:  ## Open a shell inside the backend container
	$(COMPOSE) exec backend bash

shell-worker:  ## Open a shell inside the worker container
	$(COMPOSE) exec worker bash

psql:  ## Open psql against the dev database
	$(COMPOSE) exec db psql -U citations -d citations

shell-db: psql

# --------------------------------------------------------------------------
# Testing
# --------------------------------------------------------------------------

test:  ## Run pytest inside the backend container
	$(COMPOSE) exec backend pytest -q

# --------------------------------------------------------------------------
# Production-like compose (with nginx)
# --------------------------------------------------------------------------

prod-up:  ## Bring up the production-ish stack (with nginx)
	$(PROD_COMPOSE) up -d --build

prod-down:  ## Stop the production-ish stack
	$(PROD_COMPOSE) down

clean: reset  ## Alias for reset
