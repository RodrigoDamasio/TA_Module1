"""Thin HTTP handlers: parse the request, call a use case, shape the response."""

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse

from app.application.services import ResolveShortLink, ShortenUrl
from app.config import Settings, get_settings

from .dependencies import get_resolve_short_link, get_shorten_url
from .problems import PROBLEM_RESPONSE
from .schemas import ShortenRequest, ShortenResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ShortenResponse, "description": "The URL was already shortened"},
        400: PROBLEM_RESPONSE,
        422: PROBLEM_RESPONSE,
        503: PROBLEM_RESPONSE,
    },
)
def shorten(
    body: ShortenRequest,
    response: Response,
    shorten_url: ShortenUrl = Depends(get_shorten_url),
    settings: Settings = Depends(get_settings),
) -> ShortenResponse:
    result = shorten_url(str(body.url))
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return ShortenResponse.from_link(result.link, settings.base_url)


@router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses={404: PROBLEM_RESPONSE},
)
def redirect(
    short_code: str,
    resolve: ResolveShortLink = Depends(get_resolve_short_link),
) -> RedirectResponse:
    link = resolve(short_code)
    return RedirectResponse(link.target.value, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
