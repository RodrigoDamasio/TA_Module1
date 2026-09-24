"""SQLite implementation of ShortLinkRepository — the only module that contains SQL.

Every value is passed as a bound `?` parameter, never formatted into the SQL text.
"""

import sqlite3
from datetime import UTC, datetime

from app.domain.errors import CodeAlreadyTaken, TargetAlreadyStored
from app.domain.model import ShortCode, ShortLink, TargetUrl

_FIND_BY_CODE = "SELECT short_code, url, created_at FROM urls WHERE short_code = ?"
_FIND_BY_TARGET = "SELECT short_code, url, created_at FROM urls WHERE url = ?"
_INSERT = "INSERT INTO urls (short_code, url) VALUES (?, ?)"


class SqliteShortLinkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def find_by_code(self, code: ShortCode) -> ShortLink | None:
        row = self._conn.execute(_FIND_BY_CODE, (code.value,)).fetchone()
        return _to_link(row) if row else None

    def find_by_target(self, target: TargetUrl) -> ShortLink | None:
        row = self._conn.execute(_FIND_BY_TARGET, (target.value,)).fetchone()
        return _to_link(row) if row else None

    def add(self, link: ShortLink) -> None:
        try:
            with self._conn:
                self._conn.execute(_INSERT, (link.code.value, link.target.value))
        except sqlite3.IntegrityError as err:
            if self.find_by_target(link.target):
                raise TargetAlreadyStored() from err
            raise CodeAlreadyTaken() from err


def _to_link(row: sqlite3.Row) -> ShortLink:
    return ShortLink(
        code=ShortCode(row["short_code"]),
        target=TargetUrl(row["url"]),
        created_at=datetime.fromisoformat(row["created_at"]).replace(tzinfo=UTC),
    )
