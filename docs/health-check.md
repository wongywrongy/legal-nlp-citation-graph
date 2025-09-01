# Health Check System Documentation

## Overview

The Legal Citation Graph system includes a comprehensive health check mechanism designed to verify the operational status of all system components. This system provides clear, professional status reporting and automated verification of system health.

## Health Check Components

### 1. System Health Verification Script

The primary health check script (`health_check.py`) performs comprehensive system validation:

- **File Structure Validation**: Verifies all required directories and files exist
- **Docker Status Check**: Confirms container health and operational status
- **Backend API Health**: Validates backend service responsiveness
- **API Endpoint Verification**: Tests accessibility of all API endpoints
- **Frontend Service Check**: Verifies frontend application availability

### 2. Automated Test Suite

The testing framework (`run_test_suite.py`) provides comprehensive testing capabilities:

- **Test Categorization**: Organized test execution by component type
- **Automated Reporting**: Generates JUnit XML and HTML test reports
- **Performance Metrics**: Tracks test execution time and success rates
- **Prerequisite Validation**: Ensures testing environment is properly configured

## Running Health Checks

### Quick System Verification

Execute the comprehensive health check script:

```bash
python health_check.py
```

**Expected Output:**
```
Legal Citation Graph Health Check
==================================================
[PASS] File Structure: All required paths exist

[PASS] Docker: 2 containers running

[PASS] Backend Health: OK (Response time: 0.15s)

[PASS] Documents API: Accessible (HTTP 200)
[PASS] Graph API: Accessible (HTTP 200)
[PASS] API Documentation: Accessible (HTTP 200)
[PASS] OpenAPI Schema: Accessible (HTTP 200)
[PASS] API Endpoints: 4/4 accessible

[PASS] Frontend: Accessible

==================================================
HEALTH CHECK SUMMARY
==================================================
[PASS] File Structure
[PASS] Docker Status
[PASS] Backend Health
[PASS] API Endpoints
[PASS] Frontend Access

Overall Status: 5/5 checks passed
[PASS] System is healthy and fully operational!
```

### Comprehensive Test Execution

#### Full Test Suite

```bash
# Execute complete test suite with detailed reporting
python run_test_suite.py --full
```

#### Test Categories

```bash
# Run tests by category
python run_test_suite.py --category
```

#### Specific Test Types

```bash
# Run tests with specific markers
python run_test_suite.py --marker unit
python run_test_suite.py --marker integration
python run_test_suite.py --marker api
python run_test_suite.py --marker health
```

### Individual Test Execution

#### Health Check Tests

```bash
# Run health check specific tests
pytest tests/test_health.py -v

# Run with coverage reporting
pytest tests/test_health.py -v --cov=backend --cov-report=html
```

#### API Endpoint Tests

```bash
# Test API functionality
pytest tests/test_api_endpoints.py -v

# Test specific endpoint categories
pytest tests/test_api_endpoints.py -v -m "api and fast"
```

#### Database and Model Tests

```bash
# Test data models and persistence
pytest tests/test_models.py -v

# Test database operations
pytest tests/test_models.py -v -m database
```

#### Integration Tests

```bash
# Test component interactions
pytest tests/test_integration.py -v

# Test end-to-end workflows
pytest tests/test_integration.py -v -m e2e
```

## Status Indicators

The health check system uses clear, professional status indicators:

| Indicator | Meaning | Description |
|-----------|---------|-------------|
| `[PASS]` | Success | Component is functioning correctly |
| `[FAIL]` | Critical Error | Component has critical issues requiring immediate attention |
| `[WARN]` | Warning | Component has non-critical issues that should be monitored |
| `[INFO]` | Information | General informational messages about system status |

## Test Markers

The testing framework uses industry-standard markers for test categorization:

### Core Test Types

- **`unit`**: Unit tests for individual components in isolation
- **`integration`**: Integration tests for component interactions
- **`e2e`**: End-to-end tests for complete workflow validation

### Component-Specific Markers

