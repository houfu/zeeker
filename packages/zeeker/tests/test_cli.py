"""Comprehensive tests for Zeeker CLI commands using Click's CliRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zeeker.cli import cli
from zeeker.core.types import (
    BuildReport,
    ResourceOutcome,
    ValidationResult,
    ZeekerSchemaConflictError,
)


class TestCLIInit:
    """Test 'zeeker init' command."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    def test_init_basic_project(self, runner):
        """Test basic project initialization."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "test_project"])

            assert result.exit_code == 0
            assert "✅ Initialized Zeeker project 'test_project'" in result.output
            assert Path("test_project").exists()
            assert Path("test_project/zeeker.toml").exists()
            assert Path("test_project/pyproject.toml").exists()
            assert Path("test_project/resources").exists()

    def test_init_with_custom_path(self, runner):
        """Test project initialization with custom path."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "my_project", "--path", "custom_dir"])

            assert result.exit_code == 0
            assert Path("custom_dir").exists()
            assert Path("custom_dir/zeeker.toml").exists()

    def test_init_project_already_exists(self, runner):
        """Test initialization when project directory already exists."""
        with runner.isolated_filesystem():
            Path("existing_project").mkdir()

            with patch("zeeker.core.project.ZeekerProjectManager.init_project") as mock_init:
                mock_result = ValidationResult(is_valid=False)
                mock_result.errors.append("Project directory already exists")
                mock_init.return_value = mock_result

                result = runner.invoke(cli, ["init", "existing_project"])

                assert result.exit_code == 0  # CLI doesn't exit with error, just prints
                assert "❌ Project directory already exists" in result.output

    def test_init_success_messages(self, runner):
        """Test that success messages are displayed correctly."""
        with runner.isolated_filesystem():
            with patch("zeeker.core.project.ZeekerProjectManager.init_project") as mock_init:
                mock_result = ValidationResult(is_valid=True)
                mock_result.info.extend(
                    [
                        "Created: zeeker.toml",
                        "Created: pyproject.toml",
                        "Created: resources/",
                        "Created: .gitignore",
                    ]
                )
                mock_init.return_value = mock_result

                result = runner.invoke(cli, ["init", "test_project"])

                assert result.exit_code == 0
                for info in mock_result.info:
                    assert f"✅ {info}" in result.output


