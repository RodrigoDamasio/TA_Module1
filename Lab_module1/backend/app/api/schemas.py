from pydantic import BaseModel, HttpUrl

from app.domain.model import ShortLink


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str

    @classmethod
    def from_link(cls, link: ShortLink, base_url: str) -> "ShortenResponse":
        return cls(short_code=link.code.value, short_url=f"{base_url}/{link.code.value}")
