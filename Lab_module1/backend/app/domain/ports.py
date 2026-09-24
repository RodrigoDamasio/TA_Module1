"""Abstractions the application depends on; implemented in app.infrastructure."""

from typing import Protocol

from .model import ShortCode, ShortLink, TargetUrl


class ShortLinkRepository(Protocol):
    def find_by_code(self, code: ShortCode) -> ShortLink | None: ...

    def find_by_target(self, target: TargetUrl) -> ShortLink | None: ...

    def add(self, link: ShortLink) -> None:
        """Store a new short link.

        Raises CodeAlreadyTaken or TargetAlreadyStored on a uniqueness conflict.
        """
        ...


class ShortCodeGenerator(Protocol):
    def generate(self) -> ShortCode: ...
