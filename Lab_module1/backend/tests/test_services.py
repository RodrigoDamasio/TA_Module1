"""Use-case tests with in-memory doubles — no database, no HTTP."""

import pytest
from fakes import InMemoryShortLinkRepository, SequenceCodeGenerator

from app.application.services import ResolveShortLink, ShortenUrl
from app.domain.errors import (
    InvalidShortCode,
    InvalidTargetUrl,
    ShortCodeSpaceExhausted,
    ShortLinkNotFound,
    TargetAlreadyStored,
)
from app.domain.model import ShortCode, ShortLink, TargetUrl

URL = "https://example.com/"


@pytest.fixture
def repo():
    return InMemoryShortLinkRepository()


# T-U1
def test_new_url_is_created_then_reused(repo):
    shorten = ShortenUrl(repo, SequenceCodeGenerator(["AAAAAA", "BBBBBB"]))

    first = shorten(URL)
    second = shorten(URL)

    assert (first.link.code.value, first.created) == ("AAAAAA", True)
    assert (second.link.code.value, second.created) == ("AAAAAA", False)
    assert len(repo.by_code) == 1


# T-U2
def test_code_collision_is_retried(repo):
    shorten = ShortenUrl(repo, SequenceCodeGenerator(["AAAAAA", "AAAAAA", "BBBBBB"]))
    shorten("https://one.example/")

    result = shorten("https://two.example/")

    assert (result.link.code.value, result.created) == ("BBBBBB", True)


# T-U3
def test_gives_up_after_max_attempts(repo):
    shorten = ShortenUrl(repo, SequenceCodeGenerator(["AAAAAA"] * 10))
    shorten("https://one.example/")

    with pytest.raises(ShortCodeSpaceExhausted):
        shorten("https://two.example/")


# T-U4
def test_concurrent_insert_of_same_target_returns_stored_link(repo):
    stored = ShortLink(ShortCode("ZZZZZZ"), TargetUrl(URL))

    class RacingRepo(InMemoryShortLinkRepository):
        """The first lookup misses; then another request's insert 'wins' the race."""

        def __init__(self):
            super().__init__()
            self.lookups = 0

        def find_by_target(self, target):
            self.lookups += 1
            return None if self.lookups == 1 else stored

        def add(self, link):
            raise TargetAlreadyStored()

    result = ShortenUrl(RacingRepo(), SequenceCodeGenerator(["AAAAAA"]))(URL)

    assert (result.link, result.created) == (stored, False)


def test_invalid_url_is_rejected_by_the_domain(repo):
    with pytest.raises(InvalidTargetUrl):
        ShortenUrl(repo, SequenceCodeGenerator(["AAAAAA"]))("ftp://example.com")


# T-U5
def test_resolve(repo):
    link = ShortenUrl(repo, SequenceCodeGenerator(["AAAAAA"]))(URL).link
    resolve = ResolveShortLink(repo)

    assert resolve("AAAAAA") == link
    with pytest.raises(ShortLinkNotFound):
        resolve("ZZZZZZ")
    with pytest.raises(InvalidShortCode):
        resolve("bad-code")
