#!/usr/bin/env python3
"""
Test runner for BIMFabrikHH API tests
"""

import os
import sys

import pytest

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_all_tests():
    """Run the full test suite via pytest."""
    print("=== Running BIMFabrikHH API Tests ===\n")
    return pytest.main([TESTS_DIR, "-v"]) == 0


def run_specific_test(test_name):
    """Run a specific test module by short name (e.g. ``celery_database``)."""
    print(f"=== Running Test: {test_name} ===\n")

    module_path = os.path.join(TESTS_DIR, f"test_{test_name}.py")
    if not os.path.exists(module_path):
        print(f"Unknown test: {test_name}")
        print(f"Expected module not found: {module_path}")
        return False

    return pytest.main([module_path, "-v"]) == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        success = run_specific_test(sys.argv[1])
    else:
        # Run all tests
        success = run_all_tests()

    sys.exit(0 if success else 1)