- **`api`**: API endpoint and response validation tests
- **`database`**: Database operations and model tests
- **`frontend`**: Frontend component and configuration tests
- **`health`**: System health and operational verification tests

### Execution Characteristics

- **`fast`**: Tests that complete quickly (under 1 second)
- **`slow`**: Tests that require longer execution time
- **`smoke`**: Basic functionality verification tests

## Health Check Failures

### Common Failure Scenarios

1. **Docker Container Issues**
   - Containers not running
   - Port conflicts
   - Resource constraints

2. **Backend Service Problems**
   - Database connection failures
   - File permission issues
   - Service startup errors

3. **Frontend Service Issues**
   - Build failures
   - Port conflicts
   - Dependency issues

4. **Network Connectivity Problems**
   - Service-to-service communication failures
   - External API access issues

### Troubleshooting Steps

#### 1. Verify Container Status

```bash
# Check running containers
docker ps

# View container logs
docker-compose logs backend
docker-compose logs frontend

# Check container health
docker-compose ps
```

#### 2. Verify Service Accessibility

```bash
# Test backend health
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000

# Check API endpoints
curl http://localhost:8000/v1/documents
```

#### 3. Check File Permissions

```bash
# Verify data directory permissions
ls -la data/
ls -la data/pdfs/

# Check database file
ls -la data/citations.db
```

#### 4. Restart Services

```bash
# Restart development environment
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up --build -d

# Restart production environment
docker-compose down
docker-compose up --build -d
```

## Automated Health Monitoring

### Continuous Health Checks

For production environments, consider implementing automated health monitoring:

```bash
# Create a monitoring script
#!/bin/bash
while true; do
    python health_check.py
    if [ $? -ne 0 ]; then
        echo "Health check failed at $(date)"
        # Send alert or restart services
    fi
    sleep 300  # Check every 5 minutes
done
```

### Integration with CI/CD

The health check system integrates with continuous integration pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Health Checks
  run: |
    python health_check.py
    python run_test_suite.py --full
```

## Performance Considerations

### Health Check Optimization

- **Response Time Thresholds**: Health checks should complete within 30 seconds
- **Resource Usage**: Minimize system resource consumption during health checks
- **Parallel Execution**: Run independent checks concurrently when possible

### Test Suite Performance

- **Fast Tests**: Unit tests should execute in under 1 second
- **Integration Tests**: Complete within 10 seconds
- **End-to-End Tests**: Complete within 60 seconds

## Reporting and Logging

### Health Check Reports

Health check results are logged with timestamps and detailed status information:

```
[2025-01-01 10:00:00] [INFO] Starting health check
[2025-01-01 10:00:01] [PASS] File structure validation completed
[2025-01-01 10:00:02] [PASS] Docker containers operational
[2025-01-01 10:00:03] [PASS] Backend service healthy
[2025-01-01 10:00:04] [PASS] Frontend service accessible
[2025-01-01 10:00:04] [INFO] Health check completed successfully
```

### Test Suite Reports

The test suite generates comprehensive reports:

- **Console Output**: Real-time test execution status
- **JUnit XML**: Standard format for CI/CD integration
- **HTML Reports**: Human-readable test results with coverage data

## Best Practices

### Health Check Implementation

1. **Comprehensive Coverage**: Test all critical system components
2. **Clear Status Reporting**: Use unambiguous status indicators
3. **Performance Monitoring**: Track response times and resource usage
4. **Automated Recovery**: Implement automatic service restart for failed components

### Testing Strategy

1. **Test Isolation**: Ensure tests don't interfere with each other
2. **Data Cleanup**: Clean up test data after execution
3. **Mock External Services**: Use mocks for external dependencies
4. **Regular Execution**: Run health checks and tests regularly

## Support and Maintenance

### Documentation Updates

Keep health check documentation current with:
- New test categories and markers
- Updated troubleshooting procedures
- Performance benchmarks and thresholds

### System Evolution

As the system evolves:
- Add new health check categories
- Update test coverage for new features
- Refine performance thresholds
- Enhance automated recovery mechanisms
