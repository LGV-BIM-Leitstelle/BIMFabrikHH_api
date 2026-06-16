"""
Test configuration settings import and validation.

Copyright (C) 2025 Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung
"""

import pytest

from src.api.config import api_settings


class TestConfigImport:
    """Test configuration settings are properly loaded."""

    def test_api_settings_loaded(self):
        """Test that api_settings is loaded."""
        assert api_settings is not None

    def test_api_settings_all_fields_populated(self):
        """Test that all required fields are populated."""
        for field in api_settings.model_fields:
            value = getattr(api_settings, field)
            assert value is not None, f"API setting '{field}' is None or missing"

    def test_api_settings_required_fields(self):
        """Test that critical fields exist."""
        assert hasattr(api_settings, "BASE_URL")
        assert hasattr(api_settings, "API_HOST")
        assert hasattr(api_settings, "API_PORT")
        assert hasattr(api_settings, "OUTPUT_FOLDER_PATH")

    def test_api_settings_url_formats(self):
        """Test that URL fields are properly formatted."""
        assert str(api_settings.BASE_URL).startswith("http")
        assert str(api_settings.URL_OUTPUT_HTTP).startswith("http://")
        assert str(api_settings.URL_OUTPUT_HTTPS).startswith("https://")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
