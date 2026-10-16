.PHONY: help install dev test test-bench test-fast lint format clean check all

PKG := skills/disk-cleaner/diskcleaner

help:           ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install:        ## Install development dependencies
	pip install -e ".[dev]"

dev:            ## Install dev dependencies and pre-commit hooks
	pip install -e ".[dev]"
	pre-commit install

test:           ## Run tests with coverage (benchmarks: make test-bench)
	pytest tests/ -v --ignore=tests/benchmarks --cov=diskcleaner --cov-report=html --cov-report=term

test-bench:     ## Run performance benchmarks
	pytest tests/benchmarks/ -v

test-fast:      ## Run tests, skipping slow ones
	pytest tests/ -v -m "not slow"

lint:           ## Run the pre-commit hooks (black, isort, flake8), as CI does
	pre-commit run --all-files

format:         ## Format code with black and isort
	black $(PKG) tests/
	isort $(PKG) tests/

clean:          ## Remove build output and caches
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	find skills/ tests/ -type d -name __pycache__ -prune -exec rm -rf {} +

check: lint test ## Run lint and tests

all: format lint test ## Format, lint and test
