#!/usr/bin/env python3
"""
Simple Test Runner for Legal Citation Graph
Run this script to execute all tests with clear output
"""
import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"TESTING: {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[PASS] SUCCESS")
            if result.stdout:
                print("Output:")
                print(result.stdout)
        else:
            print("[FAIL] FAILED")
            if result.stderr:
                print("Error:")
                print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"[FAIL] ERROR: {e}")
        return False

def main():
    """Main test runner"""
    print("Legal Citation Graph Test Runner")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("tests"):
        print("[FAIL] Error: 'tests' directory not found. Please run from project root.")
        sys.exit(1)
    
    # Check if pytest is available
    try:
        subprocess.run(["pytest", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[FAIL] Error: pytest not found. Please install with: pip install pytest")
        sys.exit(1)
    
    success_count = 0
    total_tests = 0
    
    # Test categories
    test_categories = [
        ("pytest tests/test_health.py -v", "Health Check Tests"),
        ("pytest tests/test_api_endpoints.py -v", "API Endpoint Tests"),
        ("pytest tests/test_models.py -v", "Database Model Tests"),
        ("pytest tests/test_citation_parser.py -v", "Citation Parser Tests"),
        ("pytest tests/test_integration.py -v", "Integration Tests"),
        ("pytest tests/test_frontend_components.py -v", "Frontend Component Tests"),
    ]
    
    # Run each test category
    for command, description in test_categories:
        total_tests += 1
        if run_command(command, description):
            success_count += 1
    
    # Run all tests together
    print(f"\n{'='*60}")
    print("RUNNING: Complete Test Suite")
    print(f"{'='*60}")
    
    all_tests_success = run_command("pytest tests/ -v", "Complete Test Suite")
    if all_tests_success:
        success_count += 1
    total_tests += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"[PASS] Passed: {success_count}")
    print(f"[FAIL] Failed: {total_tests - success_count}")
    print(f"Success Rate: {(success_count/total_tests)*100:.1f}%")
    
    if success_count == total_tests:
        print("\n[PASS] ALL TESTS PASSED! System is working correctly.")
        return 0
    else:
        print(f"\n[WARN] {total_tests - success_count} test categories failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
