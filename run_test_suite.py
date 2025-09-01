#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Legal Citation Graph
Follows industry standard testing practices and provides detailed reporting
"""
import subprocess
import sys
import os
import time
import argparse
from pathlib import Path

class TestRunner:
    """Industry standard test runner with comprehensive reporting"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
        
    def print_header(self, title):
        """Print formatted header"""
        print(f"\n{'='*80}")
        print(f" {title}")
        print(f"{'='*80}")
    
    def print_section(self, title):
        """Print formatted section"""
        print(f"\n{'-'*60}")
        print(f" {title}")
        print(f"{'-'*60}")
    
    def run_command(self, command, description, category):
        """Run a command and capture results"""
        print(f"\n[RUNNING] {description}")
        print(f"Command: {command}")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout
            )
            end_time = time.time()
            duration = end_time - start_time
            
            success = result.returncode == 0
            
            # Store results
            self.results[category] = {
                'success': success,
                'duration': duration,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command
            }
            
            if success:
                print(f"[PASS] {description} completed in {duration:.2f}s")
                if result.stdout.strip():
                    print("Output:")
                    print(result.stdout.strip())
            else:
                print(f"[FAIL] {description} failed after {duration:.2f}s")
                if result.stderr.strip():
                    print("Error Output:")
                    print(result.stderr.strip())
                if result.stdout.strip():
                    print("Standard Output:")
                    print(result.stdout.strip())
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"[FAIL] {description} timed out after 5 minutes")
            self.results[category] = {
                'success': False,
                'duration': 300,
                'return_code': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'command': command
            }
            return False
            
        except Exception as e:
            print(f"[FAIL] {description} failed with exception: {e}")
            self.results[category] = {
                'success': False,
                'duration': 0,
                'return_code': -1,
                'stdout': '',
                'stderr': str(e),
                'command': command
            }
            return False
    
    def run_health_check(self):
        """Run system health check"""
        self.print_section("System Health Check")
        return self.run_command(
            "python health_check.py",
            "System Health Check",
            "health_check"
        )
    
    def run_test_categories(self):
        """Run tests by category"""
        self.print_section("Test Category Execution")
        
        test_categories = [
            ("pytest tests/test_health.py -v --tb=short", "Health Check Tests", "health_tests"),
            ("pytest tests/test_api_endpoints.py -v --tb=short", "API Endpoint Tests", "api_tests"),
            ("pytest tests/test_models.py -v --tb=short", "Database Model Tests", "model_tests"),
            ("pytest tests/test_citation_parser.py -v --tb=short", "Citation Parser Tests", "parser_tests"),
            ("pytest tests/test_integration.py -v --tb=short", "Integration Tests", "integration_tests"),
            ("pytest tests/test_frontend_components.py -v --tb=short", "Frontend Component Tests", "frontend_tests"),
        ]
        
        results = []
        for command, description, category in test_categories:
            success = self.run_command(command, description, category)
            results.append((category, success))
        
        return results
    
    def run_full_test_suite(self):
        """Run complete test suite"""
        self.print_section("Complete Test Suite")
        return self.run_command(
            "pytest tests/ -v --tb=short --junitxml=test-results.xml --html=test-results.html --self-contained-html",
            "Complete Test Suite with Reports",
            "full_suite"
        )
    
    def run_marked_tests(self, marker):
        """Run tests with specific markers"""
        self.print_section(f"Tests with '{marker}' marker")
        return self.run_command(
            f"pytest tests/ -m {marker} -v --tb=short",
            f"Tests marked '{marker}'",
            f"marked_{marker}"
        )
    
    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_section("Test Execution Report")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result['success'])
        failed_tests = total_tests - passed_tests
        
        # Calculate total duration
        total_duration = sum(result['duration'] for result in self.results.values())
        
        print(f"Total Test Categories: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Total Execution Time: {total_duration:.2f}s")
        
        print(f"\nDetailed Results:")
        print(f"{'Category':<25} {'Status':<8} {'Duration':<10} {'Return Code':<12}")
        print(f"{'-'*25} {'-'*8} {'-'*10} {'-'*12}")
        
        for category, result in self.results.items():
            status = "PASS" if result['success'] else "FAIL"
            duration = f"{result['duration']:.2f}s"
            return_code = str(result['return_code'])
            print(f"{category:<25} {status:<8} {duration:<10} {return_code:<12}")
        
        # Summary
        print(f"\n{'='*60}")
        if failed_tests == 0:
            print("ALL TESTS PASSED - System is fully operational")
            return 0
        elif failed_tests <= total_tests * 0.2:
            print("MOST TESTS PASSED - System is mostly operational")
            return 1
        else:
            print("MANY TESTS FAILED - System has significant issues")
            return 2
    
    def run(self, args):
        """Main test execution method"""
        self.start_time = time.time()
        
        self.print_header("Legal Citation Graph Test Suite")
        
        # Check prerequisites
        if not self.check_prerequisites():
            return 1
        
        # Run health check first
        if not self.run_health_check():
            print("\n[WARN] Health check failed - continuing with tests anyway")
        
        # Run tests based on arguments
        if args.marker:
            self.run_marked_tests(args.marker)
        elif args.category:
            self.run_test_categories()
        else:
            # Run full test suite
            self.run_test_categories()
            self.run_full_test_suite()
        
        self.end_time = time.time()
        
        # Generate report
        exit_code = self.generate_report()
        
        # Print final summary
        total_time = self.end_time - self.start_time
        print(f"\nTotal Test Suite Execution Time: {total_time:.2f}s")
        
        return exit_code
    
    def check_prerequisites(self):
        """Check if all prerequisites are met"""
        self.print_section("Prerequisites Check")
        
        # Check Python
        try:
            result = subprocess.run(["python", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[PASS] Python: {result.stdout.strip()}")
            else:
                print("[FAIL] Python not available")
                return False
        except Exception:
            print("[FAIL] Python not available")
            return False
        
        # Check pytest
        try:
            result = subprocess.run(["pytest", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[PASS] pytest: {result.stdout.strip()}")
            else:
                print("[FAIL] pytest not available")
                return False
        except Exception:
            print("[FAIL] pytest not available")
            return False
        
        # Check tests directory
        if not Path("tests").exists():
            print("[FAIL] tests directory not found")
            return False
        print("[PASS] tests directory found")
        
        # Check health check script
        if not Path("health_check.py").exists():
            print("[FAIL] health_check.py not found")
            return False
        print("[PASS] health_check.py found")
        
        return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Legal Citation Graph Test Suite Runner")
    parser.add_argument("--marker", "-m", help="Run tests with specific marker (e.g., unit, integration)")
    parser.add_argument("--category", "-c", action="store_true", help="Run tests by category")
    parser.add_argument("--full", "-f", action="store_true", help="Run full test suite with reports")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    try:
        exit_code = runner.run(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during test execution: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
