.PHONY: setup run demo test test-cov lint typecheck dev-install clean

VENV := ./venv/bin
PYTHON := $(VENV)/python3
PIP := $(VENV)/pip

setup:
	$(PIP) install -r requirements.txt
	cd src/frontend-react && npm install

run:
	./palantir.sh

demo:
	./palantir.sh --demo

test:
	$(PYTHON) -m pytest src/python/tests/ -v --tb=short

test-cov:
	$(PYTHON) -m pytest src/python/tests/ --cov=src/python --cov-report=term-missing --cov-fail-under=80

lint:
	$(PYTHON) -m ruff check src/python/
	cd src/frontend-react && npx eslint src/

typecheck:
	$(PYTHON) -m mypy src/python/

dev-install:
	$(PIP) install -e ".[dev]"

build:
	cd src/frontend-react && npm run build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
