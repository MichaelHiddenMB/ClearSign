import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, read from environment variables."""

    # Words below this Tesseract confidence (0-100) are discarded.
    min_confidence: float = field(default_factory=lambda: _env_float("OCR_MIN_CONFIDENCE", 60.0))
    # Tesseract language pack(s), e.g. "eng" or "eng+spa".
    language: str = field(default_factory=lambda: os.environ.get("OCR_LANGUAGE", "eng"))
    # Page segmentation mode tried first; sparse-text mode is tried if it finds nothing.
    psm: int = field(default_factory=lambda: _env_int("OCR_PSM", 6))
    # Largest upload accepted, in bytes.
    max_upload_bytes: int = field(default_factory=lambda: _env_int("OCR_MAX_UPLOAD_BYTES", 12 * 1024 * 1024))
    # Comma-separated origins allowed to call the API. "*" allows any (development).
    cors_origins: str = field(default_factory=lambda: os.environ.get("CORS_ORIGINS", "*"))

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
