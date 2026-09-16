import os
from dataclasses import dataclass, field

from .ocr import OcrOptions, default_tessdata_dir
from .pipeline import PipelineOptions
from .preprocess import PreprocessOptions


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int | None) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, read from environment variables."""

    # Words below this Tesseract confidence (0-100) are discarded.
    min_confidence: float = field(default_factory=lambda: _env_float("OCR_MIN_CONFIDENCE", OcrOptions.min_confidence))
    # Tesseract language pack(s), e.g. "eng" or "eng+spa".
    language: str = field(default_factory=lambda: os.environ.get("OCR_LANGUAGE", "eng"))
    # Force a single page segmentation mode instead of the benchmarked set.
    psm: int | None = field(default_factory=lambda: _env_int("OCR_PSM", None))
    # Directory with *.traineddata files.
    tessdata_dir: str | None = field(default_factory=default_tessdata_dir)
    # Largest upload accepted, in bytes.
    max_upload_bytes: int = field(default_factory=lambda: _env_int("OCR_MAX_UPLOAD_BYTES", 12 * 1024 * 1024) or 0)
    # Comma-separated origins allowed to call the API. "*" allows any (development).
    cors_origins: str = field(default_factory=lambda: os.environ.get("CORS_ORIGINS", "*"))

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def pipeline(self) -> PipelineOptions:
        ocr = OcrOptions(
            language=self.language,
            min_confidence=self.min_confidence,
            tessdata_dir=self.tessdata_dir,
            **({"psms": (self.psm,)} if self.psm is not None else {}),
        )
        return PipelineOptions(preprocess=PreprocessOptions(), ocr=ocr)

    @property
    def model_description(self) -> str:
        if self.tessdata_dir:
            return f"{self.language} from {self.tessdata_dir}"
        return f"{self.language} (Tesseract default)"


settings = Settings()
