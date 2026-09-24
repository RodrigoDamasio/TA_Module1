import re
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.main import app

CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")


def _shorten(client, url):
    return client.post("/shorten", json={"url": url})


# A1
def test_shorten_valid_url(client):
    r = _shorten(client, "https://example.com/page")
    assert r.status_code == 201
    body = r.json()
    assert CODE_RE.match(body["short_code"])
    assert body["short_url"] == f"http://test.local/{body['short_code']}"


# A2
def test_duplicate_url_returns_same_code(client):
    first = _shorten(client, "https://example.com").json()
    r = _shorten(client, "https://example.com")
    assert r.status_code == 200
    assert r.json()["short_code"] == first["short_code"]


# A3
def test_different_urls_get_different_codes(client):
    a = _shorten(client, "https://example.com/a").json()["short_code"]
    b = _shorten(client, "https://example.com/b").json()["short_code"]
    assert a != b


# A4
@pytest.mark.parametrize(
    "bad",
    [
        "not-a-url",
        "example.com",
        "ftp://example.com",
        "javascript:alert(1)",
        "http://",
        "",
    ],
)
def test_invalid_urls_rejected(client, bad):
    assert _shorten(client, bad).status_code == 422


# A5
def test_too_long_url_rejected(client):
    assert _shorten(client, "https://example.com/" + "a" * 2100).status_code == 422


# A6
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"json": {}}, 422),
        ({"json": {"url": 123}}, 422),
        # Not JSON at all is a syntax problem → 400 (RFC 9457 "malformed-request")
        ({"content": "not json", "headers": {"Content-Type": "application/json"}}, 400),
    ],
)
def test_malformed_body_rejected(client, kwargs, expected):
    assert client.post("/shorten", **kwargs).status_code == expected


# A7
def test_redirect(client):
    code = _shorten(client, "https://example.com/page").json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/page"


# A8
def test_redirect_preserves_query_and_fragment(client):
    url = "https://example.com/search?q=a+b&page=2#top"
    code = _shorten(client, url).json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.headers["location"] == url


# A9
def test_unknown_code_is_404(client):
    assert client.get("/zzzzzz", follow_redirects=False).status_code == 404


# A10
@pytest.mark.parametrize("code", ["abc", "abcdefgh", "abc-12"])
def test_malformed_code_is_404(client, code):
    assert client.get(f"/{code}", follow_redirects=False).status_code == 404


# A11
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def _preflight(client, origin):
    return client.options(
        "/shorten",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )


# A12
def test_cors_allows_frontend_origin(client):
    r = _preflight(client, "http://localhost:3000")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# A13
def test_cors_blocks_other_origins(client):
    r = _preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in r.headers


# A14
def test_data_persists_across_clients(client):
    code = _shorten(client, "https://example.com/persist").json()["short_code"]
    new_client = TestClient(app)
    r = new_client.get(f"/{code}", follow_redirects=False)
    assert r.headers["location"] == "https://example.com/persist"


# A15
def test_end_to_end_flow(client):
    short_url = _shorten(client, "https://example.com/e2e").json()["short_url"]
    r = client.get(urlparse(short_url).path, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/e2e"
