#!/usr/bin/env python3
"""
Test runner for BIMFabrikHH API tests
"""

import os
import sys
import unittest

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def run_all_tests():
    """Run all tests in the tests directory"""
    print("=== Running BIMFabrikHH API Tests ===\n")

    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n=== Test Results ===")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")

    if result.failures:
        print("\n=== Failures ===")
        for test, traceback in result.failures:
            print(f"FAIL: {test}")
            print(traceback)

    if result.errors:
        print("\n=== Errors ===")
        for test, traceback in result.errors:
            print(f"ERROR: {test}")
            print(traceback)

    return result.wasSuccessful()


def run_specific_test(test_name):
    """Run a specific test by name"""
    print(f"=== Running Test: {test_name} ===\n")

    # Import the specific test module
    if test_name == "celery_tasks":
        from tests.test_celery_tasks import TestCeleryTasks

        suite = unittest.TestLoader().loadTestsFromTestCase(TestCeleryTasks)
    elif test_name == "celery_database":
        from tests.test_celery_database import TestCeleryDatabase

        suite = unittest.TestLoader().loadTestsFromTestCase(TestCeleryDatabase)
    else:
        print(f"Unknown test: {test_name}")
        print("Available tests: celery_tasks, celery_database")
        return False

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all tests
        success = run_all_tests()

    sys.exit(0 if success else 1)
