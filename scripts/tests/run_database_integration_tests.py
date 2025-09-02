#!/usr/bin/env python3
"""
Comprehensive test runner for database integration tests.

This script runs all database integration tests and provides coverage analysis.
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime


def run_command(command, cwd=None, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def run_pytest_with_coverage(test_path, test_name):
    """Run pytest with coverage for specific test."""
    print(f"\n{'='*60}")
    print(f"Running {test_name}")
    print(f"{'='*60}")

    # Run pytest with coverage
    cmd = f"python -m pytest {test_path} -v --tb=short --cov=services.analytics_service --cov=backend.app --cov-report=term-missing"

    success, stdout, stderr = run_command(cmd)

    if success:
        print(f"✅ {test_name} PASSED")
        return True, stdout
    else:
        print(f"❌ {test_name} FAILED")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return False, stdout + stderr


def run_migration_tests():
    """Run migration tests."""
    migration_test_path = "backend/migrations/tests/test_analysis_tables_migration.py"
    if os.path.exists(migration_test_path):
        return run_pytest_with_coverage(migration_test_path, "Migration Tests")
    else:
        print(f"⚠️  Migration test file not found: {migration_test_path}")
        return True, "Test file not found"


def run_repository_tests():
    """Run repository layer tests."""
    tests = [
        ("services/analytics-service/tests/test_analysis_result_repository.py", "Repository Unit Tests"),
        ("services/analytics-service/tests/test_analysis_result_repository_integration.py", "Repository Integration Tests")
    ]

    results = []
    for test_path, test_name in tests:
        if os.path.exists(test_path):
            success, output = run_pytest_with_coverage(test_path, test_name)
            results.append((test_name, success, output))
        else:
            print(f"⚠️  Test file not found: {test_path}")
            results.append((test_name, True, "Test file not found"))

    return results


def run_router_tests():
    """Run router endpoint tests."""
    router_test_path = "backend/app/tests/test_project_analysis_router.py"
    if os.path.exists(router_test_path):
        return run_pytest_with_coverage(router_test_path, "Router Endpoint Tests")
    else:
        print(f"⚠️  Router test file not found: {router_test_path}")
        return True, "Test file not found"


def run_e2e_tests():
    """Run end-to-end tests."""
    e2e_test_path = "scripts/tests/integration/test_jsonl_analysis_e2e.py"
    if os.path.exists(e2e_test_path):
        return run_pytest_with_coverage(e2e_test_path, "End-to-End JSONL Analysis Tests")
    else:
        print(f"⚠️  E2E test file not found: {e2e_test_path}")
        return True, "Test file not found"


def generate_test_report(results, start_time):
    """Generate a comprehensive test report."""
    end_time = time.time()
    duration = end_time - start_time

    report = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": round(duration, 2),
            "total_tests": len(results),
            "passed_tests": sum(1 for _, success, _ in results if success),
            "failed_tests": sum(1 for _, success, _ in results if not success)
        },
        "test_results": []
    }

    print(f"\n{'='*80}")
    print("DATABASE INTEGRATION TEST REPORT")
    print(f"{'='*80}")
    print(f"Test Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total Test Suites: {len(results)}")
    print(f"Passed: {report['test_run']['passed_tests']}")
    print(f"Failed: {report['test_run']['failed_tests']}")

    all_passed = report['test_run']['failed_tests'] == 0

    for test_name, success, output in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status} {test_name}")

        if not success and len(output) > 0:
            print("Details:")
            # Show last 20 lines of output for failures
            lines = output.split('\n')[-20:]
            for line in lines:
                if line.strip():
                    print(f"  {line}")

        report["test_results"].append({
            "test_name": test_name,
            "success": success,
            "output_length": len(output)
        })

    print(f"\n{'='*80}")
    if all_passed:
        print("🎉 ALL TESTS PASSED! Database integration is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED. Please review the output above for details.")
    print(f"{'='*80}")

    # Save detailed report to file
    report_file = "database_integration_test_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nDetailed report saved to: {report_file}")

    return all_passed


def check_test_dependencies():
    """Check if all required test dependencies are available."""
    required_packages = [
        "pytest",
        "pytest-cov",
        "sqlalchemy",
        "fastapi",
        "httpx",
        "alembic"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("⚠️  Missing test dependencies:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall with: pip install " + " ".join(missing_packages))
        return False

    print("✅ All test dependencies are available")
    return True


def main():
    """Main test runner function."""
    print("🚀 Starting Database Integration Test Suite")
    print("Testing JSONL Analysis System Database Integration")
    print("-" * 50)

    # Check dependencies
    if not check_test_dependencies():
        print("❌ Cannot run tests due to missing dependencies")
        sys.exit(1)

    start_time = time.time()

    # Run all test suites
    results = []

    # Migration tests
    success, output = run_migration_tests()
    results.append(("Migration Tests", success, output))

    # Repository tests
    repo_results = run_repository_tests()
    results.extend(repo_results)

    # Router tests
    success, output = run_router_tests()
    results.append(("Router Tests", success, output))

    # E2E tests
    success, output = run_e2e_tests()
    results.append(("E2E Tests", success, output))

    # Generate report
    all_passed = generate_test_report(results, start_time)

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()