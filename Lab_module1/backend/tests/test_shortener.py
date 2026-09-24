import re

import pytest

from app import shortener

CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")


def _patch_codes(monkeypatch, codes):
    it = iter(codes)
    monkeypatch.setattr(shortener, "generate_code", lambda: next(it))


def _count(conn):
    return conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]


# U1
def test_generated_codes_are_six_alphanumerics():
    for _ in range(1000):
        assert CODE_RE.match(shortener.generate_code())


# U2
def test_generated_codes_are_random():
    codes = {shortener.generate_code() for _ in range(1000)}
    assert len(codes) == 1000


# U3
@pytest.mark.parametrize(
    "code, valid",
    [
        ("aB3xY9", True),
        ("abc", False),
        ("abcdefg", False),
        ("abc-12", False),
        ("abc 12", False),
        ("", False),
    ],
)
def test_is_valid_code(code, valid):
    assert shortener.is_valid_code(code) is valid


# U4
def test_new_url_is_created(conn):
    code, created = shortener.get_or_create(conn, "https://example.com/")
    assert created is True
    assert CODE_RE.match(code)
    assert _count(conn) == 1


# U5
def test_duplicate_url_reuses_code(conn):
    first, _ = shortener.get_or_create(conn, "https://example.com/")
    second, created = shortener.get_or_create(conn, "https://example.com/")
    assert second == first
    assert created is False
    assert _count(conn) == 1


# U6
def test_code_collision_is_retried(conn, monkeypatch):
    _patch_codes(monkeypatch, ["AAAAAA", "AAAAAA", "BBBBBB"])
    shortener.get_or_create(conn, "https://one.example/")
    code, created = shortener.get_or_create(conn, "https://two.example/")
    assert (code, created) == ("BBBBBB", True)
    assert _count(conn) == 2


# U7
def test_gives_up_after_max_attempts(conn, monkeypatch):
    monkeypatch.setattr(shortener, "generate_code", lambda: "AAAAAA")
    shortener.get_or_create(conn, "https://one.example/")
    with pytest.raises(RuntimeError):
        shortener.get_or_create(conn, "https://two.example/")


# U8
def test_resolve(conn):
    code, _ = shortener.get_or_create(conn, "https://example.com/page")
    assert shortener.resolve(conn, code) == "https://example.com/page"
    assert shortener.resolve(conn, "zzzzzz") is None


# U9
def test_concurrent_insert_of_same_url_returns_existing(conn, monkeypatch):
    # Simulate another request saving the URL between our lookup and our insert.
    code, _ = shortener.get_or_create(conn, "https://example.com/")
    real_find = shortener._find_code
    calls = iter([None])
    monkeypatch.setattr(shortener, "_find_code", lambda c, u: next(calls, real_find(c, u)))
    assert shortener.get_or_create(conn, "https://example.com/") == (code, False)
