# ClearSign OCR service

FastAPI service that turns a photo of a sign into lines of text. OpenCV cleans the image up and Tesseract reads it. The pipeline was tuned against a benchmark of real sign photos and synthetic degraded signs; see [Accuracy](#accuracy) for the numbers and how to reproduce them.

## Requirements

- Python 3.12
- Tesseract 5 (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian/Ubuntu)
- The `tessdata_best` English model, fetched by `scripts/fetch_tessdata.sh` (about 15 MB). Package managers install the smaller integer `tessdata_fast` model, which the benchmark showed to be measurably less accurate; the service falls back to it if the download is skipped.

## Run locally

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
sh scripts/fetch_tessdata.sh
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The client's dev server proxies `/api` here. Interactive docs are at http://localhost:8000/docs.

## Tests

```sh
.venv/bin/pytest
```

The tests render synthetic signs with Pillow (straight, tilted, light-on-dark, in cluttered scenes) and run them through the real pipeline, so they need Tesseract installed.

## Pipeline

Recognition runs in two passes so that a sign photographed in a cluttered scene is read the way a scan would be.

**Pass 1, detect.** The grayscale photo is bounded to 1600 px and Tesseract runs in sparse-text mode over the whole thing. Even when it misreads, the boxes of its confident words say where the text is, how tall it is, whether the ink is lighter than its background, and how the baselines are tilted. The region is seeded from the surest words (confidence 88 or more, three or more characters) and grown only to reliable neighbours of a plausible size, so junk read in grass or brickwork cannot stretch it across the photo. If fewer than three reliable words turn up, the pass is retried at 2600 px (phone photos are 4000 px wide and small print vanishes at 1600), and if nothing reliable reads at all it is retried at 90, 180 and 270 degrees for photos stored sideways.

**Pass 2, read.** The region around those words is cropped from the full-resolution photo and prepared with OpenCV:

1. **Perspective**: the largest convex quadrilateral (the sign) is warped flat. The unwarped crop is also read, so a wrong quadrilateral cannot lose the text.
2. **Scale** so the typical glyph is 50 px tall, the height at which Tesseract's LSTM reads best.
3. **Bilateral denoise** and an **unsharp mask**, which smooth JPEG noise while keeping stroke edges.
4. **Polarity**: light-on-dark signs are inverted so text is always dark on light.
5. **Adaptive Gaussian threshold** (61 px window) for the binarised candidate; the cleaned grayscale is kept as a second candidate because Tesseract's own thresholding often does better on clean signs.
6. **Deskew** by the pass-1 baseline angle (blob-fitting as a fallback), then threshold again.

Tesseract reads the grayscale and binary candidates in block mode; if fewer than three confident words come back it also tries column mode and sparse mode, and the opposite polarity when the read is weak. A binarised crop with more than 3,000 connected components is texture rather than text and is skipped, which is what keeps foliage and stone walls from costing ten seconds. Every candidate's words are mapped back to photo coordinates through the exact inverse of the geometry applied to them.

**Merge.** Rather than crowning one candidate, confident words from all candidates (including pass 1) are merged geometrically: words are accepted in order of confidence and a word whose box overlaps an accepted one is dropped, so misreads of the same word lose to better reads and a line one candidate missed is filled in from another. Signs that mix a large title with small print depend on this. Accepted words are clustered into lines in the level frame of the candidate that contributed most of them, which keeps rows intact under tilt and keystone distortion.

**Filtering.** Words below the confidence threshold (70) are dropped and counted, as are punctuation-only "words" and one- or two-letter words under 80, which is what clutter usually reads as.

## Accuracy

`bench/` holds a benchmark and every knob above is an option, so changes can be measured rather than guessed. Metrics are character error rate (CER, lower is better), word F1, and the share of ground-truth lines reproduced exactly.

| Set | Pipeline | CER | Word F1 | Line recall | Photos fully correct |
| --- | --- | --- | --- | --- | --- |
| 19 real photos | first version | 1.228 | 0.397 | 0.232 | 5% |
| 19 real photos | current | **0.339** | **0.631** | **0.466** | **16%** |
| 150 synthetic (seed 2, held out) | first version | 0.177 | 0.820 | 0.740 | 67% |
| 150 synthetic (seed 2, held out) | current | **0.109** | **0.908** | **0.835** | **77%** |
| 120 synthetic (seed 1, tuning set) | first version | 0.204 | 0.801 | 0.724 | 63% |
| 120 synthetic (seed 1, tuning set) | current | **0.064** | **0.929** | **0.875** | **80%** |
| 19 real photos resized to 3000 px | first version | 0.813 | 0.272 | 0.127 | 0% |
| 19 real photos resized to 3000 px | current | **0.243** | **0.658** | **0.464** | **11%** |

A CER above 1 means the output was mostly junk. The first version's real-photo output was largely punctuation and fragments; the current pipeline reads twelve of the nineteen photos with a CER of 0.35 or better. The hardest remaining cases are cast-metal relief lettering, a dot-matrix departure board, hand-painted wood, and leaves occluding letters.

Median processing time is about 0.35 s for synthetic images, 1.2 s for 1600 px real photos and 1.3 s for 3000 px photos on an Apple M-series laptop, against 0.19 s and 0.8 s for the first version. The slowest photo (a low-contrast carved sign in tall grass) takes about 5 s at 3000 px.

### Full-resolution photos

The ClearSign client sends 1920 px camera frames, but the API accepts any image, and a photo straight from a phone's library is 12 megapixels, often stored sideways with an orientation tag, and sometimes HEIC. The first version of the pipeline scored a CER of 0.81 on such inputs. Now the detection pass retries at higher resolution and at other orientations when little reads, a texture guard keeps cluttered backgrounds from costing seconds, and `pillow-heif` decodes HEIC. Use `--upscale 3000` (or 4000) with the benchmark to reproduce that case.

What the benchmark showed, in order of impact:

1. Detecting the text region first and reading only that, at the right scale (real-photo CER 1.47 to 0.33 on the initial ten photos).
2. Perspective correction with the flat crop as a fallback.
3. Reading grayscale as well as the binarised image, and letting Tesseract try inverted lines itself.
4. The `tessdata_best` model over `tessdata_fast`.
5. The geometric merge of candidates, especially on signs with mixed text sizes.
6. Glyph height 50 px rather than 40, unsharp masking, a confidence threshold of 70, and the short-word rule.

Things that did not help and were left out: CLAHE, non-local-means or median denoising, smaller threshold windows, adding a white border, a blurred candidate for dot-matrix displays, a 1200 px detection pass, a second read scaled for small print, and a 4000 px read-pass bound (2600 px is as accurate and faster).

### Running the benchmark

```sh
.venv/bin/python -m bench.fetch_real                      # downloads the real photos (Wikimedia Commons, CC licensed)
.venv/bin/python -m bench.run --variants baseline,defaults --n 150 --seed 2 --real bench/real/manifest.json
.venv/bin/python -m bench.run --variants defaults --set preprocess.target_text_height=60 --show-misses 5
.venv/bin/python -m bench.inspect bench/real/reston.jpg --draw /tmp/boxes.png   # every candidate's words for one photo
```

`bench/run.py` lists the named variants; any option can be overridden with `--set section.name=value`. Synthetic sets are generated deterministically from the seed and cached under `bench/.cache/`. The real photos are listed in `bench/real/manifest.json` with their ground truth, source page, author and licence.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OCR_MIN_CONFIDENCE` | `70` | Words below this confidence (0–100) are discarded |
| `OCR_LANGUAGE` | `eng` | Tesseract language pack(s), e.g. `eng+spa` |
| `OCR_PSM` | benchmarked set | Force a single page segmentation mode |
| `OCR_TESSDATA_DIR` | `./tessdata` if present | Directory holding `*.traineddata` |
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

`GET /api/health` reports the Tesseract version and which model directory is in use.

## Docker

```sh
docker build -t clearsign-ocr backend
docker run -p 8000:8000 clearsign-ocr
```

The image installs Tesseract and downloads the `tessdata_best` model at build time.
