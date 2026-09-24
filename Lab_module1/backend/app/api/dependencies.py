"""Wiring: the only place that chooses concrete implementations for the domain ports."""

from collections.abc import Iterator

from fastapi import Depends

from app.application.services import ResolveShortLink, ShortenUrl
from app.config import Settings, get_settings
from app.domain.ports import ShortCodeGenerator, ShortLinkRepository
from app.infrastructure import database
from app.infrastructure.code_generator import RandomShortCodeGenerator
from app.infrastructure.sqlite_repository import SqliteShortLinkRepository


def get_repository(settings: Settings = Depends(get_settings)) -> Iterator[ShortLinkRepository]:
    conn = database.connect(settings.database_path)
    try:
        yield SqliteShortLinkRepository(conn)
    finally:
        conn.close()


def get_code_generator() -> ShortCodeGenerator:
    return RandomShortCodeGenerator()


def get_shorten_url(
    repo: ShortLinkRepository = Depends(get_repository),
    generator: ShortCodeGenerator = Depends(get_code_generator),
) -> ShortenUrl:
    return ShortenUrl(repo, generator)


def get_resolve_short_link(
    repo: ShortLinkRepository = Depends(get_repository),
) -> ResolveShortLink:
    return ResolveShortLink(repo)
