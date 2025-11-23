# Testing Guide

This directory contains tests for the MetalDeploy Action.

## Running Tests

### Quick Start (Using Make)

```bash
# Install test dependencies
make install-dev

# Run all tests
make test

# Run only fast unit tests
make test-unit

# Run with coverage report
make test-coverage
```

### Manual Setup

#### Install Test Dependencies

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

#### Run All Tests

```bash
poetry run pytest
```

### Run Only Unit Tests (Fast)

```bash
poetry run pytest -m "not integration and not slow"
```

### Run with Coverage

```bash
poetry run pytest --cov=deploy --cov-report=html
```

Then open `htmlcov/index.html` in your browser to see coverage report.

### Run Specific Test File

```bash
poetry run pytest tests/test_deploy.py
```

### Run Specific Test

```bash
poetry run pytest tests/test_deploy.py::TestRunCommand::test_run_command_with_sudo
```

## Test Structure

- **test_deploy.py** - Unit tests for core functionality (mocked)
- **test_integration.py** - Integration tests (require real infrastructure, skipped by default)

## Writing New Tests

1. Create test functions starting with `test_`
2. Use `@pytest.mark.unit` for fast unit tests
3. Use `@pytest.mark.integration` for integration tests
4. Use `@pytest.mark.slow` for tests that take a long time
5. Mock external dependencies (SSH connections, file system, etc.)

## Example Test

```python
def test_my_function(mock_connection):
    from deploy import my_function

    with patch('deploy.SOME_VAR', 'value'):
        result = my_function(mock_connection)
        assert result is not None
```

## CI/CD

Tests run automatically on:
- Push to main/develop branches
- Pull requests
- Manual trigger via workflow_dispatch

See `.github/workflows/test.yml` for CI configuration.
