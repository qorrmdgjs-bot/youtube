.PHONY: setup install test lint new run batch status cost clean

setup:
	bash scripts/setup_env.sh

install:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

new:
	python -m src.cli new $(ARGS)

run:
	python -m src.cli run $(ARGS)

batch:
	python -m src.cli batch $(ARGS)

status:
	python -m src.cli status $(ARGS)

cost:
	python scripts/cost_report.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
