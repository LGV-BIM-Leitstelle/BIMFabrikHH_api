# BIMFabrikHH API Tests

This directory contains test files for the BIMFabrikHH API.

## Quick Start

**Run fast tests (without Celery worker):**
```bash
pytest tests/ -m "not requires_worker"
```

**Run all tests:**
```bash
pytest tests/ -v
```

## Test Files

### `test_api_endpoints.py`
Comprehensive tests for FastAPI HTTP endpoints:
- Main routes (landing page, root)
- OGC API Processes endpoints (list, describe, execute)
- Job status and results endpoints
- CORS header validation
- API documentation endpoints
- Error handling (404, 405, 422)
- Input validation
- Content negotiation
- End-to-end workflow tests

### `test_tree_model_generation.py`
Tests for tree model generation:
- Successful model generation
- Error handling
- Invalid input validation
- Integration tests

### `test_city_model_generation.py`
Tests for city model generation:
- Successful model generation
- Too many tiles handling
- Exception handling
- Integration tests

### `test_dgm_model_generation.py`
Tests for DGM/terrain model generation:
- Successful model generation
- Tile limit validation
- Error handling
- Integration tests

### `test_celery_tasks.py`
Comprehensive Celery task tests (pytest):
- Task configuration and registration
- Task execution with mocked dependencies
- Task results and state tracking
- Progress tracking
- Input validation
- Error handling

### `test_bim_model_generation.py`
BIM model generation tests (pytest):
- Tree model generation
- City model generation
- DGM/terrain model generation
- Tile limit validation
- Exception handling

### `test_celery_configuration.py`
Celery app configuration tests:
- App name and setup
- Broker configuration
- Backend configuration

### `test_celery_workers.py`
Basic Celery worker tests:
- In-memory Celery setup
- Simple task definition and execution

### `test_celery_database.py`
Legacy Celery database inspection tests (unittest):
- Database existence and structure
- Table schema validation
- Task count and status reporting
- Database integrity checks

### `test_database.py`
Comprehensive database tests with pytest fixtures:
- Database configuration and initialization
- Connection management and context managers
- Schema validation and constraints
- Result storage and retrieval
- Query operations and filtering
- Database utilities (backup, cleanup)
- Transaction management (commit, rollback, autocommit)
- Concurrent access scenarios
- Error handling and recovery
- Database maintenance (VACUUM, ANALYZE)
- Integrity checks

## Running Tests

### Using pytest (Recommended)

**Run all tests:**
```bash
pytest tests/
```

**Run specific test file:**
```bash
# API endpoint tests
pytest tests/test_api_endpoints.py

# Database tests
pytest tests/test_database.py

# Celery task tests
pytest tests/test_celery_tasks.py

# BIM model generation tests
pytest tests/test_bim_model_generation.py

# Tree model tests (legacy)
pytest tests/test_tree_model_generation.py

# City model tests (legacy)
pytest tests/test_city_model_generation.py

# DGM model tests (legacy)
pytest tests/test_dgm_model_generation.py
```

**Run tests by marker:**
```bash
# Run only unit tests
pytest tests/ -m unit

# Run only integration tests
pytest tests/ -m integration

# Run only tree model tests
pytest tests/ -m tree

# Run only slow tests
pytest tests/ -m slow
```

**Run with verbose output:**
```bash
pytest tests/ -v
```

**Run with coverage:**
```bash
pytest tests/ --cov=src --cov-report=html
```

### Using unittest (Legacy)

**Run all tests:**
```bash
python tests/run_tests.py
```

**Run specific test:**
```bash
# Run Celery tasks test
python tests/run_tests.py celery_tasks

# Run Celery database test
python tests/run_tests.py celery_database
```

**Run individual test files:**
```bash
# Run Celery tasks test directly
python tests/test_celery_tasks.py

# Run database inspection directly
python tests/test_celery_database.py
```

**Using Python's unittest discovery:**
```bash
# Run all tests with unittest discovery
python -m unittest discover tests

# Run specific test class
python -m unittest tests.test_celery_tasks.TestCeleryTasks
```

## Test Requirements

### Core Requirements
- Python 3.11+
- All project dependencies installed (`poetry install`)
- pytest installed (included in dev dependencies)

### Optional Requirements
- Celery worker (for real task execution tests)
- SQLite database (`celerydb.sqlite`) for database tests
- Running FastAPI server (for manual integration testing)

## Test Structure

Tests use **pytest** framework (with some legacy unittest tests) and follow these conventions:

### Pytest Tests (Recommended)
- Test classes don't require inheritance
- Test functions/methods start with `test_`
- Use pytest fixtures for setup/teardown
- Use pytest markers for categorization
- Clear assertions with helpful error messages

### Legacy Unittest Tests
- Test classes inherit from `unittest.TestCase`
- Test methods start with `test_`
- Use setUp() and tearDown() methods
- Compatible with both pytest and unittest runners

### Test Organization
- **Unit tests**: Fast, isolated, mocked dependencies
- **Integration tests**: Test component interactions with mocks
- **End-to-end tests**: Full workflow tests

## Test Coverage

Current test coverage by component:

| Component | Coverage | Test File |
|-----------|----------|-----------|
| **API Endpoints** | ✅ Comprehensive | `test_api_endpoints.py` |
| **Database** | ✅ Comprehensive | `test_database.py` |
| **Celery Tasks** | ✅ Comprehensive | `test_celery_tasks.py` |
| **BIM Models** | ✅ Good | `test_bim_model_generation.py` |
| **Celery Config** | ✅ Good | `test_celery_configuration.py` |
| **Tree Models** | ✅ Good (Legacy) | `test_tree_model_generation.py` |
| **City Models** | ✅ Good (Legacy) | `test_city_model_generation.py` |
| **DGM Models** | ✅ Good (Legacy) | `test_dgm_model_generation.py` |
| **Configuration** | ⚠️ Partial | `test_config.py` |

## Test Markers

Available pytest markers for filtering tests:

- `@pytest.mark.unit` - Fast unit tests with mocked dependencies
- `@pytest.mark.integration` - Integration tests with external dependencies
- `@pytest.mark.slow` - Slow-running tests (performance tests)
- `@pytest.mark.tree` - Tree model generation tests
- `@pytest.mark.city` - City model generation tests
- `@pytest.mark.dgm` - DGM/terrain model generation tests
- `@pytest.mark.celery` - Celery task functionality tests
- `@pytest.mark.error` - Error handling tests

## Notes

- **API endpoint tests** use `TestClient` and don't require a running server
- **Celery task tests** use mocks by default (no worker required)
- **Database tests** are non-destructive and only read data
- Some tests may be skipped if prerequisites are not met
- Live Hamburg API URL tests are in `test_external_api_urls.py` (marker: `external_api`); skip with `pytest -m "not external_api"` 