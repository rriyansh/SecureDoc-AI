"""Tests for utility functions."""

import pytest
from src.utils import (
    hash_text,
    truncate,
    safe_get,
    generate_id,
    sanitize_filename,
    parse_size,
    format_duration,
    mask_secrets,
    chunk_list,
    flatten_dict,
    deep_merge,
)


class TestHashText:
    def test_hash_text_consistent(self):
        assert hash_text("hello") == hash_text("hello")

    def test_hash_text_different(self):
        assert hash_text("hello") != hash_text("world")

    def test_hash_text_empty(self):
        assert hash_text("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestTruncate:
    def test_truncate_short(self):
        assert truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        assert truncate("hello world", 8) == "hello..."

    def test_truncate_exact(self):
        assert truncate("hello", 5) == "hello"


class TestSafeGet:
    def test_safe_get_nested(self):
        data = {"a": {"b": {"c": 1}}}
        assert safe_get(data, "a.b.c") == 1

    def test_safe_get_missing(self):
        data = {"a": {"b": 1}}
        assert safe_get(data, "a.c", "default") == "default"

    def test_safe_get_none(self):
        data = {"a": None}
        assert safe_get(data, "a.b", "default") == "default"


class TestGenerateId:
    def test_generate_id_unique(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_id_with_prefix(self):
        id_str = generate_id("test_")
        assert id_str.startswith("test_")
        assert len(id_str) > 5


class TestSanitizeFilename:
    def test_sanitize_special_chars(self):
        assert sanitize_filename('file<>:"/\\|?*.txt') == "file_________.txt"

    def test_sanitize_control_chars(self):
        assert sanitize_filename("file\x00\x01.txt") == "file__.txt"

    def test_sanitize_strip(self):
        assert sanitize_filename("  file.txt  ") == "file.txt"
        assert sanitize_filename(".file.txt.") == "file.txt"


class TestParseSize:
    def test_parse_bytes(self):
        assert parse_size("100") == 100
        assert parse_size("100B") == 100

    def test_parse_kb(self):
        assert parse_size("1KB") == 1024
        assert parse_size("1.5KB") == 1536

    def test_parse_mb(self):
        assert parse_size("1MB") == 1024**2

    def test_parse_gb(self):
        assert parse_size("1GB") == 1024**3

    def test_parse_invalid(self):
        assert parse_size("invalid") == 0


class TestFormatDuration:
    def test_format_microseconds(self):
        assert format_duration(0.000001) == "1µs"

    def test_format_milliseconds(self):
        assert format_duration(0.001) == "1.0ms"

    def test_format_seconds(self):
        assert format_duration(1.5) == "1.50s"

    def test_format_minutes(self):
        assert format_duration(90) == "1.5m"

    def test_format_hours(self):
        assert format_duration(7200) == "2.0h"


class TestMaskSecrets:
    def test_mask_api_key(self):
        text = 'api_key="secret123"'
        masked = mask_secrets(text)
        assert "REDACTED" in masked
        assert "secret123" not in masked

    def test_mask_bearer_token(self):
        text = "Authorization: Bearer abc123"
        masked = mask_secrets(text)
        assert "REDACTED" in masked


class TestChunkList:
    def test_chunk_list_even(self):
        lst = list(range(10))
        chunks = chunk_list(lst, 3)
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_chunk_list_exact(self):
        lst = list(range(9))
        chunks = chunk_list(lst, 3)
        assert len(chunks) == 3
        assert all(len(c) == 3 for c in chunks)


class TestFlattenDict:
    def test_flatten_simple(self):
        data = {"a": 1, "b": {"c": 2}}
        flat = flatten_dict(data)
        assert flat == {"a": 1, "b.c": 2}

    def test_flatten_deep(self):
        data = {"a": {"b": {"c": 1}}}
        flat = flatten_dict(data)
        assert flat == {"a.b.c": 1}

    def test_flatten_custom_sep(self):
        data = {"a": {"b": 1}}
        flat = flatten_dict(data, sep="/")
        assert flat == {"a/b": 1}


class TestDeepMerge:
    def test_merge_simple(self):
        base = {"a": 1}
        update = {"b": 2}
        assert deep_merge(base, update) == {"a": 1, "b": 2}

    def test_merge_nested(self):
        base = {"a": {"x": 1}}
        update = {"a": {"y": 2}}
        assert deep_merge(base, update) == {"a": {"x": 1, "y": 2}}

    def test_merge_override(self):
        base = {"a": 1}
        update = {"a": 2}
        assert deep_merge(base, update) == {"a": 2}