class TestCLIAdd:
    """Test 'zeeker add' command."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    @pytest.fixture
    def mock_manager(self):
        """Mock ZeekerProjectManager."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_add_basic_resource(self, runner, mock_manager):
        """Test adding a basic resource."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.info.append("Created: resources/users.py")
        mock_manager.add_resource.return_value = mock_result

        result = runner.invoke(cli, ["add", "users"])

        assert result.exit_code == 0
        assert "✅ Created: resources/users.py" in result.output
        mock_manager.add_resource.assert_called_once_with("users", None)

    def test_add_resource_with_all_options(self, runner, mock_manager):
        """Test adding resource with all options."""
        mock_result = ValidationResult(is_valid=True)
        mock_manager.add_resource.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "add",
                "api_data",
                "--description",
                "API data source",
                "--facets",
                "category",
                "--facets",
                "status",
                "--sort",
                "created_date desc",
                "--size",
                "25",
                "--fragments",
                "--async",
            ],
        )

        assert result.exit_code == 0
        mock_manager.add_resource.assert_called_once_with(
            "api_data",
            "API data source",
            facets=["category", "status"],
            sort="created_date desc",
            size=25,
            fragments=True,
            is_async=True,
        )

    def test_add_resource_error(self, runner, mock_manager):
        """Test adding resource with error."""
        mock_result = ValidationResult(is_valid=False)
        mock_result.errors.append("Resource 'users' already exists")
        mock_manager.add_resource.return_value = mock_result

        result = runner.invoke(cli, ["add", "users"])

        assert result.exit_code == 0  # CLI doesn't exit on errors, just displays them
        assert "❌ Resource 'users' already exists" in result.output

    def test_add_displays_next_steps(self, runner, mock_manager):
        """Test that next steps are displayed after successful add."""
        mock_result = ValidationResult(is_valid=True)
        mock_manager.add_resource.return_value = mock_result

        result = runner.invoke(cli, ["add", "test_resource"])

        assert result.exit_code == 0
        assert "Next steps:" in result.output
        assert "Edit resources/test_resource.py" in result.output
        assert "Implement the fetch_data() function" in result.output
        assert "zeeker build" in result.output


class TestCLIBuild:
    """Test 'zeeker build' command."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    @pytest.fixture
    def mock_manager(self):
        """Mock ZeekerProjectManager."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @staticmethod
    def _assert_build_kwargs(mock_manager, **expected):
        """Assert build_database was called with the expected kwargs (ignoring the
        progress_callback, which is a closure the CLI constructs internally)."""
        assert mock_manager.build_database.call_count == 1
        kwargs = mock_manager.build_database.call_args.kwargs
        for key, value in expected.items():
            assert kwargs[key] == value, f"{key}: expected {value!r}, got {kwargs[key]!r}"

    def test_build_successful(self, runner, mock_manager):
        """Test successful database build."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=150)],
            total_duration_s=0.1,
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 0
        # Plain-mode renderer emits a SUMMARY line
        assert "SUMMARY: 1 succeeded" in result.output
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=False,
            sync_from_s3=False,
            resources=None,
            setup_fts=False,
        )

    def test_build_with_force_schema_reset(self, runner, mock_manager):
        """Test build with force schema reset flag."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport()
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--force-schema-reset"])

        assert result.exit_code == 0
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=True,
            sync_from_s3=False,
            resources=None,
            setup_fts=False,
        )

    def test_build_with_s3_sync(self, runner, mock_manager):
        """Test build with S3 sync flag."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport()
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--sync-from-s3"])

        assert result.exit_code == 0
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=False,
            sync_from_s3=True,
            resources=None,
            setup_fts=False,
        )

    def test_build_with_both_flags(self, runner, mock_manager):
        """Test build with both flags."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport()
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--force-schema-reset", "--sync-from-s3"])

        assert result.exit_code == 0
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=True,
            sync_from_s3=True,
            resources=None,
            setup_fts=False,
        )

    def test_build_with_setup_fts(self, runner, mock_manager):
        """Test build with setup-fts flag."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport()
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--setup-fts"])

        assert result.exit_code == 0
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=False,
            sync_from_s3=False,
            resources=None,
            setup_fts=True,
        )

    def test_build_schema_conflict_error(self, runner, mock_manager):
        """Schema conflict is a fatal error (exit code 2) routed through the renderer."""
        mock_manager.build_database.side_effect = ZeekerSchemaConflictError(
            "users",
            {"id": "INTEGER", "name": "TEXT"},
            {"id": "INTEGER", "name": "TEXT", "email": "TEXT"},
        )

        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 2
        # Plain-mode renderer emits FATAL: prefix with the conflict message
        assert "FATAL:" in result.output
        assert "users" in result.output

    def test_build_general_error(self, runner, mock_manager):
        """A ValidationResult with errors but no report is treated as fatal."""
        mock_result = ValidationResult(is_valid=False)
        mock_result.errors.append("Database file is locked")
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 2
        assert "FATAL:" in result.output
        assert "Database file is locked" in result.output

    def test_build_displays_summary(self, runner, mock_manager):
        """Build completion shows the structured SUMMARY line."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(total_duration_s=0.0)
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 0
        assert "SUMMARY:" in result.output

    def test_build_with_specific_resources(self, runner, mock_manager):
        """Test build with specific resources."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=150)]
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "users", "posts"])

        assert result.exit_code == 0
        assert "Building specific resources: users, posts" in result.output
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=False,
            sync_from_s3=False,
            resources=["users", "posts"],
            setup_fts=False,
        )

    def test_build_with_single_resource(self, runner, mock_manager):
        """Test build with single resource."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=150)]
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "users"])

        assert result.exit_code == 0
        assert "Building specific resources: users" in result.output
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=False,
            sync_from_s3=False,
            resources=["users"],
            setup_fts=False,
        )

    def test_build_with_invalid_resources(self, runner, mock_manager):
        """Unknown resources are pre-flight errors and exit as fatal (code 2)."""
        mock_result = ValidationResult(is_valid=False)
        mock_result.errors.extend(
            ["Unknown resources: invalid_resource", "Available resources: users, posts"]
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "users", "invalid_resource"])

        assert result.exit_code == 2
        assert "Unknown resources: invalid_resource" in result.output

    def test_build_resources_with_options(self, runner, mock_manager):
        """Test build with resources and options combined."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=150)]
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--force-schema-reset", "users", "posts"])

        assert result.exit_code == 0
        assert "Building specific resources: users, posts" in result.output
        self._assert_build_kwargs(
            mock_manager,
            force_schema_reset=True,
            sync_from_s3=False,
            resources=["users", "posts"],
            setup_fts=False,
        )

    def test_build_json_output(self, runner, mock_manager):
        """--json emits a single structured payload with fixed schema."""
        import json as _json

        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=42, duration_s=0.5)],
            total_duration_s=0.7,
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--json"])

        assert result.exit_code == 0
        payload = _json.loads(result.output)
        assert payload["status"] == "success"
        assert payload["resources"][0]["name"] == "users"
        assert payload["resources"][0]["records"] == 42

    def test_build_fail_on_empty_exits_one(self, runner, mock_manager):
        """--fail-on-empty turns a skipped-only build into exit 1."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="skipped", records=0)],
            total_duration_s=0.1,
        )
        mock_manager.build_database.return_value = mock_result

        # Without the flag, skipped is OK
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 0

        # With the flag, skipped is a failure
        mock_manager.build_database.reset_mock()
        mock_manager.build_database.return_value = mock_result
        result = runner.invoke(cli, ["build", "--fail-on-empty"])
        assert result.exit_code == 1

    def test_build_progress_file_written(self, runner, mock_manager, tmp_path):
        """--progress-file writes a JSON BuildReport snapshot to the given path."""
        import json as _json

        progress_path = tmp_path / "progress.json"

        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=5)],
            total_duration_s=0.1,
        )
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--progress-file", str(progress_path)])

        assert result.exit_code == 0
        assert progress_path.exists()
        payload = _json.loads(progress_path.read_text())
        assert payload["status"] == "success"
        assert payload["resources"][0]["name"] == "users"

    def test_build_parallel_flag_forwarded(self, runner, mock_manager):
        """--parallel N reaches the manager as max_parallel."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(total_duration_s=0.1)
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--parallel", "4"])
        assert result.exit_code == 0
        self._assert_build_kwargs(mock_manager, max_parallel=4)

    def test_build_post_hook_success_exits_zero(self, runner, mock_manager, tmp_path):
        """--post-hook runs after a successful build; zero exit keeps code 0."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=1)],
            total_duration_s=0.1,
        )
        mock_manager.build_database.return_value = mock_result
        mock_project = MagicMock()
        mock_project.database = "my.db"
        mock_manager.load_project.return_value = mock_project
        mock_manager.project_path = tmp_path

        result = runner.invoke(cli, ["build", "--post-hook", "exit 0"])
        assert result.exit_code == 0

    def test_build_post_hook_nonzero_exits_one(self, runner, mock_manager, tmp_path):
        """--post-hook non-zero exit propagates to exit code 1."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(
            resources=[ResourceOutcome(name="users", status="success", records=1)],
            total_duration_s=0.1,
        )
        mock_manager.build_database.return_value = mock_result
        mock_project = MagicMock()
        mock_project.database = "my.db"
        mock_manager.load_project.return_value = mock_project
        mock_manager.project_path = tmp_path

        result = runner.invoke(cli, ["build", "--post-hook", "exit 5"])
        assert result.exit_code == 1

    def test_build_force_sync_flag_forwarded(self, runner, mock_manager):
        """--force-sync reaches the manager."""
        mock_result = ValidationResult(is_valid=True)
        mock_result.report = BuildReport(total_duration_s=0.0)
        mock_manager.build_database.return_value = mock_result

        result = runner.invoke(cli, ["build", "--sync-from-s3", "--force-sync"])
        assert result.exit_code == 0
        self._assert_build_kwargs(mock_manager, force_sync=True, sync_from_s3=True)


