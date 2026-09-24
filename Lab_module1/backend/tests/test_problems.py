"""RFC 9457 Problem Details: every error response has the standard shape and media type."""

import pytest
from fakes import SequenceCodeGenerator

from app.api.dependencies import get_code_generator, get_shorten_url
from app.main import app

PROBLEM_JSON = "application/problem+json"
ORIGIN = "http://localhost:3000"


def assert_problem(r, status, slug=None, instance=None):
    assert r.status_code == status
    assert r.headers["content-type"] == PROBLEM_JSON
    body = r.json()
    assert body["status"] == status  # T-P9: body status matches HTTP status
    if slug is None:
        assert body["type"] == "about:blank"
    else:
        assert body["type"] == f"http://test.local/problems/{slug}"
    assert body["title"]
    if instance:
        assert body["instance"] == instance
    return body


# T-P1
def test_unknown_code_is_a_problem(client):
    body = assert_problem(client.get("/zzzzzz"), 404, "short-link-not-found", "/zzzzzz")
    assert body["detail"] == "No short link exists for code 'zzzzzz'."


# T-P2
def test_malformed_code_is_a_problem_without_echoing_input(client):
    r = client.get("/abc-12")
    body = assert_problem(r, 404, "short-link-not-found", "/abc-12")
    assert "abc-12" not in body["detail"]


# T-P3
def test_invalid_url_is_a_validation_problem(client):
    r = client.post("/shorten", json={"url": "not-a-url-xyz123"})
    body = assert_problem(r, 422, "validation-error", "/shorten")
    assert body["errors"] == [{"detail": "Must be a valid http or https URL.", "pointer": "#/url"}]
    assert "not-a-url-xyz123" not in r.text  # user input is not echoed
    assert not {"loc", "ctx", "input", "msg"} & set(r.text.replace('"', " ").split())


# T-P4
@pytest.mark.parametrize(
    "payload, message",
    [({}, "This field is required."), ({"url": 123}, "Must be a valid http or https URL.")],
)
def test_missing_or_wrong_type_field(client, payload, message):
    body = assert_problem(client.post("/shorten", json=payload), 422, "validation-error")
    assert body["errors"] == [{"detail": message, "pointer": "#/url"}]


# T-P5
def test_non_json_body_is_malformed_request(client):
    r = client.post("/shorten", content="not json", headers={"Content-Type": "application/json"})
    assert_problem(r, 400, "malformed-request", "/shorten")


# T-P6
def test_exhausted_code_space_is_503_with_retry_after(client):
    app.dependency_overrides[get_code_generator] = lambda: SequenceCodeGenerator(["AAAAAA"] * 10)
    client.post("/shorten", json={"url": "https://one.example/"})

    r = client.post("/shorten", json={"url": "https://two.example/"}, headers={"Origin": ORIGIN})

    assert_problem(r, 503, "code-space-exhausted", "/shorten")
    assert r.headers["retry-after"] == "1"
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()  # C2


# T-P7
def test_unexpected_error_is_500_problem_with_cors_headers(client):
    def broken():
        def shorten(url):
            raise RuntimeError("secret internal detail")

        return shorten

    app.dependency_overrides[get_shorten_url] = broken

    r = client.post("/shorten", json={"url": "https://example.com/"}, headers={"Origin": ORIGIN})

    assert_problem(r, 500, "internal-error", "/shorten")
    assert "secret internal detail" not in r.text
    assert "Traceback" not in r.text
    assert r.headers["access-control-allow-origin"] == ORIGIN  # C1: middleware order


# T-P8
def test_framework_errors_use_about_blank(client):
    r = client.delete("/shorten")
    body = assert_problem(r, 405)
    assert body["title"] == "Method Not Allowed"
    assert "allow" in r.headers

    body = assert_problem(client.get("/a/b/c"), 404)
    assert body["title"] == "Not Found"


# T-P9
def test_title_is_stable_per_type(client):
    first = client.get("/zzzzzz").json()
    second = client.get("/yyyyyy").json()
    assert first["type"] == second["type"]
    assert first["title"] == second["title"]
    assert first["detail"] != second["detail"]


# T-P10
def test_problem_types_are_documented(client):
    r = client.get("/problems/short-link-not-found")
    assert r.status_code == 200
    assert r.json()["status"] == 404
    assert_problem(client.get("/problems/does-not-exist"), 404)


def test_error_responses_on_redirect_route_carry_cors_headers(client):
    r = client.get("/zzzzzz", headers={"Origin": ORIGIN})
    assert r.headers["access-control-allow-origin"] == ORIGIN


def test_domain_url_rejection_is_a_validation_problem(client):
    """The domain re-checks URLs itself; if it rejects one, the API still answers RFC 9457."""
    from app.domain.errors import InvalidTargetUrl

    def strict():
        def shorten(url):
            raise InvalidTargetUrl(url)

        return shorten

    app.dependency_overrides[get_shorten_url] = strict
    r = client.post("/shorten", json={"url": "https://example.com/"})
    body = assert_problem(r, 422, "validation-error", "/shorten")
    assert body["errors"] == [{"detail": "Must be a valid http or https URL.", "pointer": "#/url"}]
