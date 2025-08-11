"""Tests for async template generation and validation."""

import tempfile
import pytest
from pathlib import Path
import ast
import inspect

from zeeker.core.project import ZeekerProjectManager


class TestAsyncTemplateGeneration:
    """Test async template generation produces valid Python code."""

    @pytest.fixture
    def test_project_path(self):
        """Create a temporary directory for test projects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_async_resource_template_generation(self, test_project_path):
        """Test that async resource templates generate valid Python."""
        project_path = test_project_path / "test_async_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_async_project")

        # Add async resource
        result = manager.add_resource("async_resource", "Test async resource", is_async=True)
        assert result.is_valid

        # Check the generated file
        resource_file = project_path / "resources" / "async_resource.py"
        assert resource_file.exists()

        # Read and validate the generated code
        code_content = resource_file.read_text()

        # Verify async syntax is present
        assert "async def fetch_data" in code_content
        assert "from typing import Optional, List, Dict, Any" in code_content
        assert "import asyncio" in code_content
        assert "import aiohttp" in code_content

        # Verify the code is valid Python
        try:
            ast.parse(code_content)
        except SyntaxError as e:
            pytest.fail(f"Generated async resource template has syntax error: {e}")

        # Verify the code can be compiled
        try:
            compile(code_content, resource_file, "exec")
        except Exception as e:
            pytest.fail(f"Generated async resource template cannot be compiled: {e}")

    def test_async_fragments_template_generation(self, test_project_path):
        """Test that async fragments templates generate valid Python."""
        project_path = test_project_path / "test_async_fragments_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_async_fragments_project")

        # Add async fragments resource
        result = manager.add_resource(
            "async_fragments", "Test async fragments resource", fragments=True, is_async=True
        )
        assert result.is_valid

        # Check the generated file
        resource_file = project_path / "resources" / "async_fragments.py"
        assert resource_file.exists()

        # Read and validate the generated code
        code_content = resource_file.read_text()

        # Verify async syntax is present for both functions
        assert "async def fetch_data" in code_content
        assert "async def fetch_fragments_data" in code_content
        assert "import asyncio" in code_content
        assert "import aiohttp" in code_content

        # Verify fragments-specific content
        assert "main_data_context" in code_content
        assert "Optional[List[Dict[str, Any]]] = None" in code_content

        # Verify the code is valid Python
        try:
            ast.parse(code_content)
        except SyntaxError as e:
            pytest.fail(f"Generated async fragments template has syntax error: {e}")

    def test_async_template_function_signatures(self, test_project_path):
        """Test that async templates have correct function signatures."""
        project_path = test_project_path / "test_signatures_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_signatures_project")

        # Add async resource
        manager.add_resource("test_async", "Test", is_async=True)

        # Read the generated file and check function signatures using AST
        resource_file = project_path / "resources" / "test_async.py"
        code_content = resource_file.read_text()

        # Parse the AST to inspect function signatures
        tree = ast.parse(code_content)

        # Find fetch_data function
        fetch_data_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "fetch_data":
                fetch_data_func = node
                break

        assert fetch_data_func is not None, "fetch_data async function not found"
        assert len(fetch_data_func.args.args) == 1, "fetch_data should have exactly one parameter"
        assert (
            fetch_data_func.args.args[0].arg == "existing_table"
        ), "Parameter should be 'existing_table'"

    def test_async_fragments_template_function_signatures(self, test_project_path):
        """Test that async fragments templates have correct function signatures."""
        project_path = test_project_path / "test_fragments_signatures_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_fragments_signatures_project")

        # Add async fragments resource
        manager.add_resource("test_async_frags", "Test", fragments=True, is_async=True)

        # Read and parse the generated file using AST
        resource_file = project_path / "resources" / "test_async_frags.py"
        code_content = resource_file.read_text()
        tree = ast.parse(code_content)

        # Find both async functions
        fetch_data_func = None
        fetch_fragments_func = None

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                if node.name == "fetch_data":
                    fetch_data_func = node
                elif node.name == "fetch_fragments_data":
                    fetch_fragments_func = node

        # Verify fetch_data signature (1 param)
        assert fetch_data_func is not None, "fetch_data async function not found"
        assert len(fetch_data_func.args.args) == 1, "fetch_data should have 1 parameter"
        assert fetch_data_func.args.args[0].arg == "existing_table"

        # Verify fetch_fragments_data signature (2 params)
        assert fetch_fragments_func is not None, "fetch_fragments_data async function not found"
        assert (
            len(fetch_fragments_func.args.args) == 2
        ), "fetch_fragments_data should have 2 parameters"
        assert fetch_fragments_func.args.args[0].arg == "existing_fragments_table"
        assert fetch_fragments_func.args.args[1].arg == "main_data_context"

    def test_async_template_imports_and_dependencies(self, test_project_path):
        """Test that async templates have all necessary imports."""
        project_path = test_project_path / "test_imports_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_imports_project")

        # Test async resource imports
        manager.add_resource("async_test", "Test", is_async=True)
        resource_file = project_path / "resources" / "async_test.py"
        code = resource_file.read_text()

        # Required imports for async functionality
        required_imports = [
            "import asyncio",
            "import aiohttp",
            "from sqlite_utils.db import Table",
            "from typing import Optional, List, Dict, Any",
        ]

        for import_statement in required_imports:
            assert import_statement in code, f"Missing import: {import_statement}"

        # Test async fragments resource imports
        manager.add_resource("async_frags_test", "Test", fragments=True, is_async=True)
        fragments_file = project_path / "resources" / "async_frags_test.py"
        fragments_code = fragments_file.read_text()

        # Should have same imports plus fragments-specific content
        for import_statement in required_imports:
            assert (
                import_statement in fragments_code
            ), f"Missing import in fragments: {import_statement}"

    def test_async_template_examples_and_comments(self, test_project_path):
        """Test that async templates contain helpful examples and documentation."""
        project_path = test_project_path / "test_examples_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_examples_project")

        # Test async resource examples
        manager.add_resource("example_async", "Test", is_async=True)
        resource_file = project_path / "resources" / "example_async.py"
        code = resource_file.read_text()

        # Should contain helpful async examples and documentation
        helpful_content = [
            "aiohttp.ClientSession",  # Example of async HTTP
            "async with session.get",  # Example of async context manager usage
            "async with",  # Proper async context manager usage
            "fetch_from_api",  # Example helper function
        ]

        for content in helpful_content:
            assert content in code, f"Missing helpful content: {content}"

    def test_mixed_sync_and_async_project(self, test_project_path):
        """Test that projects can have both sync and async resources."""
        project_path = test_project_path / "test_mixed_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_mixed_project")

        # Add sync resource
        manager.add_resource("sync_resource", "Sync resource")
        sync_file = project_path / "resources" / "sync_resource.py"
        sync_code = sync_file.read_text()

        # Add async resource
        manager.add_resource("async_resource", "Async resource", is_async=True)
        async_file = project_path / "resources" / "async_resource.py"
        async_code = async_file.read_text()

        # Verify sync resource doesn't have async syntax
        assert "async def fetch_data" not in sync_code
        assert "def fetch_data" in sync_code
        assert "aiohttp" not in sync_code

        # Verify async resource has async syntax
        assert "async def fetch_data" in async_code
        assert "aiohttp" in async_code

        # Both should be valid Python syntax
        try:
            ast.parse(sync_code)
            ast.parse(async_code)
        except SyntaxError as e:
            pytest.fail(f"Mixed project templates have syntax error: {e}")

        # Verify we can parse both to find their function definitions
        sync_tree = ast.parse(sync_code)
        async_tree = ast.parse(async_code)

        # Find functions
        sync_func = None
        async_func = None

        for node in ast.walk(sync_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "fetch_data":
                sync_func = node

        for node in ast.walk(async_tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "fetch_data":
                async_func = node

        assert sync_func is not None, "Sync fetch_data function not found"
        assert async_func is not None, "Async fetch_data function not found"

    def test_async_template_error_handling(self, test_project_path):
        """Test that async templates include proper error handling patterns."""
        project_path = test_project_path / "test_error_handling_project"

        # Initialize project
        manager = ZeekerProjectManager(project_path)
        manager.init_project("test_error_handling_project")

        # Add async resource
        manager.add_resource("error_test", "Test error handling", is_async=True)
        resource_file = project_path / "resources" / "error_test.py"
        code = resource_file.read_text()

        # Should include error handling patterns and response checking
        error_handling_patterns = [
            "if response.status == 200:",  # HTTP status checking
            "response.status",  # Status code handling
            "API request failed",  # Error message patterns
        ]

        for pattern in error_handling_patterns:
            assert pattern in code, f"Missing error handling pattern: {pattern}"
