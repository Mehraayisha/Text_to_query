# MongoDB Agent Tests

This directory contains the test suite for the mongodb_agent package.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=mongodb_agent --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_agent.py
```

### Run with verbose output
```bash
pytest -v
```

### Run only integration tests
```bash
pytest -m integration
```

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_agent.py` - Tests for core agent functionality
- `test_query_executor.py` - Tests for query execution
- `test_router.py` - Tests for routing logic
- `test_selector.py` - Tests for semantic model selection
- `test_query_refiner.py` - Tests for query refinement
- `test_output_parser.py` - Tests for output parsing
- `test_integration.py` - End-to-end integration tests

## Test Requirements

Install test dependencies:
```bash
pip install pytest pytest-cov pytest-mock
```

## Writing Tests

1. Use fixtures from `conftest.py` for common test objects
2. Mock external dependencies (MongoDB, LLM)
3. Test both success and error cases
4. Add integration tests for critical workflows
5. Maintain test coverage above 80%
