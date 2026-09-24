import secrets
import sqlite3
import string

ALPHABET = string.ascii_letters + string.digits  # 62 characters
CODE_LENGTH = 6
MAX_ATTEMPTS = 5


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def is_valid_code(code: str) -> bool:
    return len(code) == CODE_LENGTH and all(c in ALPHABET for c in code)


def _find_code(conn: sqlite3.Connection, url: str) -> str | None:
    row = conn.execute("SELECT short_code FROM urls WHERE url = ?", (url,)).fetchone()
    return row["short_code"] if row else None


def get_or_create(conn: sqlite3.Connection, url: str) -> tuple[str, bool]:
    """Return (short_code, created). Reuses the code if the URL already exists."""
    existing = _find_code(conn, url)
    if existing:
        return existing, False

    for _ in range(MAX_ATTEMPTS):
        code = generate_code()
        try:
            with conn:
                conn.execute("INSERT INTO urls (short_code, url) VALUES (?, ?)", (code, url))
            return code, True
        except sqlite3.IntegrityError:
            # Either the code collided (retry) or another request inserted
            # the same URL in the meantime (return that one).
            existing = _find_code(conn, url)
            if existing:
                return existing, False
    raise RuntimeError("Could not generate a unique short code")


def resolve(conn: sqlite3.Connection, code: str) -> str | None:
    row = conn.execute("SELECT url FROM urls WHERE short_code = ?", (code,)).fetchone()
    return row["url"] if row else None
