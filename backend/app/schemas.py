from pydantic import BaseModel, Field


class Line(BaseModel):
    text: str = Field(description="One line of recognised text, in reading order.")
    confidence: float = Field(ge=0, le=100, description="Mean Tesseract word confidence for the kept words.")


class OcrResponse(BaseModel):
    lines: list[Line]
    dropped_words: int = Field(ge=0, description="Words discarded for falling below the confidence threshold.")
    processing_ms: int = Field(ge=0, description="Server-side time spent preprocessing and recognising.")
    skew_degrees: float = Field(description="Rotation applied to straighten the image, in degrees.")


class HealthResponse(BaseModel):
    status: str
    tesseract_version: str
    language: str
    model: str
