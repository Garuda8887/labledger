.PHONY: up down install-api install-web migrate seed-catalog seed-demo dev-api dev-web test test-e2e \
        eval generate-synth extract-one openapi backup

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
API_DIR := $(ROOT)api
WEB_DIR := $(ROOT)web
DATA_DIR ?= $(ROOT)data
export LABLEDGER_DATA_DIR := $(DATA_DIR)
export PYTHONPATH := $(API_DIR)

# Virtualenv layout differs on Windows (run make from Git Bash / MSYS2 there).
ifeq ($(OS),Windows_NT)
  PY_BOOT ?= python
  PY := .venv/Scripts/python
else
  PY_BOOT ?= python3
  PY := .venv/bin/python
endif
API := cd $(API_DIR) && $(PY)

# --- Docker ---
up:
	docker compose up --build -d

down:
	docker compose down

# --- API ---
install-api:
	cd $(API_DIR) && { test -d .venv || $(PY_BOOT) -m venv .venv; }
	$(API) -m pip install -q -r requirements.txt

migrate: install-api
	$(API) -m alembic upgrade head

seed-catalog: install-api
	$(API) scripts_seed_catalog.py

seed-demo: install-api seed-catalog
	$(API) -m app.synth seed-demo

dev-api: install-api
	$(API) -m uvicorn app.main:app --reload --host $${BIND_HOST:-127.0.0.1} --port 8000

openapi: install-api
	$(API) -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > $(ROOT)docs/openapi.json

backup: install-api
	$(API) -c "from app.services.backups import backup_database; print(backup_database())"

# --- Web ---
install-web:
	cd $(WEB_DIR) && npm ci

dev-web: install-web
	cd $(WEB_DIR) && npm run dev -- --host $${BIND_HOST:-127.0.0.1} --port 5173

# --- Tests ---
test: install-api install-web
	$(API) -m pytest -q
	cd $(WEB_DIR) && npm run build

# Playwright (demo mode; live API flow with LABLEDGER_E2E_LIVE=1)
test-e2e: install-web
	cd $(WEB_DIR) && npx playwright test

# --- Synthetic reports / accuracy harness ---
# DEGRADE_LIMIT = how many layouts get image degradations (memory-conscious)
DEGRADE_LIMIT ?= 4
generate-synth: install-api
	$(API) -m app.synth generate --degrade-limit $(DEGRADE_LIMIT)

eval: install-api
	$(API) -m app.synth generate --digital-only
	$(API) -m app.synth eval --max-degraded-layouts 3

# Usage: make extract-one FILE=api/tests/fixtures/synth/digital/amberpine_standard.pdf [PERSIST=1]
extract-one: install-api
	@test -n "$(FILE)" || { echo "Usage: make extract-one FILE=path/to/report.pdf"; exit 2; }
	$(API) -m app.extraction.cli "$(abspath $(FILE))" $(if $(PERSIST),--persist,) --json
