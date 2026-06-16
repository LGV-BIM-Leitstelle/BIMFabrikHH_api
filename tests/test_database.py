#!/usr/bin/env python3
"""
Database tests for BIMFabrikHH API.

Tests core database functionality:
- Database configuration
- Basic operations (store, retrieve, update)
- Database utilities (backup, cleanup)
- Query operations

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
"""

import os
import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from src.database import (
    CELERY_BACKEND_URL,
    CELERY_BROKER_URL,
    CELERY_DB_PATH,
    DATABASE_DIR,
)
from src.database.db_utils import (
    backup_database,
    cleanup_old_database,
    get_database_info,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    db_path = tmp_path / "test_celerydb.sqlite"
    yield str(db_path)


@pytest.fixture
def temp_db_with_schema(temp_db_path):
    """Create a temporary database with Celery tables."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Create main Celery table
    cursor.execute(
        """
        CREATE TABLE celery_taskmeta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id VARCHAR(155) UNIQUE,
            status VARCHAR(50),
            result BLOB,
            date_done TIMESTAMP,
            traceback TEXT
        )
    """
    )

    conn.commit()
    conn.close()
    yield temp_db_path


@pytest.fixture
def temp_db_with_tasks(temp_db_with_schema):
    """Create a database with sample tasks."""
    conn = sqlite3.connect(temp_db_with_schema)
    cursor = conn.cursor()

    # Insert 5 sample tasks
    tasks = [
        ("task-1", "SUCCESS", '{"result": "output1.ifc"}', "2025-01-01 10:00:00", None),
        ("task-2", "SUCCESS", '{"result": "output2.ifc"}', "2025-01-01 11:00:00", None),
        ("task-3", "PENDING", None, "2025-01-01 12:00:00", None),
        ("task-4", "FAILURE", '{"error": "test"}', "2025-01-01 13:00:00", "Error..."),
        ("task-5", "SUCCESS", '{"result": "output3.ifc"}', "2025-01-01 14:00:00", None),
    ]

    cursor.executemany(
        "INSERT INTO celery_taskmeta (task_id, status, result, date_done, traceback) VALUES (?, ?, ?, ?, ?)",
        tasks,
    )

    conn.commit()
    conn.close()
    yield temp_db_with_schema


# ============================================================================
# Test Database Configuration
# ============================================================================


class TestDatabaseConfiguration:
    """Test basic database configuration."""

    def test_database_paths_are_set(self):
        """Test that database paths are configured."""
        assert DATABASE_DIR is not None
        assert CELERY_DB_PATH is not None
        assert CELERY_DB_PATH.endswith(".sqlite")

    def test_connection_urls_format(self):
        """Test that connection URLs have correct format."""
        assert CELERY_BROKER_URL.startswith("sqla+sqlite:///")
        assert CELERY_BACKEND_URL.startswith("db+sqlite:///")


# ============================================================================
# Test Basic Database Operations
# ============================================================================


class TestBasicOperations:
    """Test basic database operations."""

    def test_create_connection(self, temp_db_path):
        """Test creating a database connection."""
        conn = sqlite3.connect(temp_db_path)
        assert conn is not None
        
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()
        assert version is not None
        
        conn.close()

    def test_insert_and_retrieve_task(self, temp_db_with_schema):
        """Test inserting and retrieving a task."""
        conn = sqlite3.connect(temp_db_with_schema)
        cursor = conn.cursor()

        # Insert task
        task_id = "test-task-123"
        cursor.execute(
            "INSERT INTO celery_taskmeta (task_id, status, result) VALUES (?, ?, ?)",
            (task_id, "SUCCESS", '{"url": "http://example.com/output.ifc"}'),
        )
        conn.commit()

        # Retrieve task
        cursor.execute("SELECT status, result FROM celery_taskmeta WHERE task_id = ?", (task_id,))
        status, result = cursor.fetchone()

        assert status == "SUCCESS"
        assert "output.ifc" in result

        conn.close()

    def test_update_task_status(self, temp_db_with_tasks):
        """Test updating a task's status."""
        conn = sqlite3.connect(temp_db_with_tasks)
        cursor = conn.cursor()

        # Update PENDING task to SUCCESS
        cursor.execute(
            "UPDATE celery_taskmeta SET status = ?, result = ? WHERE task_id = ?",
            ("SUCCESS", '{"result": "completed.ifc"}', "task-3"),
        )
        conn.commit()

        # Verify update
        cursor.execute("SELECT status FROM celery_taskmeta WHERE task_id = ?", ("task-3",))
        status = cursor.fetchone()[0]
        assert status == "SUCCESS"

        conn.close()

    def test_task_id_unique_constraint(self, temp_db_with_schema):
        """Test that duplicate task_id raises error."""
        conn = sqlite3.connect(temp_db_with_schema)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO celery_taskmeta (task_id, status) VALUES (?, ?)",
            ("duplicate-task", "SUCCESS"),
        )

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO celery_taskmeta (task_id, status) VALUES (?, ?)",
                ("duplicate-task", "PENDING"),
            )

        conn.close()


