#!/usr/bin/env python3
"""
Database utilities for BIMFabrikHH API

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
BIM-Leitstelle, Ahmed Salem <ahmed.salem@gv.hamburg.de>
"""

import os
import shutil
import sqlite3
from typing import Any

from src.database import get_celery_db_path

# Resolved once at import time; tests may patch this module attribute.
CELERY_DB_PATH = get_celery_db_path()


def get_database_info() -> dict[str, Any]:
    """
    Get information about the Celery database.

    Returns:
        Dictionary containing database information including path, size, tables, and task count.
    """
    """Get information about the Celery database"""
    info = {
        "path": CELERY_DB_PATH,
        "exists": os.path.exists(CELERY_DB_PATH),
        "size": 0,
        "tables": [],
        "task_count": 0,
    }

    if info["exists"]:
        info["size"] = os.path.getsize(CELERY_DB_PATH)

        try:
            conn = sqlite3.connect(CELERY_DB_PATH)
            cursor = conn.cursor()

            # Get tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            info["tables"] = [row[0] for row in cursor.fetchall()]

            # Get task count
            if "celery_taskmeta" in info["tables"]:
                cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
                info["task_count"] = cursor.fetchone()[0]

            conn.close()
        except Exception as e:
            info["error"] = str(e)

    return info


def backup_database(backup_path: str | None = None) -> str:
    """
    Create a backup of the Celery database.

    Args:
        backup_path: Optional path for the backup file. If None, creates a timestamped backup.

    Returns:
        Path to the created backup file.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    """Create a backup of the Celery database"""
    if not os.path.exists(CELERY_DB_PATH):
        raise FileNotFoundError(f"Database not found at {CELERY_DB_PATH}")

    if backup_path is None:
        # Create backup in the same directory as the database with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_dir = os.path.dirname(CELERY_DB_PATH)
        db_name = os.path.basename(CELERY_DB_PATH)
        backup_name = db_name.replace(".sqlite", f"_backup_{timestamp}.sqlite")
        backup_path = os.path.join(db_dir, backup_name)

    shutil.copy2(CELERY_DB_PATH, backup_path)
    print(f"Database backed up to: {backup_path}")
    return backup_path


def cleanup_old_database(max_rows: int = 50) -> bool:
    """
    Clean up old database rows when they exceed the specified limit.

    Args:
        max_rows: Maximum number of rows to keep in the database.

    Returns:
        True if cleanup was successful, False otherwise.
    """
    """Clean up old database rows when they exceed the specified limit"""
    if not os.path.exists(CELERY_DB_PATH):
        print("Database not found, nothing to clean")
        return True

    try:
        conn = sqlite3.connect(CELERY_DB_PATH)
        cursor = conn.cursor()

        # Check current row count
        cursor.execute("SELECT COUNT(*) FROM celery_taskmeta")
        current_count = cursor.fetchone()[0]

        print(f"Current task count: {current_count}")

        if current_count > max_rows:
            # Get the IDs of the oldest rows to keep only the most recent ones
            cursor.execute(
                """
                SELECT id FROM celery_taskmeta 
                ORDER BY date_done DESC 
                LIMIT ?
            """,
                (max_rows,),
            )

            recent_ids = [row[0] for row in cursor.fetchall()]

            if recent_ids:
                # Delete all rows except the most recent ones
                placeholders = ",".join(["?" for _ in recent_ids])
                cursor.execute(
                    f"""
                    DELETE FROM celery_taskmeta 
                    WHERE id NOT IN ({placeholders})
                """,
                    recent_ids,
                )

                deleted_count = current_count - max_rows
                print(f"Cleaned up {deleted_count} old task records")
                print(f"Kept {max_rows} most recent tasks")
            else:
                print("No recent tasks found to keep")
        else:
            print(
                f"Task count ({current_count}) is within limit ({max_rows}), no cleanup needed"
            )

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error cleaning up database: {e}")
        return False


if __name__ == "__main__":
    # Print database information
    info = get_database_info()
    print("=== Celery Database Information ===")
    print(f"Path: {info['path']}")
    print(f"Exists: {info['exists']}")
    print(f"Size: {info['size']} bytes")
    print(f"Tables: {info['tables']}")
    print(f"Task count: {info['task_count']}")

    if "error" in info:
        print(f"Error: {info['error']}")

    # create a backup
    print("\n=== Database backup ===")
    backup_database()

    # Run cleanup
    print("\n=== Database Cleanup ===")
    cleanup_old_database()
