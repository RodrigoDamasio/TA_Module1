import sqlite3
from urllib.parse import unquote

import pytest

PAYLOAD_URLS = [
    "https://example.com/?q=1' OR '1'='1",
    "https://example.com/'; DROP TABLE urls; --",
    'https://example.com/search?q=" OR ""="',
]


def _row_count(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]


# T-S1
@pytest.mark.parametrize("url", PAYLOAD_URLS)
def test_injection_payload_in_url_is_stored_as_data(client, db_path, url):
    r = client.post("/shorten", json={"url": url})
    assert r.status_code == 201

    location = client.get(f"/{r.json()['short_code']}", follow_redirects=False).headers["location"]
    # URLs are normalized (quotes/spaces percent-encoded); decoded, the payload is intact.
    assert unquote(location) == url
    assert _row_count(db_path) == 1


# T-S2
@pytest.mark.parametrize("code", ["'%20OR%20'1'='1", "1'--xx", "a'or'1", "%27%3B--"])
def test_injection_payload_as_short_code_matches_nothing(client, code):
    client.post("/shorten", json={"url": "https://example.com/secret"})
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 404
    assert "location" not in r.headers
