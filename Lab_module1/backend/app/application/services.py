"""Use cases. They orchestrate the domain through its ports and know nothing of HTTP or SQL."""

from dataclasses import dataclass

from app.domain.errors import (
    CodeAlreadyTaken,
    ShortCodeSpaceExhausted,
    ShortLinkNotFound,
    TargetAlreadyStored,
)
from app.domain.model import ShortCode, ShortLink, TargetUrl
from app.domain.ports import ShortCodeGenerator, ShortLinkRepository


@dataclass(frozen=True)
class ShortenResult:
    link: ShortLink
    created: bool


class ShortenUrl:
    """Return the existing short link for a URL, or create one with a fresh code."""

    MAX_ATTEMPTS = 5

    def __init__(self, repo: ShortLinkRepository, generator: ShortCodeGenerator) -> None:
        self._repo = repo
        self._generator = generator

    def __call__(self, raw_url: str) -> ShortenResult:
        target = TargetUrl(raw_url)
        if existing := self._repo.find_by_target(target):
            return ShortenResult(existing, created=False)

        for _ in range(self.MAX_ATTEMPTS):
            link = ShortLink(self._generator.generate(), target)
            try:
                self._repo.add(link)
            except CodeAlreadyTaken:
                continue
            except TargetAlreadyStored:
                # A concurrent request stored the same URL between our lookup and insert.
                if stored := self._repo.find_by_target(target):
                    return ShortenResult(stored, created=False)
                continue
            return ShortenResult(link, created=True)
        raise ShortCodeSpaceExhausted()


class ResolveShortLink:
    """Find the short link for a code, or fail with ShortLinkNotFound / InvalidShortCode."""

    def __init__(self, repo: ShortLinkRepository) -> None:
        self._repo = repo

    def __call__(self, raw_code: str) -> ShortLink:
        code = ShortCode(raw_code)
        link = self._repo.find_by_code(code)
        if link is None:
            raise ShortLinkNotFound(code.value)
        return link
