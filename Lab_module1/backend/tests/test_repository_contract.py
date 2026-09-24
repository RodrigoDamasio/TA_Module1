"""T-R1: the same contract runs against every ShortLinkRepository (Liskov substitution)."""

import pytest
from fakes import InMemoryShortLinkRepository

from app.domain.errors import CodeAlreadyTaken, TargetAlreadyStored
from app.domain.model import ShortCode, ShortLink, TargetUrl
from app.infrastructure.sqlite_repository import SqliteShortLinkRepository

LINK = ShortLink(ShortCode("aB3xY9"), TargetUrl("https://example.com/page"))


@pytest.fixture(params=["sqlite", "memory"])
def repo(request, conn):
    if request.param == "sqlite":
        return SqliteShortLinkRepository(conn)
    return InMemoryShortLinkRepository()


def test_add_then_find_by_code_and_target(repo):
    repo.add(LINK)
    assert repo.find_by_code(LINK.code).target == LINK.target
    assert repo.find_by_target(LINK.target).code == LINK.code


def test_missing_returns_none(repo):
    assert repo.find_by_code(ShortCode("zzzzzz")) is None
    assert repo.find_by_target(TargetUrl("https://nothing.example/")) is None


def test_duplicate_code_raises_code_already_taken(repo):
    repo.add(LINK)
    with pytest.raises(CodeAlreadyTaken):
        repo.add(ShortLink(LINK.code, TargetUrl("https://other.example/")))


def test_duplicate_target_raises_target_already_stored(repo):
    repo.add(LINK)
    with pytest.raises(TargetAlreadyStored):
        repo.add(ShortLink(ShortCode("zzzzzz"), LINK.target))


# T-S3
def test_sqlite_lookup_with_injection_payload_matches_nothing(conn):
    repo = SqliteShortLinkRepository(conn)
    repo.add(LINK)
    assert repo.find_by_target(TargetUrl("https://x.example/' OR '1'='1")) is None
    assert repo.find_by_code(LINK.code) is not None  # table intact
