"""Tests for hashing utilities."""

import hashlib

import pytest
from zeeker_common.hashing import get_hash_id


class TestGetHashId:
    """Test suite for get_hash_id function."""

    def test_basic_hash_generation(self):
        """Test basic hash generation from list of strings."""
        result = get_hash_id(["user123", "post456"])
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hash is 32 hex characters

    def test_deterministic_behavior(self):
        """Test that same input always produces same hash."""
        elements = ["foo", "bar", "baz"]
        hash1 = get_hash_id(elements)
        hash2 = get_hash_id(elements)
        assert hash1 == hash2

    def test_different_inputs_produce_different_hashes(self):
        """Test that different inputs produce different hashes."""
        hash1 = get_hash_id(["a", "b"])
        hash2 = get_hash_id(["c", "d"])
        assert hash1 != hash2

    def test_order_matters(self):
        """Test that element order affects the hash."""
        hash1 = get_hash_id(["a", "b", "c"])
        hash2 = get_hash_id(["c", "b", "a"])
        assert hash1 != hash2

    @pytest.mark.parametrize(
        "elements",
        [
            pytest.param([], id="empty_list"),
            pytest.param(["single"], id="single_element"),
            pytest.param(["a b", "c d"], id="whitespace_preserved"),
        ],
    )
    def test_valid_hash_output(self, elements):
        """Test that various inputs produce valid 32-char hex hashes."""
        result = get_hash_id(elements)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_whitespace_changes_hash(self):
        """Test that whitespace in content affects the hash."""
        hash1 = get_hash_id(["a b", "c d"])
        hash2 = get_hash_id(["ab", "cd"])
        assert hash1 != hash2

    def test_special_characters(self):
        """Test hash generation with special characters."""
        elements = ["user@email.com", "post#123", "tag|special"]
        result = get_hash_id(elements)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_unicode_characters(self):
        """Test hash generation with unicode characters."""
        elements = ["用户", "帖子", "标签"]
        result = get_hash_id(elements)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_numeric_strings(self):
        """Test hash generation with numeric strings."""
        elements = ["123", "456", "789"]
        result = get_hash_id(elements)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_mixed_types_converted_to_strings(self):
        """Test that non-string elements are converted to strings."""
        result = get_hash_id(["test", "123"])
        assert isinstance(result, str)
        assert len(result) == 32

    def test_separator_in_content_no_collision(self):
        """Test that pipe character in content does NOT cause collision.

        Previously using '|' as separator caused collisions when content
        contained pipes. Now uses null byte separator to prevent this.
        """
        hash1 = get_hash_id(["a|b", "c"])
        hash2 = get_hash_id(["a", "b|c"])
        assert hash1 != hash2

    def test_known_hash_value(self):
        """Test against a known hash value for regression testing."""
        elements = ["test", "data"]
        expected_hash = hashlib.md5("test\x00data".encode()).hexdigest()
        assert get_hash_id(elements) == expected_hash

    def test_large_number_of_elements(self):
        """Test hash generation with many elements."""
        elements = [f"element_{i}" for i in range(100)]
        result = get_hash_id(elements)
        assert isinstance(result, str)
        assert len(result) == 32

    def test_long_strings(self):
        """Test hash generation with very long strings."""
        long_string = "x" * 10000
        result = get_hash_id([long_string])
        assert isinstance(result, str)
        assert len(result) == 32
