@echo off
echo Legal Citation Graph Test Runner (Windows)
echo ================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Error: Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Check if tests directory exists
if not exist "tests" (
    echo [FAIL] Error: 'tests' directory not found. Please run from project root.
    pause
    exit /b 1
)

echo [PASS] Python found
echo [PASS] Tests directory found
echo.

echo [INFO] Running Health Check...
python health_check.py
echo.

echo [INFO] Running All Tests...
python tests/run_tests.py
echo.

echo [INFO] Test execution complete!
echo.
echo [INFO] Tips:
echo    - Run 'python health_check.py' for quick system verification
echo    - Run 'pytest tests/ -v' for detailed test output
echo    - Check the test output above for any failures
echo.

pause