# ============================================================================
# Test Database Queries
# ============================================================================


class TestDatabaseQueries:
    """Test common database queries."""

    def test_count_all_tasks(self, temp_db_with_tasks):
        """Test counting total tasks."""
        conn = sqlite3.connect(temp_db_with_tasks)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
        count = cursor.fetchone()[0]

        assert count == 5  # We have 5 sample tasks

        conn.close()

    def test_count_by_status(self, temp_db_with_tasks):
        """Test counting tasks by status."""
        conn = sqlite3.connect(temp_db_with_tasks)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM celery_taskmeta WHERE status = 'SUCCESS'")
        success_count = cursor.fetchone()[0]

        assert success_count == 3

        conn.close()

    def test_get_recent_tasks(self, temp_db_with_tasks):
        """Test retrieving most recent tasks."""
        conn = sqlite3.connect(temp_db_with_tasks)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT task_id FROM celery_taskmeta 
            ORDER BY date_done DESC 
            LIMIT 2
        """
        )
        recent = cursor.fetchall()

        assert len(recent) == 2
        assert recent[0][0] == "task-5"  # Most recent

        conn.close()


# ============================================================================
# Test Database Utilities
# ============================================================================


class TestDatabaseUtilities:
    """Test database utility functions."""

    def test_get_database_info(self, temp_db_with_tasks):
        """Test getting database information."""
        with patch("src.database.db_utils.CELERY_DB_PATH", temp_db_with_tasks):
            info = get_database_info()

            assert info["exists"] is True
            assert info["size"] > 0
            assert "celery_taskmeta" in info["tables"]
            assert info["task_count"] == 5

    def test_backup_database(self, temp_db_with_tasks, tmp_path):
        """Test creating a database backup."""
        backup_path = tmp_path / "backup.sqlite"

        with patch("src.database.db_utils.CELERY_DB_PATH", temp_db_with_tasks):
            result = backup_database(str(backup_path))

            assert os.path.exists(result)
            assert result == str(backup_path)
            
            # Verify backup has same data
            conn = sqlite3.connect(result)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
            count = cursor.fetchone()[0]
            assert count == 5
            conn.close()

    def test_cleanup_old_database(self, temp_db_with_tasks):
        """Test cleaning up old database entries."""
        with patch("src.database.db_utils.CELERY_DB_PATH", temp_db_with_tasks):
            # Keep only 2 most recent tasks
            result = cleanup_old_database(max_rows=2)
            assert result is True

            # Verify only 2 tasks remain
            conn = sqlite3.connect(temp_db_with_tasks)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
            count = cursor.fetchone()[0]
            assert count == 2

            # Verify they are the most recent
            cursor.execute("SELECT task_id FROM celery_taskmeta ORDER BY date_done DESC")
            remaining = [row[0] for row in cursor.fetchall()]
            assert "task-5" in remaining
            assert "task-4" in remaining

            conn.close()

    def test_cleanup_no_action_needed(self, temp_db_with_tasks):
        """Test cleanup when below limit."""
        with patch("src.database.db_utils.CELERY_DB_PATH", temp_db_with_tasks):
            # Keep 10 tasks (we only have 5)
            result = cleanup_old_database(max_rows=10)
            assert result is True

            # Verify all 5 tasks still exist
            conn = sqlite3.connect(temp_db_with_tasks)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
            count = cursor.fetchone()[0]
            assert count == 5

            conn.close()


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in database operations."""

    def test_query_nonexistent_table(self, temp_db_with_schema):
        """Test querying a table that doesn't exist."""
        conn = sqlite3.connect(temp_db_with_schema)
        cursor = conn.cursor()

        with pytest.raises(sqlite3.OperationalError):
            cursor.execute("SELECT * FROM nonexistent_table")

        conn.close()

    def test_connection_after_close(self, temp_db_path):
        """Test operations fail after closing connection."""
        conn = sqlite3.connect(temp_db_path)
        conn.close()

        with pytest.raises(sqlite3.ProgrammingError):
            cursor = conn.cursor()
            cursor.execute("SELECT 1")


# ============================================================================
# Test Database Integrity
# ============================================================================


class TestDatabaseIntegrity:
    """Test database integrity."""

    def test_integrity_check(self, temp_db_with_schema):
        """Test database passes integrity check."""
        conn = sqlite3.connect(temp_db_with_schema)
        cursor = conn.cursor()

        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]

        assert result == "ok"

        conn.close()

    def test_vacuum_reduces_size(self, temp_db_with_tasks):
        """Test VACUUM operation."""
        initial_size = os.path.getsize(temp_db_with_tasks)

        conn = sqlite3.connect(temp_db_with_tasks)
        cursor = conn.cursor()

        # Delete some tasks
        cursor.execute("DELETE FROM celery_taskmeta WHERE status = 'SUCCESS'")
        conn.commit()

        # VACUUM to reclaim space
        cursor.execute("VACUUM")
        conn.close()

        final_size = os.path.getsize(temp_db_with_tasks)
        
        # Size should not increase
        assert final_size <= initial_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