class TestCLIDeploy:
    """Test 'zeeker deploy' command."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    @pytest.fixture
    def mock_manager(self):
        """Mock ZeekerProjectManager."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_deployer(self):
        """Mock ZeekerDeployer."""
        with patch("zeeker.core.deployer.ZeekerDeployer") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    def test_deploy_not_in_project(self, runner, mock_manager):
        """Deploy outside a project is a configuration/fatal error (exit 2)."""
        mock_manager.is_project_root.return_value = False

        result = runner.invoke(cli, ["deploy"])

        assert result.exit_code == 2
        assert "❌ Not in a Zeeker project directory" in result.output

    def test_deploy_successful(self, runner, mock_manager, mock_deployer):
        """Test successful deployment."""
        mock_manager.is_project_root.return_value = True

        # Mock project loading
        mock_project = MagicMock()
        mock_project.database = "myproject.db"
        mock_manager.load_project.return_value = mock_project
        mock_manager.project_path = Path("/tmp/test")

        # Mock database file exists
        with patch("pathlib.Path.exists", return_value=True):
            # Mock upload result
            mock_result = ValidationResult(is_valid=True)
            mock_result.info.append("Uploaded: myproject.db to s3://bucket/latest/")
            mock_deployer.upload_database.return_value = mock_result
            mock_deployer.bucket_name = "test-bucket"

            result = runner.invoke(cli, ["deploy"])

            assert result.exit_code == 0
            assert "✅ Uploaded: myproject.db to s3://bucket/latest/" in result.output
            assert "Database deployed successfully!" in result.output

    def test_deploy_dry_run(self, runner, mock_manager, mock_deployer):
        """Test deployment in dry run mode."""
        mock_manager.is_project_root.return_value = True

        # Mock project loading
        mock_project = MagicMock()
        mock_project.database = "myproject.db"
        mock_manager.load_project.return_value = mock_project
        mock_manager.project_path = Path("/tmp/test")

        # Mock database file exists
        with patch("pathlib.Path.exists", return_value=True):
            # Mock upload result for dry run
            mock_result = ValidationResult(is_valid=True)
            mock_result.info.append("Would upload: myproject.db to s3://bucket/latest/")
            mock_deployer.upload_database.return_value = mock_result

            result = runner.invoke(cli, ["deploy", "--dry-run"])

            assert result.exit_code == 0
            assert "Would upload" in result.output

    def test_deploy_error(self, runner, mock_manager, mock_deployer):
        """Missing database file is a setup error (exit 2)."""
        mock_manager.is_project_root.return_value = True

        # Mock project loading
        mock_project = MagicMock()
        mock_project.database = "nonexistent.db"
        mock_manager.load_project.return_value = mock_project
        mock_manager.project_path = Path("/tmp/test")

        # Mock database file doesn't exist
        with patch("pathlib.Path.exists", return_value=False):
            result = runner.invoke(cli, ["deploy"])

            assert result.exit_code == 2
            assert "❌ Database not found: nonexistent.db" in result.output
            assert "Run 'zeeker build' first" in result.output


