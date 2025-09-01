# Testing Framework for Legal Citation Graph

This directory contains a comprehensive testing framework designed to verify that your Legal Citation Graph system is working correctly.

## 🚀 Quick Start

### 1. Install Test Dependencies
```bash
pip install -r requirements-test.txt
```

### 2. Run Health Check (Recommended First Step)
```bash
python health_check.py
```

### 3. Run All Tests
```bash
python tests/run_tests.py
```

### 4. Run Tests with pytest
```bash
pytest tests/ -v
```

## 🧪 Test Categories

### Health Check Tests (`test_health.py`)
**Purpose**: Verify basic system functionality
**Status**: Should ALWAYS pass
**Use Case**: Quick verification that system is operational

```bash
pytest tests/test_health.py -v
```

**What it tests**:
- Health endpoint responds correctly
- Fast response times (< 1 second)
- Consistent responses
- Handles multiple concurrent requests

### API Endpoint Tests (`test_api_endpoints.py`)
**Purpose**: Verify all API endpoints are accessible
**Status**: Should pass when backend is running
**Use Case**: Verify API functionality

```bash
pytest tests/test_api_endpoints.py -v
```

**What it tests**:
- All API endpoints return correct HTTP status codes
- JSON response structures are correct
- Pagination works correctly
- Error handling is graceful

### Database Model Tests (`test_models.py`)
**Purpose**: Verify data models work correctly
**Status**: Should always pass
**Use Case**: Verify data integrity

```bash
pytest tests/test_models.py -v
```

**What it tests**:
- Document model creation and validation
- Citation model creation and validation
- Model relationships work correctly
- Default values are set correctly

### Citation Parser Tests (`test_citation_parser.py`)
**Purpose**: Verify citation parsing logic
**Status**: Should always pass
**Use Case**: Verify citation extraction works

```bash
pytest tests/test_citation_parser.py -v
```

**What it tests**:
- Simple citation parsing (e.g., "410 U.S. 113 (1973)")
- Citations without years
- Multiple citations in one text
- Edge cases and error handling

### Integration Tests (`test_integration.py`)
**Purpose**: Verify complete workflows
**Status**: Should pass when system is fully operational
**Use Case**: End-to-end verification

```bash
pytest tests/test_integration.py -v
```

**What it tests**:
- Complete document workflow
- API consistency across endpoints
- Error handling under various conditions
- Performance under load

### Frontend Component Tests (`test_frontend_components.py`)
**Purpose**: Verify frontend structure and configuration
**Status**: Should pass when frontend is properly configured
**Use Case**: Verify frontend setup

```bash
pytest tests/test_frontend_components.py -v
```

**What it tests**:
- Component imports work correctly
- API client functions exist
- Required pages exist
- Configuration files are correct

## 🔍 Health Check Script

The `health_check.py` script provides a quick way to verify system health:

```bash
python health_check.py
```

**What it checks**:
- ✅ File structure integrity
- 🐳 Docker container status
- 🔌 Backend health and response time
- 🌐 API endpoint accessibility
- 🎨 Frontend accessibility

**Output Example**:
```
🏥 Legal Citation Graph Health Check
==================================================
✅ File Structure: All required paths exist

🐳 Docker: 3 containers running

✅ Backend Health: OK (Response time: 0.15s)

✅ API Endpoints: 4/4 accessible

✅ Frontend: Accessible

==================================================
📊 HEALTH CHECK SUMMARY
==================================================
✅ File Structure
✅ Docker Status
✅ Backend Health
✅ API Endpoints
✅ Frontend Access

Overall Status: 5/5 checks passed
🎉 System is healthy and fully operational!
```

## 🎯 Test Markers

Use pytest markers to run specific test categories:

```bash
# Run only health tests
pytest tests/ -m health

# Run only integration tests
pytest tests/ -m integration

# Run only unit tests
pytest tests/ -m unit

# Skip slow tests
pytest tests/ -m "not slow"
```

## 📊 Test Results Interpretation

### All Tests Pass (✅)
- System is fully operational
- All components are working correctly
- Ready for production use

### Most Tests Pass (⚠️)
- System is partially operational
- Some components may have issues
- Check failed tests for specific problems

### Many Tests Fail (❌)
- System has significant issues
- Core functionality may be broken
- Review error messages and fix issues

## 🛠️ Troubleshooting

### Common Issues

#### 1. Backend Not Running
```bash
# Start backend
python start_backend.py

# Or with Docker
docker-compose up -d
```

#### 2. Frontend Not Running
```bash
# Start frontend
cd frontend
npm run dev
```

#### 3. Database Issues
```bash
# Check database file exists
ls -la data/

# Recreate database
rm data/citations.db
python start_backend.py
```

#### 4. Docker Issues
```bash
# Check Docker status
docker ps

# Restart containers
docker-compose down
docker-compose up -d
```

### Test-Specific Issues

#### Health Tests Failing
- Check if backend is running on port 8000
- Verify health endpoint responds to `/health`
- Check network connectivity

#### API Tests Failing
- Verify backend is running and healthy
- Check API endpoints are accessible
- Review backend logs for errors

#### Model Tests Failing
- Check database schema is correct
- Verify SQLAlchemy models are properly defined
- Check database file permissions

## 🔧 Customizing Tests

### Adding New Tests

1. Create test file in `tests/` directory
2. Follow naming convention: `test_*.py`
3. Use descriptive test function names
4. Add appropriate markers

### Example Test Structure
```python
def test_new_feature():
    """Test description - what this test verifies"""
    # Arrange
    setup_data = "test data"
    
    # Act
    result = process_data(setup_data)
    
    # Assert
    assert result == "expected result"
    assert len(result) > 0
```

### Test Fixtures

Use fixtures for common setup:

```python
@pytest.fixture
def sample_document():
    return {
        "title": "Test Document",
        "fingerprint": "test_123",
        "source_path": "/test/path"
    }

def test_with_fixture(sample_document):
    assert sample_document["title"] == "Test Document"
```

## 📈 Continuous Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: pytest tests/ -v
```

## 🎯 Best Practices

1. **Run health check first** - Quick verification of system status
2. **Run tests regularly** - Catch issues early
3. **Fix failing tests** - Don't ignore test failures
4. **Add tests for new features** - Maintain test coverage
5. **Use descriptive test names** - Make tests self-documenting
6. **Keep tests simple** - Focus on one thing per test
7. **Use appropriate assertions** - Test specific behavior, not implementation

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/testing.html)
- [React Testing](https://reactjs.org/docs/testing.html)

## 🆘 Getting Help

If tests are failing and you need help:

1. Check the error messages carefully
2. Run health check to identify system issues
3. Review the troubleshooting section above
4. Check backend and frontend logs
5. Verify Docker containers are running correctly

Remember: **Tests are your friend!** They help ensure your system works correctly and catch issues before they become problems.
