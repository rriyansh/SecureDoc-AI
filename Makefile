.PHONY: install lint test format up down build-index run-api run-cli run-eval clean

PYTHON ?= python3
PIP ?= pip3

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

lint:
	ruff check src api cli tests
	black --check src api cli tests

format:
	ruff check --fix src api cli tests
	black src api cli tests

test:
	pytest tests -v

up:
	docker-compose up -d

down:
	docker-compose down

build-index:
	$(PYTHON) -m src.ingest --build

run-api:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

run-cli:
	$(PYTHON) -m cli.main

run-eval:
	$(PYTHON) -m src.evaluate

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info
