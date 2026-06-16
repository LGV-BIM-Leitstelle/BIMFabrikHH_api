"""
Basic Celery worker tests.

Tests basic Celery functionality with a simple in-memory setup.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
"""

import pytest
from celery import Celery


# ============================================================================
# Test In-Memory Celery Setup
# ============================================================================


class TestCeleryBasics:
    """Test basic Celery functionality."""

    def test_create_celery_app(self):
        """Test creating a basic Celery app."""
        app = Celery("test", broker="memory://", backend="rpc://")
        assert app is not None
        assert app.main == "test"

    def test_define_simple_task(self):
        """Test defining a simple task."""
        app = Celery("test", broker="memory://", backend="cache+memory://")
        
        @app.task
        def add(x, y):
            return x + y
        
        assert hasattr(add, "delay")
        assert callable(add)

    def test_execute_simple_task_directly(self):
        """Test executing a task directly (without worker)."""
        app = Celery("test", broker="memory://", backend="cache+memory://")
        
        @app.task
        def multiply(x, y):
            return x * y
        
        # Execute directly (not via delay)
        result = multiply(3, 4)
        assert result == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
