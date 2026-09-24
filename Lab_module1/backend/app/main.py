import sqlite3
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

from . import db, shortener
from .config import get_settings

app = FastAPI(title="URL Shortener")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect(get_settings().database_path)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten(
    body: ShortenRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> ShortenResponse:
    code, created = shortener.get_or_create(conn, str(body.url))
    if not created:
        response.status_code = status.HTTP_200_OK
    return ShortenResponse(short_code=code, short_url=f"{get_settings().base_url}/{code}")


@app.get("/{short_code}")
def redirect(short_code: str, conn: sqlite3.Connection = Depends(get_conn)) -> RedirectResponse:
    url = shortener.resolve(conn, short_code) if shortener.is_valid_code(short_code) else None
    if url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found")
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
