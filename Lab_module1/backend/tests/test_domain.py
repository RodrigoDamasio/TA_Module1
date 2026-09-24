import dataclasses
import re

import pytest

from app.domain.errors import InvalidShortCode, InvalidTargetUrl
from app.domain.model import ShortCode, TargetUrl
from app.infrastructure.code_generator import RandomShortCodeGenerator

CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")


# T-D1
@pytest.mark.parametrize("value", ["aB3xY9", "000000", "ZZZZZZ"])
def test_short_code_accepts_six_alphanumerics(value):
    assert ShortCode(value).value == value


@pytest.mark.parametrize("value", ["abc", "abcdefg", "abc-12", "abc 12", "", "abc'--", "ábcdef"])
def test_short_code_rejects_invalid(value):
    with pytest.raises(InvalidShortCode):
        ShortCode(value)


# T-D2
@pytest.mark.parametrize("value", ["https://example.com/", "http://localhost:3000/x?q=1#top"])
def test_target_url_accepts_http_and_https(value):
    assert TargetUrl(value).value == value


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.com",
        "javascript:alert(1)",
        "http://",
        "example.com",
        "",
        "https://example.com/" + "a" * 2100,
    ],
)
def test_target_url_rejects_invalid(value):
    with pytest.raises(InvalidTargetUrl):
        TargetUrl(value)


# T-D3
def test_value_objects_compare_by_value_and_are_immutable():
    assert ShortCode("aB3xY9") == ShortCode("aB3xY9")
    assert TargetUrl("https://a.com/") == TargetUrl("https://a.com/")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ShortCode("aB3xY9").value = "zzzzzz"  # type: ignore[misc]


# Code generator (was U1/U2)
def test_generated_codes_are_valid_and_random():
    generator = RandomShortCodeGenerator()
    codes = {generator.generate().value for _ in range(1000)}
    assert len(codes) == 1000
    assert all(CODE_RE.match(c) for c in codes)
