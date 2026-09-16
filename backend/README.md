# ClearSign OCR service

FastAPI service that turns a photo of a sign into lines of text. OpenCV cleans the image up and Tesseract reads it.

## Requirements

- Python 3.12
- Tesseract 5 with the English data (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian/Ubuntu)

## Run locally

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The client's dev server proxies `/api` here. Interactive docs are at http://localhost:8000/docs.

## Tests

```sh
.venv/bin/pytest
```

The tests render synthetic signs with Pillow (straight, tilted, light-on-dark) and run them through the real pipeline, so they need Tesseract installed.

## Pipeline

1. **Decode** with Pillow, applying the EXIF orientation phones record, then hand off to OpenCV.
2. **Grayscale** and **rescale** so the long side is about 1800 px, where Tesseract reads typical signage best.
3. **Denoise** with a bilateral filter, which smooths JPEG noise while keeping stroke edges sharp.
4. **Adaptive threshold** (Gaussian, 31 px window) to handle uneven lighting and shadows. If the result is mostly dark, it is inverted so text is always dark on white.
5. **Deskew**: words are smeared horizontally so each text line becomes one blob, a minimum-area rectangle is fitted to each line-shaped blob, and the median angle is used to rotate the grayscale image before thresholding again. Corrections under 0.3° or over 20° are ignored.
6. **Recognise** with Tesseract (`--oem 3`, page segmentation mode 6). Words below the confidence threshold are dropped, the survivors are regrouped into lines by Tesseract's block/paragraph/line numbers, and each line reports the mean confidence of its kept words. If nothing is found, sparse-text mode (11) is tried for scattered labels.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OCR_MIN_CONFIDENCE` | `60` | Words below this confidence (0–100) are discarded |
| `OCR_LANGUAGE` | `eng` | Tesseract language pack(s), e.g. `eng+spa` |
| `OCR_PSM` | `6` | Page segmentation mode tried first |
| `OCR_MAX_UPLOAD_BYTES` | `12582912` | Largest accepted upload |
| `CORS_ORIGINS` | `*` | Comma-separated origins allowed to call the API |

## API

`POST /api/ocr` with a multipart field `image` (JPEG or PNG). Returns:

```json
{
  "lines": [{ "text": "PLATFORM 2", "confidence": 96.1 }],
  "dropped_words": 2,
  "processing_ms": 640,
  "skew_degrees": -3.2
}
```

`GET /api/health` reports the Tesseract version and language in use.

## Docker

```sh
docker build -t clearsign-ocr backend
docker run -p 8000:8000 clearsign-ocr
```