# Assets commands have complex implementation details that need more investigation
# Commenting out for now to get core CLI tests passing

# class TestCLIAssetsGenerate:
#     """Test 'zeeker assets generate' command."""
#     # TODO: Implement after understanding exact interface

# class TestCLIAssetsValidate:
#     """Test 'zeeker assets validate' command."""
#     # TODO: Implement after understanding exact interface

# class TestCLIAssetsDeploy:
#     """Test 'zeeker assets deploy' command."""
#     # TODO: Implement after understanding exact interface


# class TestCLIAssetsList:
#     """Test 'zeeker assets list' command."""
#     # TODO: Implement after understanding exact interface


class TestCLIHelp:
    """Test CLI help messages and usage."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    @pytest.mark.parametrize(
        "args",
        [
            ["--help"],
            ["init", "--help"],
            ["add", "--help"],
            ["build", "--help"],
            ["assets", "--help"],
        ],
    )
    def test_cli_help(self, runner, args):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    @pytest.fixture
    def runner(self):
        """Create CliRunner instance."""
        return CliRunner()

    def test_missing_required_argument(self, runner):
        """Test behavior with missing required arguments."""
        result = runner.invoke(cli, ["init"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "PROJECT_NAME" in result.output

    def test_invalid_option(self, runner):
        """Test behavior with invalid options."""
        result = runner.invoke(cli, ["init", "test", "--invalid-option"])

        assert result.exit_code != 0
        assert "no such option" in result.output.lower()

    def test_invalid_path_type(self, runner):
        """Test behavior with invalid path arguments."""
        result = runner.invoke(cli, ["assets", "validate", "/nonexistent/path", "dbname"])

        assert result.exit_code != 0
        assert "does not exist" in result.output or "Invalid value" in result.output


class TestHelpers:
    """Test shared CLI helper functions."""

    def test_require_project_not_in_project(self):
        """Test require_project when not in a project directory."""
        from zeeker.commands.helpers import require_project

        manager = MagicMock()
        manager.is_project_root.return_value = False
        assert require_project(manager) is None

    def test_require_project_load_error(self):
        """Test require_project when project loading fails."""
        from zeeker.commands.helpers import require_project

        manager = MagicMock()
        manager.is_project_root.return_value = True
        manager.load_project.side_effect = Exception("bad toml")
        assert require_project(manager) is None

    def test_require_project_success(self):
        """Test require_project returns project on success."""
        from zeeker.commands.helpers import require_project

        manager = MagicMock()
        manager.is_project_root.return_value = True
        project = MagicMock()
        manager.load_project.return_value = project
        assert require_project(manager) is project

    def test_require_database_missing(self, tmp_path):
        """Test require_database when db file doesn't exist."""
        from zeeker.commands.helpers import require_database

        manager = MagicMock()
        manager.project_path = tmp_path
        project = MagicMock()
        project.database = "nonexistent.db"
        assert require_database(manager, project) is None

    def test_require_database_exists(self, tmp_path):
        """Test require_database when db file exists."""
        from zeeker.commands.helpers import require_database

        (tmp_path / "test.db").touch()
        manager = MagicMock()
        manager.project_path = tmp_path
        project = MagicMock()
        project.database = "test.db"
        assert require_database(manager, project) == tmp_path / "test.db"

    def test_create_deployer_missing_config(self):
        """Test create_deployer with missing S3 config."""
        from zeeker.commands.helpers import create_deployer

        with patch("zeeker.commands.helpers.load_dotenv"):
            with patch(
                "zeeker.core.deployer.ZeekerDeployer",
                side_effect=ValueError("Missing S3_BUCKET"),
            ):
                assert create_deployer() is None

    def test_echo_errors(self):
        """Test echo_errors displays all errors."""
        from zeeker.commands.helpers import echo_errors

        result = ValidationResult(is_valid=False)
        result.errors = ["err1", "err2"]
        # Just verify it doesn't crash — output goes to click
        echo_errors(result)

    def test_echo_warnings(self):
        """Test echo_warnings displays all warnings."""
        from zeeker.commands.helpers import echo_warnings

        result = ValidationResult(is_valid=True)
        result.warnings = ["warn1"]
        echo_warnings(result)


