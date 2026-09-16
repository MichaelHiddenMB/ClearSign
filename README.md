# ClearSign

ClearSign is an accessibility web app for people with low vision. Point a phone camera at real-world signage, a menu, or a label, and ClearSign re-presents the text enlarged, in a high-contrast colour scheme of your choosing, and reads it aloud.

## How it works

1. The React client captures a frame from the browser camera (or a photo from the library) and posts it to the API.
2. The FastAPI service locates the text with a first Tesseract pass, then preprocesses that region with OpenCV (perspective correction, rescaling, denoising, adaptive thresholding, deskewing) and reads it with Tesseract, merging the reads of several candidate images and discarding words below a confidence threshold. The pipeline is tuned with a benchmark of real and synthetic sign photos; see `backend/README.md`.
3. The client renders the recognised lines in the reader, where text size, typeface, line and letter spacing, weight, and colour theme are all adjustable, and the Web Speech API reads the lines aloud with the current word highlighted.

## Repository layout

| Path | Contents |
| --- | --- |
| `frontend/` | React + TypeScript client (Vite) |
| `backend/` | FastAPI + OpenCV + Tesseract service |

## Running it

You need Node 20+, Python 3.12, and Tesseract 5 (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian/Ubuntu).

```sh
# Terminal 1: OCR service on :8000
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
sh scripts/fetch_tessdata.sh          # the more accurate tessdata_best model (15 MB)
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2: client on :5173
cd frontend
npm install
npm run dev
```

The client's dev server proxies `/api` to the service. While the service is not running, the client shows a clearly labelled sample result so the reader can be exercised on its own. Each part has its own README with details, and `backend/Dockerfile` builds a container with Tesseract included.

## API contract

The client expects one endpoint from the service:

```
POST /api/ocr
Content-Type: multipart/form-data
  image: <JPEG or PNG file>

200 OK
{
  "lines": [
    { "text": "PLATFORM 2", "confidence": 96.1 }
  ],
  "dropped_words": 2,
  "processing_ms": 640,
  "skew_degrees": -3.2
}
```

`lines` are in reading order, `confidence` is the mean Tesseract word confidence for the line (0–100), `dropped_words` counts the words the service filtered out for low confidence, and `skew_degrees` is the rotation applied to straighten the photo. An unreadable upload returns 400 and an oversized one 413; the client shows any non-2xx status as a service error.
