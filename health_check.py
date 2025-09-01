#!/usr/bin/env python3
"""
Health Check Script for Legal Citation Graph
This script provides simple verification that the system is working
"""
import requests
import time
import sys
import os
from pathlib import Path

def print_status(message, status="INFO"):
    """Print a formatted status message"""
    status_indicators = {
        "INFO": "[INFO]",
        "SUCCESS": "[PASS]",
        "WARNING": "[WARN]",
        "ERROR": "[FAIL]"
    }
    indicator = status_indicators.get(status, "[INFO]")
    print(f"{indicator} {message}")

def check_backend_health(base_url="http://localhost:8000"):
    """Check if backend is healthy"""
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/health", timeout=5)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") in ["ok", "healthy"]:
                print_status(f"Backend Health: OK (Response time: {response_time:.2f}s)", "SUCCESS")
                return True
            else:
                print_status(f"Backend Health: Unexpected response: {data}", "WARNING")
                return False
        else:
            print_status(f"Backend Health: HTTP {response.status_code}", "ERROR")
            return False
            
    except requests.exceptions.ConnectionError:
        print_status("Backend Health: Connection refused - Backend not running", "ERROR")
        return False
    except requests.exceptions.Timeout:
        print_status("Backend Health: Timeout - Backend not responding", "ERROR")
        return False
    except Exception as e:
        print_status(f"Backend Health: Error - {e}", "ERROR")
        return False

def check_api_endpoints(base_url="http://localhost:8000"):
    """Check if API endpoints are accessible"""
    endpoints = [
        ("/v1/documents", "Documents API"),
        ("/v1/graph", "Graph API"),
        ("/docs", "API Documentation"),
        ("/openapi.json", "OpenAPI Schema")
    ]
    
    success_count = 0
    total_count = len(endpoints)
    
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code in [200, 404]:  # 404 is okay for empty data
                print_status(f"{name}: Accessible (HTTP {response.status_code})", "SUCCESS")
                success_count += 1
            else:
                print_status(f"{name}: HTTP {response.status_code}", "WARNING")
        except Exception as e:
            print_status(f"{name}: Error - {e}", "ERROR")
    
    print_status(f"API Endpoints: {success_count}/{total_count} accessible", 
                "SUCCESS" if success_count == total_count else "WARNING")
    return success_count == total_count

def check_frontend_accessibility(base_url="http://localhost:3000"):
    """Check if frontend is accessible"""
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print_status("Frontend: Accessible", "SUCCESS")
            return True
        else:
            print_status(f"Frontend: HTTP {response.status_code}", "WARNING")
            return False
    except requests.exceptions.ConnectionError:
        print_status("Frontend: Connection refused - Frontend not running", "WARNING")
        return False
    except Exception as e:
        print_status(f"Frontend: Error - {e}", "ERROR")
        return False

def check_file_structure():
    """Check if required files and directories exist"""
    required_paths = [
        "backend/",
        "frontend/",
        "tests/",
        "data/",
        "requirements.txt",
        "docker-compose.yml",
        "Dockerfile"
    ]
    
    missing_paths = []
    for path in required_paths:
        if not Path(path).exists():
            missing_paths.append(path)
    
    if missing_paths:
        print_status(f"File Structure: Missing {len(missing_paths)} paths: {', '.join(missing_paths)}", "WARNING")
        return False
    else:
        print_status("File Structure: All required paths exist", "SUCCESS")
        return True

def check_docker_status():
    """Check if Docker containers are running"""
    try:
        import subprocess
        result = subprocess.run(["docker", "ps", "--filter", "name=legal-citation-graph"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Header + containers
                container_count = len(lines) - 1
                print_status(f"Docker: {container_count} containers running", "SUCCESS")
                return True
            else:
                print_status("Docker: No containers running", "WARNING")
                return False
        else:
            print_status("Docker: Command failed", "WARNING")
            return False
    except FileNotFoundError:
        print_status("Docker: Not installed or not in PATH", "WARNING")
        return False
    except Exception as e:
        print_status(f"Docker: Error - {e}", "WARNING")
        return False

def run_health_check():
    """Run complete health check"""
    print("Legal Citation Graph Health Check")
    print("=" * 50)
    
    # Check file structure
    file_structure_ok = check_file_structure()
    print()
    
    # Check Docker status
    docker_ok = check_docker_status()
    print()
    
    # Check backend
    backend_ok = check_backend_health()
    print()
    
    # Check API endpoints
    api_ok = check_api_endpoints()
    print()
    
    # Check frontend
    frontend_ok = check_frontend_accessibility()
    print()
    
    # Summary
    print("=" * 50)
    print("HEALTH CHECK SUMMARY")
    print("=" * 50)
    
    checks = [
        ("File Structure", file_structure_ok),
        ("Docker Status", docker_ok),
        ("Backend Health", backend_ok),
        ("API Endpoints", api_ok),
        ("Frontend Access", frontend_ok)
    ]
    
    passed = sum(1 for _, status in checks if status)
    total = len(checks)
    
    for name, status in checks:
        indicator = "[PASS]" if status else "[FAIL]"
        print(f"{indicator} {name}")
    
    print(f"\nOverall Status: {passed}/{total} checks passed")
    
    if passed == total:
        print_status("System is healthy and fully operational!", "SUCCESS")
        return 0
    elif passed >= total * 0.6:
        print_status("System is partially operational", "WARNING")
        return 1
    else:
        print_status("System has significant issues", "ERROR")
        return 2

if __name__ == "__main__":
    try:
        exit_code = run_health_check()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nHealth check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during health check: {e}")
        sys.exit(2)
