.PHONY: test test-unit test-coverage lint install-dev clean

# Install development dependencies
install-dev:
	poetry install

# Run all tests
test:
	poetry run pytest tests/ -v

# Run only unit tests (fast)
test-unit:
	poetry run pytest tests/ -v -m "not integration and not slow"

# Run tests with coverage
test-coverage:
	poetry run pytest tests/ --cov=deploy --cov-report=html --cov-report=term -m "not integration and not slow"
	@echo "Coverage report generated in htmlcov/index.html"

# Run linting
lint:
	poetry run flake8 . --max-line-length=100 --ignore=E501,W503 --exclude=.git,__pycache__,*.pyc,.pytest_cache,.venv,venv
	poetry run black --check .
	poetry run isort --check-only .

# Format code
format:
	poetry run black .
	poetry run isort .

# Clean generated files
clean:
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# Validate action.yml
validate:
	poetry run python -c "import yaml; yaml.safe_load(open('action.yml'))"
	@echo "✅ action.yml is valid YAML"
