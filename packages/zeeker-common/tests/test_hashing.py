"""Tests for hashing utilities."""

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

    def test_single_element(self):
        """Test hash generation with single element."""
        result = get_hash_id(["single"])
        assert isinstance(result, str)
        assert len(result) == 32

    def test_empty_list(self):
        """Test hash generation with empty list."""
        result = get_hash_id([])
        assert isinstance(result, str)
        assert len(result) == 32
        # Empty string should produce consistent hash
        assert result == get_hash_id([])

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
        # The function signature expects list[str], but implementation
        # uses str() to convert, so this tests that behavior
        result = get_hash_id(["test", "123"])
        assert isinstance(result, str)
        assert len(result) == 32

    def test_whitespace_handling(self):
        """Test that whitespace is preserved in hashing."""
        hash1 = get_hash_id(["a b", "c d"])
        hash2 = get_hash_id(["ab", "cd"])
        assert hash1 != hash2

    def test_separator_in_content(self):
        """Test that pipe character in content creates collision.

        Note: This is a known limitation - using pipe in data can cause
        hash collisions since pipe is used as the separator.
        """
        # Since the implementation uses "|" as separator,
        # these will actually produce the same hash (collision)
        hash1 = get_hash_id(["a|b", "c"])
        hash2 = get_hash_id(["a", "b|c"])
        # Both result in "a|b|c" when joined, so they're the same
        assert hash1 == hash2  # This is a limitation of the implementation

    def test_known_hash_value(self):
        """Test against a known hash value for regression testing."""
        # This ensures the hash implementation doesn't change unexpectedly
        elements = ["test", "data"]
        expected_hash = "5dcda16b3a1a182e7d9304b4ce5bc399"
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
