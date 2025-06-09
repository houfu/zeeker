"""
Pytest configuration and shared fixtures.
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_database_structure(temp_dir):
    """Create a sample database customization structure."""
    # Create directory structure
    templates_dir = temp_dir / "templates"
    static_dir = temp_dir / "static"
    images_dir = static_dir / "images"

    templates_dir.mkdir()
    static_dir.mkdir()
    images_dir.mkdir()

    # Create template files
    (templates_dir / "database-testdb.html").write_text(
        """
    {% extends "default:database.html" %}
    {% block content %}
    <h1>Test Database</h1>
    {{ super() }}
    {% endblock %}
    """
    )

    (templates_dir / "custom-header.html").write_text(
        """
    <header class="custom-header">
        <h1>Custom Header</h1>
    </header>
    """
    )

    # Create static files
    (static_dir / "custom.css").write_text(
        """
    :root {
        --primary-color: #3498db;
        --accent-color: #e74c3c;
    }

    .custom-header {
        background-color: var(--primary-color);
        color: white;
        padding: 1rem;
    }
    """
    )

    (static_dir / "custom.js").write_text(
        """
    document.addEventListener('DOMContentLoaded', function() {
        console.log('Custom JS loaded for testdb');

        // Add custom functionality
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            table.classList.add('enhanced-table');
        });
    });
    """
    )

    # Create metadata file
    metadata = {
        "title": "Test Database",
        "description": "A sample test database for validation",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/cc-by-4.0/",
        "extra_css_urls": ["/static/databases/testdb/custom.css"],
        "extra_js_urls": ["/static/databases/testdb/custom.js"],
        "databases": {
            "testdb": {
                "title": "Test Database",
                "description": "A sample test database for validation",
            }
        },
    }

    import json

    (temp_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return temp_dir


@pytest.fixture
def invalid_database_structure(temp_dir):
    """Create an invalid database customization structure for testing errors."""
    # Create directory structure with issues
    templates_dir = temp_dir / "templates"
    static_dir = temp_dir / "static"
    unexpected_dir = temp_dir / "unexpected"

    templates_dir.mkdir()
    static_dir.mkdir()
    unexpected_dir.mkdir()  # This should generate a warning

    # Create banned template (should generate error)
    (templates_dir / "database.html").write_text("<h1>Banned Template</h1>")

    # Create template with poor naming
    (templates_dir / "random.html").write_text("<h1>Random Template</h1>")

    # Create invalid metadata
    (temp_dir / "metadata.json").write_text("{ invalid json content")

    return temp_dir


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing deployment functionality."""
    client = MagicMock()

    # Mock successful upload
    client.upload_file.return_value = None

    # Mock list objects response
    client.list_objects_v2.return_value = {
        "CommonPrefixes": [
            {"Prefix": "assets/databases/db1/"},
            {"Prefix": "assets/databases/db2/"},
            {"Prefix": "assets/databases/test_database/"},
        ]
    }

    return client


@pytest.fixture
def mock_boto3_session(mock_s3_client):
    """Mock boto3 session that returns our mock S3 client."""
    session = MagicMock()
    session.client.return_value = mock_s3_client
    return session


# Pytest markers for test categorization
pytestmark = pytest.mark.unit


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "cli: CLI command tests")
    config.addinivalue_line("markers", "aws: Tests requiring AWS credentials")
    config.addinivalue_line("markers", "slow: Slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add unit marker to all tests by default
        if not any(marker.name in ["integration", "cli", "aws"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)

        # Add cli marker to CLI tests
        if "cli" in item.name.lower() or "command" in item.name.lower():
            item.add_marker(pytest.mark.cli)

        # Add aws marker to AWS-related tests
        if "s3" in item.name.lower() or "deploy" in item.name.lower() or "aws" in item.name.lower():
            item.add_marker(pytest.mark.aws)
