# ClearSign

ClearSign is an accessibility web app for people with low vision. Point a phone camera at real-world signage, a menu, or a label, and ClearSign re-presents the text enlarged, in a high-contrast colour scheme of your choosing, and reads it aloud.

## How it works

1. The React client captures a frame from the browser camera and posts it to the API. Each capture opens in its own tab, so earlier signs stay a tap away.
2. The FastAPI service locates the text with a first Tesseract pass, then preprocesses that region with OpenCV (perspective correction, rescaling, denoising, adaptive thresholding, deskewing) and reads it with Tesseract, merging the reads of several candidate images and discarding words below a confidence threshold. The pipeline is tuned with a benchmark of real and synthetic sign photos; see `backend/README.md`.
3. The client renders the recognised lines in the reader, where text size, typeface, line and letter spacing, weight, and colour theme are all adjustable and apply to the whole interface, and the Web Speech API reads the lines aloud with the current word highlighted.

## Repository layout

| Path | Contents |
| --- | --- |
| `frontend/` | React + TypeScript client (Vite) |
| `backend/` | FastAPI + OpenCV + Tesseract service, with its accuracy benchmark in `backend/bench/` |

## Setup

### 1. Prerequisites

| Tool | Version | Install |
| --- | --- | --- |
| Node.js | 20 or newer | https://nodejs.org |
| Python | 3.12 | `brew install python@3.12` on macOS, `apt install python3.12 python3.12-venv` on Debian/Ubuntu |
| Tesseract | 5.x with English data | `brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian/Ubuntu |

Check them with `node --version`, `python3.12 --version` and `tesseract --version`.

### 2. Get the code

```sh
git clone <this repository> ClearSign
cd ClearSign
```

### 3. Set up the OCR service

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
sh scripts/fetch_tessdata.sh
```

The last step downloads the 15 MB `tessdata_best` English model into `backend/tessdata/`. It is more accurate than the model package managers install; the service falls back to the system model if the download is skipped.

Start the service:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Confirm it is up by opening http://localhost:8000/api/health, which reports the Tesseract version and the model in use. The root URL http://localhost:8000/ has no page and answers `{"detail":"Not Found"}`; the interactive API docs are at http://localhost:8000/docs.

### 4. Set up the client

In a second terminal:

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the service on port 8000. Allow camera access when the browser asks, press **Turn on camera**, point it at a sign and press **Capture** (or the Space bar).

### 5. Try it on a phone

Browsers only expose the camera on secure pages, so a phone on the same network cannot use the plain `http://<your-ip>:5173` address. Two options:

- **Tunnel:** start the client with `npm run dev -- --host`, then expose port 5173 with an HTTPS tunnel such as `npx localtunnel --port 5173` or ngrok, and open the tunnel's `https://` URL on the phone. The `/api` proxy keeps working through the tunnel.
- **Local HTTPS:** generate a certificate with [mkcert](https://github.com/FiloSottile/mkcert) and add `server: { https: { key, cert }, host: true }` to `frontend/vite.config.ts`.

### 6. Run the tests

```sh
cd backend && .venv/bin/pytest          # renders synthetic signs and runs them through the real pipeline
cd frontend && npx tsc -b && npm run lint
```

### Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| A yellow "Sample text · recognition service is offline" chip in the reader | The client could not reach port 8000, so it showed built-in sample text. Start the service (step 3). |
| "The text recognition service returned an error (HTTP 502)" in production | The reverse proxy in front of the client is not forwarding `/api` to the service. |
| "Camera access was blocked" | Allow the camera for this site in the browser's site settings, then press **Try camera again**. |
| Camera never appears on a phone | The page is not being served over HTTPS; see step 5. |
| `pytest` fails with `TesseractNotFoundError` | Tesseract is not on `PATH`; reinstall it (step 1) or set `TESSDATA_PREFIX`. |

### Production

Build the client with `npm run build` in `frontend/` and serve `frontend/dist/` from any static host, with `/api` reverse-proxied to the service. `backend/Dockerfile` builds a container that installs Tesseract, downloads the model and runs the service on port 8000; set `CORS_ORIGINS` to the client's origin if they are served from different hosts.

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
