import time

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .pipeline import run
from .preprocess import ImageDecodeError, decode_image
from .schemas import HealthResponse, Line, OcrResponse

app = FastAPI(
    title="ClearSign OCR",
    description="Preprocesses a photo of signage with OpenCV and extracts its text with Tesseract.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        tesseract_version=str(pytesseract.get_tesseract_version()),
        language=settings.language,
        model=settings.model_description,
    )


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr(image: UploadFile = File(...)) -> OcrResponse:
    data = await image.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="The upload was empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="The image is too large. Send a smaller photo.")

    started = time.perf_counter()
    try:
        # OpenCV and Tesseract are CPU-bound; keep them off the event loop.
        result = await run_in_threadpool(_recognise_bytes, data)
    except ImageDecodeError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return OcrResponse(
        lines=[Line(text=l.text, confidence=l.confidence) for l in result.recognition.lines],
        dropped_words=result.recognition.dropped_words,
        processing_ms=elapsed_ms,
        skew_degrees=result.prepared.skew_degrees,
    )


def _recognise_bytes(data: bytes):
    return run(decode_image(data), settings.pipeline)
