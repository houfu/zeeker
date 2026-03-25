"""
Test .env file loading functionality in CLI commands.
"""

from unittest.mock import patch


class TestDotenvLoading:
    """Test that .env files are loaded by CLI commands."""

    @patch("zeeker.commands.helpers.load_dotenv")
    def test_build_command_calls_load_dotenv(self, mock_load_dotenv):
        """Test that build command calls load_dotenv()."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.build_database.return_value.errors = []
            mock_instance.build_database.return_value.warnings = []
            mock_instance.build_database.return_value.info = ["Test build info"]

            from click.testing import CliRunner

            from zeeker.cli import build

            runner = CliRunner()
            runner.invoke(build, [])

            mock_load_dotenv.assert_called_once()

    @patch("zeeker.commands.helpers.load_dotenv")
    def test_deploy_command_calls_load_dotenv(self, mock_load_dotenv):
        """Test that deploy command calls load_dotenv()."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.is_project_root.return_value = True

            mock_project = type("MockProject", (), {"database": "test.db"})()
            mock_instance.load_project.return_value = mock_project

            with patch("zeeker.core.deployer.ZeekerDeployer") as mock_deployer_class:
                mock_deployer_class.return_value.bucket_name = "test"

                from click.testing import CliRunner

                from zeeker.cli import deploy_database

                runner = CliRunner()
                runner.invoke(deploy_database, [])

                # load_dotenv called via create_deployer -> load_env
                assert mock_load_dotenv.called
