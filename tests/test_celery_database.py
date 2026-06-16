#!/usr/bin/env python3
"""
Test script to inspect Celery database contents
"""

import os
import unittest

from src.database import CELERY_DB_PATH


class TestCeleryDatabase(unittest.TestCase):
    """Test cases for Celery database inspection"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_path = CELERY_DB_PATH

    def test_database_exists(self):
        """Test that the Celery database file exists"""
        print(f"Checking if database exists: {self.db_path}")
        self.assertTrue(
            os.path.exists(self.db_path), f"Database file {self.db_path} does not exist"
        )

        # Check file size
        file_size = os.path.getsize(self.db_path)
        print(f"Database file size: {file_size} bytes")
        self.assertGreater(file_size, 0, "Database file should not be empty")

    def test_database_tables_exist(self):
        """Test that required database tables exist"""
        if not os.path.exists(self.db_path):
            self.skipTest(f"Database file {self.db_path} does not exist")

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]

            print(f"Tables in database: {table_names}")

            # Check for required tables
            required_tables = [
                "celery_taskmeta",
                "celery_tasksetmeta",
                "kombu_queue",
                "kombu_message",
            ]
            for table in required_tables:
                self.assertIn(table, table_names, f"Required table {table} not found")

            conn.close()

        except Exception as e:
            self.fail(f"Error checking database tables: {e}")

    def test_celery_taskmeta_structure(self):
        """Test the structure of the celery_taskmeta table"""
        if not os.path.exists(self.db_path):
            self.skipTest(f"Database file {self.db_path} does not exist")

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get table schema
            cursor.execute("PRAGMA table_info(celery_taskmeta)")
            columns = cursor.fetchall()

            print("celery_taskmeta table columns:")
            column_names = []
            for col in columns:
                column_name = col[1]
                column_type = col[2]
                column_names.append(column_name)
                print(f"  {column_name} ({column_type})")

            # Check for required columns
            required_columns = ["id", "task_id", "status", "result", "date_done"]
            for col in required_columns:
                self.assertIn(col, column_names, f"Required column {col} not found")

            conn.close()

        except Exception as e:
            self.fail(f"Error checking table structure: {e}")

    def test_task_count_and_status(self):
        """Test task count and status information"""
        if not os.path.exists(self.db_path):
            self.skipTest(f"Database file {self.db_path} does not exist")

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get total task count
            cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
            total_tasks = cursor.fetchone()[0]
            print(f"Total tasks in database: {total_tasks}")

            # Get tasks by status
            cursor.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM celery_taskmeta 
                GROUP BY status 
                ORDER BY count DESC
            """
            )
            status_counts = cursor.fetchall()

            print("Tasks by status:")
            for status, count in status_counts:
                print(f"  {status}: {count}")

            # Get recent tasks
            if total_tasks > 0:
                cursor.execute(
                    """
                    SELECT task_id, status, date_done 
                    FROM celery_taskmeta 
                    ORDER BY date_done DESC 
                    LIMIT 5
                """
                )
                recent_tasks = cursor.fetchall()

                print("Recent tasks:")
                for task_id, status, date_done in recent_tasks:
                    print(f"  {task_id}: {status} at {date_done}")

            conn.close()

        except Exception as e:
            self.fail(f"Error checking task count and status: {e}")

    def test_database_integrity(self):
        """Test database integrity"""
        if not os.path.exists(self.db_path):
            self.skipTest(f"Database file {self.db_path} does not exist")

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()

            print(f"Database integrity check: {integrity_result[0]}")
            self.assertEqual(
                integrity_result[0], "ok", "Database integrity check failed"
            )

            conn.close()

        except Exception as e:
            self.fail(f"Error checking database integrity: {e}")


def inspect_celery_db():
    """Function to inspect Celery database contents"""
    print("=== Celery Database Inspection ===")

    test_instance = TestCeleryDatabase()
    test_instance.setUp()

    # Run all inspection tests
    test_instance.test_database_exists()
    test_instance.test_database_tables_exist()
    test_instance.test_celery_taskmeta_structure()
    test_instance.test_task_count_and_status()
    test_instance.test_database_integrity()

    print("\n=== Database Inspection Complete ===")


if __name__ == "__main__":
    # Run as standalone inspection
    inspect_celery_db()