class TestMetadataCommand:
    """Test metadata command group."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_metadata_generate_no_args(self, runner):
        """Test metadata generate with no arguments shows error."""
        with patch("zeeker.commands.metadata.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = True
            mock_project = MagicMock()
            mock_mgr.return_value.load_project.return_value = mock_project

            result = runner.invoke(cli, ["metadata", "generate"])
            assert "Specify a resource name" in result.output

    def test_metadata_generate_not_in_project(self, runner):
        """Test metadata generate when not in project."""
        with patch("zeeker.commands.metadata.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = False

            result = runner.invoke(cli, ["metadata", "generate", "--all"])
            assert "Not in a Zeeker project directory" in result.output

    def test_metadata_show_not_in_project(self, runner):
        """Test metadata show when not in project."""
        with patch("zeeker.commands.metadata.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = False

            result = runner.invoke(cli, ["metadata", "show"])
            assert "Not in a Zeeker project directory" in result.output

    def test_metadata_show_resource_not_found(self, runner):
        """Test metadata show for nonexistent resource."""
        with patch("zeeker.commands.metadata.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = True
            mock_project = MagicMock()
            mock_project.resources = {}
            mock_mgr.return_value.load_project.return_value = mock_project

            result = runner.invoke(cli, ["metadata", "show", "nonexistent"])
            assert "not found" in result.output

    def test_metadata_show_all_empty(self, runner):
        """Test metadata show with no resources."""
        with patch("zeeker.commands.metadata.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = True
            mock_project = MagicMock()
            mock_project.resources = {}
            mock_mgr.return_value.load_project.return_value = mock_project

            result = runner.invoke(cli, ["metadata", "show"])
            assert "No resources found" in result.output


class TestBackupCommand:
    """Test backup command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_backup_not_in_project(self, runner):
        """Test backup when not in project."""
        with patch("zeeker.commands.backup.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = False

            result = runner.invoke(cli, ["backup"])
            assert "Not in a Zeeker project directory" in result.output

    def test_backup_future_date(self, runner):
        """Test backup with future date."""
        with patch("zeeker.commands.backup.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = True
            mock_mgr.return_value.load_project.return_value = MagicMock()

            with patch("zeeker.commands.helpers.load_dotenv"):
                with patch("zeeker.core.deployer.ZeekerDeployer"):
                    result = runner.invoke(cli, ["backup", "--date", "2099-12-31"])
                    assert "cannot be in the future" in result.output

    def test_backup_invalid_date(self, runner):
        """Test backup with invalid date format."""
        with patch("zeeker.commands.backup.ZeekerProjectManager") as mock_mgr:
            mock_mgr.return_value.is_project_root.return_value = True
            mock_mgr.return_value.load_project.return_value = MagicMock()

            with patch("zeeker.commands.helpers.load_dotenv"):
                with patch("zeeker.core.deployer.ZeekerDeployer"):
                    result = runner.invoke(cli, ["backup", "--date", "not-a-date"])
                    assert "Invalid date format" in result.output


class TestAssetsCommand:
    """Test assets commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_assets_generate(self, runner, tmp_path):
        """Test assets generate creates files."""
        output_dir = tmp_path / "output"
        result = runner.invoke(cli, ["assets", "generate", "testdb", str(output_dir)])
        assert result.exit_code == 0
        assert "Generated assets" in result.output
        assert (output_dir / "metadata.json").exists()
        assert (output_dir / "static" / "custom.css").exists()
        assert (output_dir / "templates" / "database-testdb.html").exists()

    def test_assets_validate_passes(self, runner, tmp_path):
        """Test assets validate on valid structure."""
        # Create valid structure
        (tmp_path / "templates").mkdir()
        (tmp_path / "static").mkdir()
        (tmp_path / "templates" / "database-test.html").write_text("<html/>")
        (tmp_path / "static" / "custom.css").write_text("body {}")
        import json

        (tmp_path / "metadata.json").write_text(
            json.dumps({"title": "Test", "description": "Test"})
        )

        result = runner.invoke(cli, ["assets", "validate", str(tmp_path), "test"])
        assert "Validation passed" in result.output

    def test_assets_deploy_clean_and_sync_conflict(self, runner):
        """Test that --clean and --sync flags conflict."""
        with patch("zeeker.commands.helpers.load_dotenv"):
            with patch("zeeker.core.deployer.ZeekerDeployer"):
                # Create a temp dir that exists for the path validation
                import tempfile

                with tempfile.TemporaryDirectory() as td:
                    result = runner.invoke(
                        cli,
                        ["assets", "deploy", td, "testdb", "--clean", "--sync"],
                    )
                    assert "Cannot use both" in result.output
