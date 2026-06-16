#!/usr/bin/env python3
"""
Test runner for BIM model generation tests.

This script runs comprehensive tests for the generate_bim_modells.py module,
including unit tests and integration tests with proper reporting.
"""

import os
import sys
import time
import unittest
from typing import Tuple

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def run_bim_model_tests() -> Tuple[int, int]:
    """
    Run all BIM model generation tests.

    Returns:
        Tuple of (total_tests, failed_tests)
    """
    print("=" * 60)
    print("BIM Model Generation Tests")
    print("=" * 60)

    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern="test_generate_bim_models.py")

    # Create test runner with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2, stream=sys.stdout, descriptions=True, failfast=False
    )

    # Run tests
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")

    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)

    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)

    return result.testsRun, len(result.failures) + len(result.errors)


def run_specific_test(test_name: str) -> bool:
    """
    Run a specific test by name.

    Args:
        test_name: Name of the test to run (e.g., 'TestGenerateBimModels.test_execute_generate_tree_model_success')

    Returns:
        True if test passed, False otherwise
    """
    print(f"Running specific test: {test_name}")

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(
        test_name, module=__import__("test_generate_bim_models")
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return len(result.failures) + len(result.errors) == 0


def run_test_categories() -> None:
    """Run tests by category with detailed reporting."""
    print("=" * 60)
    print("Running BIM Model Tests by Category")
    print("=" * 60)

    # Test categories
    categories = {
        "Unit Tests": "TestGenerateBimModels",
        "Integration Tests": "TestGenerateBimModelsIntegration",
    }

    total_passed = 0
    total_failed = 0

    for category_name, test_class in categories.items():
        print(f"\n{category_name}:")
        print("-" * 40)

        try:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromName(
                test_class, module=__import__("test_generate_bim_models")
            )

            runner = unittest.TextTestRunner(verbosity=1)
            result = runner.run(suite)

            passed = result.testsRun - len(result.failures) - len(result.errors)
            failed = len(result.failures) + len(result.errors)

            total_passed += passed
            total_failed += failed

            print(f"  Passed: {passed}")
            print(f"  Failed: {failed}")
            print(f"  Total: {result.testsRun}")

        except Exception as e:
            print(f"  Error running {category_name}: {e}")
            total_failed += 1

    print("\nOverall Results:")
    print(f"  Total Passed: {total_passed}")
    print(f"  Total Failed: {total_failed}")
    print(
        f"  Success Rate: {total_passed / (total_passed + total_failed) * 100:.1f}%"
        if (total_passed + total_failed) > 0
        else "N/A"
    )


def main():
    """Main function to run tests based on command line arguments."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--categories":
            run_test_categories()
        elif sys.argv[1] == "--specific" and len(sys.argv) > 2:
            test_name = sys.argv[2]
            success = run_specific_test(test_name)
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python run_bim_model_tests.py                    # Run all tests")
            print(
                "  python run_bim_model_tests.py --categories       # Run tests by category"
            )
            print(
                "  python run_bim_model_tests.py --specific <test>  # Run specific test"
            )
            print("  python run_bim_model_tests.py --help             # Show this help")
            return
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    else:
        # Run all tests
        total_tests, failed_tests = run_bim_model_tests()
        sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    main()
