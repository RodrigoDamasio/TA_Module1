"""Test doubles that satisfy the domain ports without a database."""

from collections.abc import Iterable

from app.domain.errors import CodeAlreadyTaken, TargetAlreadyStored
from app.domain.model import ShortCode, ShortLink, TargetUrl


class InMemoryShortLinkRepository:
    def __init__(self) -> None:
        self.by_code: dict[ShortCode, ShortLink] = {}

    def find_by_code(self, code: ShortCode) -> ShortLink | None:
        return self.by_code.get(code)

    def find_by_target(self, target: TargetUrl) -> ShortLink | None:
        return next((link for link in self.by_code.values() if link.target == target), None)

    def add(self, link: ShortLink) -> None:
        if self.find_by_target(link.target):
            raise TargetAlreadyStored()
        if link.code in self.by_code:
            raise CodeAlreadyTaken()
        self.by_code[link.code] = link


class SequenceCodeGenerator:
    """Returns the given codes in order — makes collisions reproducible."""

    def __init__(self, codes: Iterable[str]) -> None:
        self._codes = iter(codes)

    def generate(self) -> ShortCode:
        return ShortCode(next(self._codes))
