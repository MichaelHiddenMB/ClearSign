# ClearSign

ClearSign is an accessibility web app for people with low vision. Point a phone camera at real-world signage, a menu, or a label, and ClearSign re-presents the text enlarged, in a high-contrast colour scheme of your choosing, and reads it aloud.

## How it works

1. The React client captures a frame from the browser camera (or a photo from the library) and posts it to the API.
2. The FastAPI service preprocesses the frame with OpenCV (grayscale, adaptive thresholding, deskewing) and runs Tesseract OCR, discarding words below a confidence threshold.
3. The client renders the recognised lines in the reader, where text size, typeface, line and letter spacing, weight, and colour theme are all adjustable, and the Web Speech API reads the lines aloud with the current word highlighted.

## Repository layout

| Path | Contents |
| --- | --- |
| `frontend/` | React + TypeScript client (Vite) |
| `backend/` | FastAPI + OpenCV + Tesseract service (not yet added) |

## Running the client

```sh
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://localhost:8000`. While the API is not running, the client shows a clearly labelled sample result so the reader can be exercised on its own.

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
  "processing_ms": 640
}
```

`lines` are in reading order, `confidence` is the mean Tesseract word confidence for the line (0–100), and `dropped_words` counts the words the service filtered out for low confidence. Any non-2xx status is shown to the user as a service error.
