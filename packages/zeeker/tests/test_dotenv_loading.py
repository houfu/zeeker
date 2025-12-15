"""
Test .env file loading functionality in CLI commands.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv


class TestDotenvLoading:
    """Test that .env files are loaded by CLI commands."""

    def test_load_dotenv_import_works(self):
        """Test that python-dotenv can be imported successfully."""
        # If this test passes, it means python-dotenv is available
        from dotenv import load_dotenv

        assert callable(load_dotenv)

    def test_dotenv_loading_in_build_context(self):
        """Test that load_dotenv loads .env files from current directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("TEST_VAR=test_value\n")

            # Change to the directory with .env file
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Load the .env file manually to simulate what the CLI would do
                load_dotenv(dotenv_path=env_file)

                # Verify the environment variable is loaded
                assert os.getenv("TEST_VAR") == "test_value"

            finally:
                os.chdir(original_cwd)
                # Clean up environment
                if "TEST_VAR" in os.environ:
                    del os.environ["TEST_VAR"]

    def test_env_vars_available_after_load_dotenv(self):
        """Test that environment variables from .env are accessible."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as env_file:
            env_file.write("CLI_TEST_VAR=cli_test_value\n")
            env_file.write("ANOTHER_TEST_VAR=another_value\n")
            env_file_path = env_file.name

        try:
            # Load the specific .env file
            load_dotenv(env_file_path)

            # Check that variables are available
            assert os.getenv("CLI_TEST_VAR") == "cli_test_value"
            assert os.getenv("ANOTHER_TEST_VAR") == "another_value"

        finally:
            # Cleanup
            os.unlink(env_file_path)
            if "CLI_TEST_VAR" in os.environ:
                del os.environ["CLI_TEST_VAR"]
            if "ANOTHER_TEST_VAR" in os.environ:
                del os.environ["ANOTHER_TEST_VAR"]

    @patch("zeeker.cli.load_dotenv")
    def test_build_command_calls_load_dotenv(self, mock_load_dotenv):
        """Test that build command calls load_dotenv()."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_manager:
            # Mock the manager to avoid actual project operations
            mock_instance = mock_manager.return_value
            mock_instance.build_database.return_value.errors = []
            mock_instance.build_database.return_value.warnings = []
            mock_instance.build_database.return_value.info = ["Test build info"]

            # Import click's testing framework
            from click.testing import CliRunner

            from zeeker.cli import build

            runner = CliRunner()
            runner.invoke(build, [])

            # Verify load_dotenv was called
            mock_load_dotenv.assert_called_once()

    @patch("zeeker.cli.load_dotenv")
    def test_deploy_command_calls_load_dotenv(self, mock_load_dotenv):
        """Test that deploy command calls load_dotenv()."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_manager:
            # Mock the manager to return not a project root
            mock_instance = mock_manager.return_value
            mock_instance.is_project_root.return_value = False

            from click.testing import CliRunner

            from zeeker.cli import deploy_database

            runner = CliRunner()
            runner.invoke(deploy_database, [])

            # Verify load_dotenv was called even when not in project root
            mock_load_dotenv.assert_called_once()
