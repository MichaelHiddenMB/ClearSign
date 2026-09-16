import time

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .ocr import recognize
from .preprocess import ImageDecodeError, background_is_dark, decode_image, preprocess
from .schemas import HealthResponse, Line, OcrResponse

app = FastAPI(
    title="ClearSign OCR",
    description="Preprocesses a photo of signage with OpenCV and extracts its text with Tesseract.",
    version="0.1.0",
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

    prepared, recognition = result
    return OcrResponse(
        lines=[Line(text=l.text, confidence=l.confidence) for l in recognition.lines],
        dropped_words=recognition.dropped_words,
        processing_ms=elapsed_ms,
        skew_degrees=prepared.skew_degrees,
    )


def _recognise_bytes(data: bytes):
    bgr = decode_image(data)
    prepared = preprocess(bgr)
    recognition = _recognise(prepared)
    if not recognition.lines:
        # A dark sign in a bright scene (or the reverse) can fool the polarity
        # guess; the opposite polarity is a cheap second chance.
        flipped = preprocess(bgr, invert=not background_is_dark(_gray(bgr)))
        flipped_recognition = _recognise(flipped)
        if flipped_recognition.lines:
            return flipped, flipped_recognition
    return prepared, recognition


def _recognise(prepared):
    return recognize(
        prepared.binary,
        min_confidence=settings.min_confidence,
        language=settings.language,
        psm=settings.psm,
    )


def _gray(bgr):
    import cv2

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
