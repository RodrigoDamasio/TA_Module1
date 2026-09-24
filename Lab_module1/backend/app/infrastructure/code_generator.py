import secrets

from app.domain.model import SHORT_CODE_ALPHABET, ShortCode


class RandomShortCodeGenerator:
    """Cryptographically random codes, so links can't be guessed from one another."""

    def generate(self) -> ShortCode:
        return ShortCode(
            "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(ShortCode.LENGTH))
        )
