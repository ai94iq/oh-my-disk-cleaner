.PHONY: help install dev test test-bench test-fast lint format clean build check all

PKG := skills/disk-cleaner/diskcleaner

help:           ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install:        ## Install development dependencies
	pip install -e ".[dev]"

dev:            ## Install dev dependencies and pre-commit hooks
	pip install -e ".[dev]"
	pre-commit install

test:           ## Run all tests with coverage
	pytest tests/ -v --cov=diskcleaner --cov-report=html --cov-report=term

test-bench:     ## Run performance benchmarks
	pytest tests/benchmarks/ -v

test-fast:      ## Run tests, skipping slow ones
	pytest tests/ -v -m "not slow"

lint:           ## Run black, isort, flake8 and mypy
	black --check $(PKG) tests/
	isort --check-only $(PKG) tests/
	flake8 $(PKG) tests/ --max-line-length=100
	mypy $(PKG) --config-file=mypy.ini

format:         ## Format code with black and isort
	black $(PKG) tests/
	isort $(PKG) tests/

clean:          ## Remove build output and caches
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	find skills/ tests/ -type d -name __pycache__ -prune -exec rm -rf {} +

build:          ## Build the distribution package
	python -m build

check: lint test ## Run lint and tests

all: format lint test ## Format, lint and test
