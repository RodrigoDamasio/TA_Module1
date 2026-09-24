"""Value objects and the ShortLink aggregate. Invalid instances cannot be created."""

import string
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from urllib.parse import urlsplit

from .errors import InvalidShortCode, InvalidTargetUrl

SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
_ALPHABET_SET = frozenset(SHORT_CODE_ALPHABET)


@dataclass(frozen=True, slots=True)
class ShortCode:
    value: str
    LENGTH: ClassVar[int] = 6

    def __post_init__(self) -> None:
        if len(self.value) != self.LENGTH or not set(self.value) <= _ALPHABET_SET:
            raise InvalidShortCode(self.value)


@dataclass(frozen=True, slots=True)
class TargetUrl:
    value: str
    MAX_LENGTH: ClassVar[int] = 2083

    def __post_init__(self) -> None:
        parts = urlsplit(self.value)
        if (
            len(self.value) > self.MAX_LENGTH
            or parts.scheme not in ("http", "https")
            or not parts.hostname
        ):
            raise InvalidTargetUrl(self.value)


@dataclass(frozen=True, slots=True)
class ShortLink:
    """Aggregate root: a short code bound to the target URL it redirects to."""

    code: ShortCode
    target: TargetUrl
    created_at: datetime | None = None
