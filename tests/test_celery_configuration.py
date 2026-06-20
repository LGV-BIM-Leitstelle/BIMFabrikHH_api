"""
Tests for Celery app configuration.
"""

from src.api.ogc_api.services.generate_bim_modells import app


class TestCeleryAppConfiguration:
    """Tests for Celery app configuration."""

    def test_celery_app_name(self):
        """Test that Celery app has correct name."""
        assert app.main == "hamburg"

    def test_celery_app_broker_configuration(self):
        """Test that Celery app has broker configuration."""
        assert app.conf.get("broker_url") is not None

    def test_celery_app_backend_configuration(self):
        """Test that Celery app has result backend configuration."""
        assert app.conf.get("result_backend") is not None
