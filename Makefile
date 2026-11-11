.DEFAULT_GOAL := help
PYTHON := python

.PHONY: help setup install ingest run cli eval test test-fast lint format clean docker docker-up docker-down rotate-keys health benchmark

help:
	@echo "make setup install ingest run cli eval test lint format clean docker docker-up docker-down rotate-keys health benchmark"

setup:       ; bash scripts/setup.sh
install:     ; $(PYTHON) -m pip install -r requirements-dev.txt
ingest:      ; $(PYTHON) -m src.ingest
run:         ; uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
cli:         ; $(PYTHON) -m cli.main
eval:        ; $(PYTHON) -m src.evaluate
test:        ; $(PYTHON) -m pytest
test-fast:   ; $(PYTHON) -m pytest --no-cov
lint:        ; ruff check src api cli tests && mypy src api cli --ignore-missing-imports && bandit -c pyproject.toml -r src api -q
format:      ; ruff format src api cli tests && ruff check --fix src api cli tests
rotate-keys: ; bash scripts/rotate_keys.sh
health:      ; bash scripts/healthcheck.sh
benchmark:   ; $(PYTHON) scripts/benchmark.py
docker:      ; docker build -t securedoc-ai:3.0.0 .
docker-up:   ; docker compose up --build -d
docker-down: ; docker compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	rm -rf vectorstore/* docstore/* logs/* audit/* evaluation_results.json benchmark_results.json
	touch vectorstore/.gitkeep docstore/.gitkeep logs/.gitkeep audit/.gitkeep
