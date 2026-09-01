#!/usr/bin/env python3
"""
Inspection tests for the configured Celery SQLite database.

These tests inspect the *live* SQLite database used by the Celery backend
(as resolved by :func:`src.database.get_celery_db_path`). They are only
meaningful for the SQLite backend and skip gracefully when the database file
does not yet exist (e.g. on a fresh checkout or when running with the Redis
backend). Deterministic schema/utility behaviour is covered separately in
``test_database.py``.
"""

import os
import sqlite3

import pytest

from src.database import get_celery_db_path


@pytest.fixture
def db_path():
    """Resolve the configured Celery SQLite database path."""
    return get_celery_db_path()


@pytest.fixture
def db_connection(db_path):
    """Open a connection to the live database, skipping if it does not exist."""
    if not os.path.exists(db_path):
        pytest.skip(f"Celery database file {db_path} does not exist")
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


def test_database_exists(db_path):
    """The configured database file exists and is non-empty."""
    if not os.path.exists(db_path):
        pytest.skip(f"Celery database file {db_path} does not exist")

    file_size = os.path.getsize(db_path)
    assert file_size > 0, "Database file should not be empty"


def test_database_tables_exist(db_connection):
    """The expected Celery/Kombu tables are present."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row[0] for row in cursor.fetchall()]

    required_tables = [
        "celery_taskmeta",
        "celery_tasksetmeta",
        "kombu_queue",
        "kombu_message",
    ]
    for table in required_tables:
        assert table in table_names, f"Required table {table} not found"


def test_celery_taskmeta_structure(db_connection):
    """The celery_taskmeta table exposes the expected columns."""
    cursor = db_connection.cursor()
    cursor.execute("PRAGMA table_info(celery_taskmeta)")
    column_names = [col[1] for col in cursor.fetchall()]

    required_columns = ["id", "task_id", "status", "result", "date_done"]
    for col in required_columns:
        assert col in column_names, f"Required column {col} not found"


def test_task_count_is_queryable(db_connection):
    """The task table can be queried for a (non-negative) task count."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
    total_tasks = cursor.fetchone()[0]
    assert total_tasks >= 0


def test_database_integrity(db_connection):
    """The SQLite integrity check reports no corruption."""
    cursor = db_connection.cursor()
    cursor.execute("PRAGMA integrity_check")
    integrity_result = cursor.fetchone()
    assert integrity_result[0] == "ok", "Database integrity check failed"
