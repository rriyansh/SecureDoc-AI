"""Tests for src.utils."""

from pathlib import Path

from src.utils import clean_text, file_hash, format_docs, truncate


def test_clean_text_whitespace():
    assert clean_text("a   b\t\tc") == "a b c"


def test_clean_text_newlines():
    assert clean_text("l1\r\nl2\rl3") == "l1\nl2\nl3"


def test_file_hash_deterministic(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    assert file_hash(f) == file_hash(f)
    assert len(file_hash(f)) == 64


def test_format_docs():
    class D:
        def __init__(self, c): self.page_content = c
    assert format_docs([D("x"), D("y")]) == "x\n\n---\n\ny"


def test_truncate():
    assert truncate("abcdef", 6) == "abcdef"
    assert truncate("abcdefghij", 6) == "abc..."
