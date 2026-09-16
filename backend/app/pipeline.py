"""End-to-end recognition in two passes.

Pass 1 (detect): Tesseract runs in sparse-text mode on a bounded-size grayscale
copy of the whole photo. Even when it misreads, its word boxes tell us where
the text is and how tall it is.

Pass 2 (read): the region around those words is cropped from the full-
resolution image, scaled so glyphs are the height Tesseract reads best,
cleaned, deskewed, and recognised from both grayscale and binarised versions.
The best-scoring result wins, with pass 1 itself as a fallback candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import cv2
import numpy as np

from .ocr import DEFAULT_OCR_OPTIONS, Candidate, OcrOptions, Recognition, Word, map_boxes, merge, recognize, run_tesseract, unite
from .preprocess import (DEFAULT_OPTIONS, Preprocessed, PreprocessOptions, _resize, denoise, estimate_skew,
                         estimate_text_height, preprocess_gray, threshold)


@dataclass(frozen=True)
class PipelineOptions:
    preprocess: PreprocessOptions = field(default_factory=PreprocessOptions)
    ocr: OcrOptions = field(default_factory=OcrOptions)
    # Which prepared images to offer Tesseract in pass 2, in order: gray, binary.
    inputs: tuple[str, ...] = ("gray", "binary")
    # Also try the opposite polarity when the read pass is weak.
    polarity_retry: bool = True
    # Pass 1 settings.
    detect: bool = True
    detect_long_side: int = 1600
    detect_psm: int = 11
    detect_min_confidence: float = 40.0
    # Region margin around detected words, as a multiple of the median word height.
    margin_factor: float = 1.5
    # Which percentile of detected word heights sets the scale (median = 50).
    height_percentile: float = 50.0
    # Add a smoothed candidate that merges dot-matrix and segmented glyphs.
    smooth_candidate: bool = False
    # When perspective correction found a quadrilateral, also read the
    # uncorrected crop and keep whichever scores better.
    perspective_fallback: bool = True
    # Words this confident (and at least two characters) define the region,
    # text height, skew and polarity; junk from textures rarely qualifies.
    reliable_confidence: float = 70.0
    # The region is seeded from words this confident (three or more
    # characters) and grown only to reliable words next to it, so junk read
    # in grass or brickwork cannot stretch it across the photo.
    seed_confidence: float = 88.0
    # When pass 1 finds fewer than this many reliable words, retry it at
    # detect_retry_long_side (phone photos are 4000 px; small text vanishes
    # at 1600) and then at 90/180/270 degrees for photos stored sideways.
    rescue_min_words: int = 3
    detect_retry_long_side: int = 2600
    # Other orientations are tried only when nothing reliable reads upright;
    # a one-word sign must not pay for three extra detection passes.
    orientation_rescue: bool = True
    orientation_rescue_max_words: int = 0
    # A binarised crop with more connected components than this is texture
    # (grass, brick, foliage); Tesseract would spend seconds on it, so only
    # the grayscale candidate is read.
    max_binary_components: int = 3000
    # Estimate skew from the detected word baselines instead of ink blobs.
    skew_from_words: bool = True
    # words | blobs | agree: which estimate levels the crop. "agree" averages
    # the two when they roughly match and otherwise takes the smaller one.
    skew_source: str = "words"
    # Decide light-on-dark from pixel statistics inside detected words.
    polarity_from_words: bool = True
    # When detected word heights span more than multi_scale_ratio, read the
    # crop a second time scaled for the small text; the union merges both.
    multi_scale: bool = False
    multi_scale_ratio: float = 2.2


DEFAULT_PIPELINE = PipelineOptions(preprocess=DEFAULT_OPTIONS, ocr=DEFAULT_OCR_OPTIONS)


@dataclass
class Detection:
    words: list[Word]
    region: tuple[int, int, int, int] | None
    """(x0, y0, x1, y1) in full-resolution pixels, or None when nothing was found."""
    text_height: float | None
    """Typical word height in full-resolution pixels."""
    scale: float
    skew_degrees: float | None = None
    """Skew of the detected lines, or None when too few lines were found."""
    inverted: bool | None = None
    """Light text on dark background, judged inside the detected words."""
    small_text_height: float | None = None
    """20th percentile of reliable word heights, for a second read of small print."""
    reliable_count: int = 0
    """How many words met the reliability bar; low counts trigger the rescues."""
    rotation: int = 0
    """Degrees the photo was rotated (0, 90, 180, 270) before reading."""


@dataclass
class PipelineResult:
    recognition: Recognition
    prepared: Preprocessed
    detection: Detection | None = None


def detect_text(gray: np.ndarray, options: PipelineOptions) -> Detection:
    """Pass 1 with rescues: a larger detection image, then other orientations."""
    detection = _detect_at(gray, options, options.detect_long_side)
    height, width = gray.shape[:2]
    if (detection.reliable_count < options.rescue_min_words
            and options.detect_retry_long_side > options.detect_long_side
            and max(height, width) > options.detect_long_side * 1.25):
        bigger = _detect_at(gray, options, options.detect_retry_long_side)
        if bigger.reliable_count > detection.reliable_count:
            detection = bigger
    if detection.reliable_count <= options.orientation_rescue_max_words and options.orientation_rescue:
        # Adopt another orientation only on clear evidence: a sideways photo
        # reads nothing upright and several words when turned, while junk
        # from texture rarely produces three reliable words in any direction.
        for rotation, code in ((90, cv2.ROTATE_90_CLOCKWISE), (270, cv2.ROTATE_90_COUNTERCLOCKWISE), (180, cv2.ROTATE_180)):
            turned = _detect_at(cv2.rotate(gray, code), options, options.detect_long_side)
            if turned.reliable_count >= options.rescue_min_words and turned.reliable_count > 2 * detection.reliable_count:
                turned.rotation = rotation
                detection = turned
    return detection


def _detect_at(gray: np.ndarray, options: PipelineOptions, long_side: int) -> Detection:
    height, width = gray.shape[:2]
    scale = min(1.0, long_side / max(height, width))
    small = _resize(gray, scale) if scale < 1.0 else gray
    small = denoise(small, "gaussian")
    words = run_tesseract(small, options.detect_psm, options.ocr)
    map_boxes(words, np.diag([1.0 / scale, 1.0 / scale, 1.0]))
    good = [w for w in words if w.confidence >= options.detect_min_confidence and w.alphanumeric]
    if not good:
        return Detection(words=words, region=None, text_height=None, scale=scale)

    # Prefer clearly-read words for every geometric decision; fall back to
    # everything only when the sign is barely legible at detection size.
    reliable = [w for w in good if w.confidence >= options.reliable_confidence and w.alnum_length >= 2]
    basis = reliable if len(reliable) >= 2 else good
    region_words = _grow_region(basis, options)

    heights = np.array([w.height for w in region_words], dtype=np.float32) / scale
    text_height = float(np.percentile(heights, options.height_percentile))
    small_text_height = float(np.percentile(heights, 20))
    margin = int(options.margin_factor * text_height)
    x0 = max(0, int(min(w.left for w in region_words) / scale) - margin)
    y0 = max(0, int(min(w.top for w in region_words) / scale) - margin)
    x1 = min(width, int(max(w.left + w.width for w in region_words) / scale) + margin)
    y1 = min(height, int(max(w.top + w.height for w in region_words) / scale) + margin)

    skew = skew_from_words(region_words) if options.skew_from_words else None
    inverted = polarity_from_words(small, region_words) if options.polarity_from_words else None
    return Detection(words=words, region=(x0, y0, x1, y1), text_height=text_height, scale=scale,
                     skew_degrees=skew, inverted=inverted, small_text_height=small_text_height,
                     reliable_count=len(reliable))


def _grow_region(basis: list[Word], options: PipelineOptions) -> list[Word]:
    """Seeds the region with the surest words and grows it to reliable neighbours."""
    seeds = [w for w in basis if w.confidence >= options.seed_confidence and w.alnum_length >= 3]
    if len(seeds) < 2:
        return basis
    chosen = list(seeds)
    seed_height = float(np.median([w.height for w in seeds]))
    # Only words of a plausible size may join: texture reads as tiny or odd-sized words.
    remaining = [w for w in basis if w not in chosen and 0.25 * seed_height <= w.height <= 4.0 * seed_height]
    for _ in range(3):
        if not remaining:
            break
        reach = 2.0 * float(np.median([w.height for w in chosen]))
        x0 = min(w.left for w in chosen) - reach
        y0 = min(w.top for w in chosen) - reach
        x1 = max(w.left + w.width for w in chosen) + reach
        y1 = max(w.top + w.height for w in chosen) + reach
        near = [w for w in remaining
                if w.left + w.width >= x0 and w.left <= x1 and w.top + w.height >= y0 and w.top <= y1]
        if not near:
            break
        chosen.extend(near)
        remaining = [w for w in remaining if w not in near]
    return chosen


def skew_from_words(words: list[Word]) -> float | None:
    """Median baseline angle between horizontally adjacent words, in degrees.

    Sparse-mode line numbers can lump distant words together, so only pairs
    that are neighbours (small gap, similar height) contribute, weighted by
    their horizontal span. A tilted word's axis-aligned box touches the
    baseline at its lower end only, so the run is measured between left
    edges for rising text and right edges for falling text. Negative means
    the text rises to the right; `preprocess.rotate` by this angle levels it.
    """
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for w in words:
        lines.setdefault((w.block, w.paragraph, w.line), []).append(w)
    angles, weights = [], []
    for members in lines.values():
        members = sorted(members, key=lambda w: w.left)
        for a, b in zip(members, members[1:]):
            height = max(a.height, b.height)
            gap = b.left - (a.left + a.width)
            if gap > 3 * height or gap < -0.5 * height or min(a.height, b.height) < 0.6 * height:
                continue
            dy = (b.top + b.height) - (a.top + a.height)  # box bottoms
            dx = (b.left - a.left) if dy < 0 else ((b.left + b.width) - (a.left + a.width))
            if dx < 1.5 * height:
                continue
            angles.append(float(np.degrees(np.arctan2(dy, dx))))
            weights.append(dx)
    if not angles:
        return None
    order = np.argsort(angles)
    cumulative = np.cumsum(np.array(weights)[order])
    median_index = order[int(np.searchsorted(cumulative, cumulative[-1] / 2))]
    return float(np.clip(angles[median_index], -20, 20))


def combine_skew(from_words: float | None, from_blobs: float, tolerance: float = 2.5) -> float:
    """Reconciles the two skew estimates: agree -> average, disagree -> the smaller correction."""
    if from_words is None:
        return from_blobs
    if abs(from_words - from_blobs) <= tolerance:
        return (from_words + from_blobs) / 2.0
    return from_words if abs(from_words) < abs(from_blobs) else from_blobs


def polarity_from_words(gray: np.ndarray, words: list[Word]) -> bool | None:
    """True when the ink inside the detected words is lighter than its surroundings."""
    votes = []
    for w in words:
        x0, y0 = max(0, w.left), max(0, w.top)
        x1, y1 = min(gray.shape[1], w.left + w.width), min(gray.shape[0], w.top + w.height)
        patch = gray[y0:y1, x0:x1]
        if patch.size < 50:
            continue
        threshold_value, _ = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        dark = patch[patch <= threshold_value]
        light = patch[patch > threshold_value]
        if dark.size == 0 or light.size == 0:
            continue
        # Text strokes cover less of a word box than its background does.
        votes.append(dark.size > light.size)  # light pixels are the minority -> light ink
    if not votes:
        return None
    return sum(votes) > len(votes) / 2


def smooth(gray: np.ndarray, text_height: float) -> np.ndarray:
    """Blurs just enough to fuse the dots of a matrix display into strokes."""
    sigma = max(0.8, text_height / 14.0)
    return cv2.GaussianBlur(gray, (0, 0), sigma)


def run(bgr: np.ndarray, options: PipelineOptions = DEFAULT_PIPELINE) -> PipelineResult:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    detection: Detection | None = None
    crop = gray
    offset = (0, 0)
    text_height: float | None = None
    skew: float | None = None
    inverted: bool | None = None
    if options.detect:
        detection = detect_text(gray, options)
        if detection.rotation:
            # The photo was stored sideways; work in the orientation that read.
            code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[detection.rotation]
            gray = cv2.rotate(gray, code)
            crop = gray
        if detection.region:
            x0, y0, x1, y1 = detection.region
            crop = gray[y0:y1, x0:x1]
            offset = (x0, y0)
            text_height = detection.text_height
            skew = detection.skew_degrees
            inverted = detection.inverted

    if text_height is None:
        text_height = estimate_text_height(crop)
    scale = None
    if text_height:
        scale = float(np.clip(options.preprocess.target_text_height / text_height,
                              options.preprocess.min_scale, options.preprocess.max_scale))
        scale = min(scale, options.preprocess.max_long_side / max(crop.shape[:2]))

    if options.skew_source != "words":
        blob_skew = estimate_skew(threshold(_resize(crop, scale) if scale else crop, options.preprocess))
        skew = blob_skew if options.skew_source == "blobs" else combine_skew(skew, blob_skew)

    prepared = preprocess_gray(crop, options.preprocess, invert=inverted, scale=scale, skew=skew)
    recognition = recognize(_candidates(prepared, options, offset=offset), options.ocr)
    chosen = prepared

    if prepared.perspective_corrected and options.perspective_fallback:
        # A wrongly detected quadrilateral would crop the text away; the flat
        # crop competes on equal terms.
        plain = preprocess_gray(crop, replace(options.preprocess, perspective=False), invert=inverted, scale=scale, skew=skew)
        plain_recognition = recognize(_candidates(plain, options, "flat-", offset=offset), options.ocr)
        recognition = merge(recognition, plain_recognition, options=options.ocr)
        if recognition.candidate.startswith("flat-"):
            chosen = plain

    if options.polarity_retry and not _strong(recognition):
        flipped = preprocess_gray(crop, options.preprocess, invert=not prepared.inverted, scale=scale, skew=skew)
        flipped_recognition = recognize(_candidates(flipped, options, "inverted-", offset=offset), options.ocr)
        recognition = merge(recognition, flipped_recognition, options=options.ocr)
        if recognition.candidate.startswith("inverted-"):
            chosen = flipped

    if (options.multi_scale and detection and detection.small_text_height and text_height
            and text_height / detection.small_text_height >= options.multi_scale_ratio):
        # Titles and small print on one sign: a second read scaled for the small print.
        small_scale = float(np.clip(options.preprocess.target_text_height / detection.small_text_height,
                                    options.preprocess.min_scale, options.preprocess.max_scale))
        small_scale = min(small_scale, options.preprocess.max_long_side / max(crop.shape[:2]))
        small = preprocess_gray(crop, replace(options.preprocess, perspective=False), invert=prepared.inverted,
                                scale=small_scale, skew=skew)
        small_recognition = recognize([_candidates(small, options, "small-", offset=offset)[0]], options.ocr)
        recognition = merge(recognition, small_recognition, options=options.ocr)

    if detection and detection.words:
        # Pass 1 read the whole photo; it competes with the focused read.
        first_pass = Recognition(lines=[], dropped_words=0, candidate=f"detect/psm{options.detect_psm}",
                                 words=detection.words, raw=[(f"detect/psm{options.detect_psm}", detection.words)])
        recognition = merge(recognition, first_pass, options=options.ocr)

    if options.ocr.union:
        level = skew if skew is not None else chosen.skew_degrees
        united = unite(recognition.raw, options.ocr, skew_degrees=-level)
        if united.lines:
            recognition = united

    return PipelineResult(recognition=recognition, prepared=chosen, detection=detection)


def _candidates(prepared: Preprocessed, options: PipelineOptions, label: str = "",
                offset: tuple[int, int] = (0, 0)) -> list[Candidate]:
    images = {"gray": prepared.gray, "binary": prepared.binary}
    if "binary" in images and options.max_binary_components:
        components, _ = cv2.connectedComponents(cv2.bitwise_not(prepared.binary), connectivity=8)
        if components > options.max_binary_components:
            del images["binary"]
    shift = np.array([[1, 0, offset[0]], [0, 1, offset[1]], [0, 0, 1]], dtype=np.float64)
    transform = shift @ prepared.transform
    candidates = [Candidate(f"{label}{name}", images[name], transform) for name in options.inputs if name in images]
    if options.smooth_candidate:
        candidates.append(Candidate(f"{label}smooth", smooth(prepared.gray, options.preprocess.target_text_height), transform))
    return candidates


def _strong(recognition: Recognition) -> bool:
    """A read with several confident words does not need the polarity retry."""
    confident = [w for w in recognition.words if w.alphanumeric and w.confidence >= 80]
    return len(confident) >= 3
