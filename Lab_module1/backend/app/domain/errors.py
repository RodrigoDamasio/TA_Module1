"""Business failures, named in the ubiquitous language. Mapped to HTTP only in app.api."""


class DomainError(Exception):
    """Base class for every business rule violation."""


class InvalidShortCode(DomainError):
    def __init__(self, value: str) -> None:
        super().__init__("A short code must be 6 letters or digits.")
        self.value = value


class InvalidTargetUrl(DomainError):
    def __init__(self, value: str) -> None:
        super().__init__("A target URL must be an http or https URL of at most 2083 characters.")
        self.value = value


class ShortLinkNotFound(DomainError):
    def __init__(self, code: str) -> None:
        super().__init__(f"No short link exists for code '{code}'.")
        self.code = code


class ShortCodeSpaceExhausted(DomainError):
    def __init__(self) -> None:
        super().__init__("Could not find an unused short code; try again.")


class CodeAlreadyTaken(DomainError):
    """Repository conflict: another short link already uses this code."""


class TargetAlreadyStored(DomainError):
    """Repository conflict: a short link for this target URL already exists."""
