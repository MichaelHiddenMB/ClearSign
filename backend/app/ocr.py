"""Tesseract recognition: runs candidates, scores them, and filters words by confidence."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

PSM_SPARSE_TEXT = 11

# `scripts/fetch_tessdata.sh` downloads the tessdata_best English model here.
BUNDLED_TESSDATA = Path(__file__).resolve().parent.parent / "tessdata"


def default_tessdata_dir() -> str | None:
    """Prefers OCR_TESSDATA_DIR, then the bundled tessdata_best model, then Tesseract's own."""
    override = os.environ.get("OCR_TESSDATA_DIR")
    if override:
        return override
    if (BUNDLED_TESSDATA / "eng.traineddata").exists():
        return str(BUNDLED_TESSDATA)
    return None


@dataclass(frozen=True)
class OcrOptions:
    language: str = "eng"
    # Words below this Tesseract confidence (0-100) are discarded from the output.
    min_confidence: float = 70.0
    # Page segmentation modes to try for every candidate image.
    psms: tuple[int, ...] = (6,)
    # OCR engine mode: 1 = LSTM only, 3 = default.
    oem: int = 3
    # Directory holding *.traineddata; None uses Tesseract's default.
    tessdata_dir: str | None = field(default_factory=default_tessdata_dir)
    # Let Tesseract also try inverted text line by line; on grayscale input
    # this is what copes with a light sign carrying a dark band of text.
    do_invert: bool = True
    # Declared DPI for images without metadata.
    dpi: int = 300
    # Short alphabetic words (1-2 letters) need this much confidence; clutter
    # often reads as "a", "i" or "oe". 0 disables the rule.
    short_word_min_confidence: float = 80.0
    # Merge words from every candidate by position instead of keeping one
    # candidate; words below union_min_confidence never take part, and
    # single characters need union_single_char_min_confidence.
    union: bool = True
    union_min_confidence: float = 75.0
    union_single_char_min_confidence: float = 85.0
    # Extra segmentation modes tried in order on the primary candidate while
    # fewer than fallback_min_words confident words have been read.
    fallback_psms: tuple[int, ...] = (4, PSM_SPARSE_TEXT)
    fallback_min_words: int = 3
    # How to pick between candidate results: mean | sum | confident | guarded
    # (guarded = best mean confidence among candidates that read at least
    # `guard_fraction` as many confident words as the most productive one).
    select: str = "guarded"
    guard_fraction: float = 0.5
    # Stop trying further candidates once one scores at least this well
    # (mean word confidence); 101 disables early exit.
    early_exit_confidence: float = 90.0


DEFAULT_OCR_OPTIONS = OcrOptions()


@dataclass
class Word:
    text: str
    confidence: float
    block: int
    paragraph: int
    line: int
    left: int
    top: int
    width: int
    height: int
    box: tuple[float, float, float, float] | None = None
    """(x0, y0, x1, y1) bounding box in photo coordinates, once mapped through the candidate's transform."""
    quad: np.ndarray | None = None
    """4x2 corners of the word box in photo coordinates (a rotated rectangle when the candidate was deskewed)."""
    transform: np.ndarray | None = None
    """The candidate transform the quad was mapped through (shared by all words of a candidate)."""

    @property
    def alnum_length(self) -> int:
        return sum(ch.isalnum() for ch in self.text)

    @property
    def alphanumeric(self) -> bool:
        """False for "words" made only of punctuation, which are almost always clutter."""
        return any(ch.isalnum() for ch in self.text)


@dataclass
class RecognisedLine:
    text: str
    confidence: float


@dataclass
class Recognition:
    lines: list[RecognisedLine]
    dropped_words: int
    candidate: str = ""
    """Label of the candidate image/psm that produced this result."""
    words: list[Word] = field(default_factory=list, repr=False)
    raw: list[tuple[str, list[Word]]] = field(default_factory=list, repr=False)
    """Every (label, words) result that competed for this recognition."""


@dataclass
class Candidate:
    label: str
    image: np.ndarray
    transform: np.ndarray | None = None
    """3x3 matrix mapping candidate pixels to photo pixels; None means identity."""


def map_boxes(words: list[Word], transform: np.ndarray | None) -> None:
    """Fills each word's photo-coordinate quad and bounding box using the candidate transform."""
    matrix = np.eye(3) if transform is None else transform
    for w in words:
        corners = np.array([[w.left, w.top, 1], [w.left + w.width, w.top, 1],
                            [w.left + w.width, w.top + w.height, 1], [w.left, w.top + w.height, 1]], dtype=np.float64)
        mapped = corners @ matrix.T
        mapped = mapped[:, :2] / np.maximum(mapped[:, 2:3], 1e-9)
        w.quad = mapped.astype(np.float32)
        w.box = (float(mapped[:, 0].min()), float(mapped[:, 1].min()), float(mapped[:, 0].max()), float(mapped[:, 1].max()))
        w.transform = matrix


def run_tesseract(image: np.ndarray, psm: int, options: OcrOptions = DEFAULT_OCR_OPTIONS) -> list[Word]:
    """Runs Tesseract once and returns its words with confidences and positions."""
    config = (
        f"--oem {options.oem} --psm {psm} "
        f"-c tessedit_do_invert={int(options.do_invert)} -c user_defined_dpi={options.dpi}"
    )
    if options.tessdata_dir:
        config += f' --tessdata-dir "{options.tessdata_dir}"'
    data = pytesseract.image_to_data(image, lang=options.language, config=config, output_type=Output.DICT)
    return words_from_data(data)


def words_from_data(data: dict) -> list[Word]:
    """Keeps only real word rows; Tesseract reports confidence -1 for layout rows."""
    words = []
    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        words.append(
            Word(
                text=text,
                confidence=conf,
                block=int(data["block_num"][i]),
                paragraph=int(data["par_num"][i]),
                line=int(data["line_num"][i]),
                left=int(data["left"][i]) if "left" in data else 0,
                top=int(data["top"][i]) if "top" in data else 0,
                width=int(data["width"][i]) if "width" in data else 0,
                height=int(data["height"][i]) if "height" in data else 0,
            )
        )
    return words


def group_words(data_or_words, *, min_confidence: float, short_word_min_confidence: float = 0.0) -> Recognition:
    """Groups words into lines in reading order, dropping junk and low-confidence words."""
    words = data_or_words if isinstance(data_or_words, list) else words_from_data(data_or_words)
    lines: dict[tuple[int, int, int], list[Word]] = {}
    order: list[tuple[int, int, int]] = []
    dropped = 0
    for word in words:
        if not word.alphanumeric:
            continue
        if word.confidence < min_confidence:
            dropped += 1
            continue
        if short_word_min_confidence and len(word.text) <= 2 and word.text.isalpha() and word.confidence < short_word_min_confidence:
            dropped += 1
            continue
        key = (word.block, word.paragraph, word.line)
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(word)

    recognised = [
        RecognisedLine(
            text=" ".join(w.text for w in lines[key]),
            confidence=round(sum(w.confidence for w in lines[key]) / len(lines[key]), 1),
        )
        for key in order
    ]
    return Recognition(lines=recognised, dropped_words=dropped, words=words)


def score(words: list[Word], method: str, min_confidence: float) -> float:
    """Ranks a single candidate result; higher is better."""
    words = [w for w in words if w.alphanumeric]
    if not words:
        return 0.0
    confs = np.array([w.confidence for w in words])
    if method == "mean":
        return float(confs.mean())
    if method == "sum":
        return float(confs.sum())
    # "confident" (and the per-candidate part of "guarded"): number of
    # trustworthy words, with mean confidence as tie-break.
    return float((confs >= min_confidence).sum() + confs.mean() / 101.0)


def choose(results: list[tuple[str, list[Word]]], options: OcrOptions) -> int:
    """Index of the best candidate under the selection rule."""
    if not results:
        raise ValueError("no candidates")
    if options.select != "guarded":
        return max(range(len(results)), key=lambda i: score(results[i][1], options.select, options.min_confidence))
    counts = [sum(1 for w in words if w.alphanumeric and w.confidence >= options.min_confidence) for _, words in results]
    means = [score(words, "mean", options.min_confidence) for _, words in results]
    floor = options.guard_fraction * max(counts)
    eligible = [i for i in range(len(results)) if counts[i] >= floor]
    return max(eligible, key=lambda i: (means[i], counts[i]))


def build(results: list[tuple[str, list[Word]]], options: OcrOptions) -> Recognition:
    """Selects the best candidate from a pool and groups it into lines."""
    index = choose(results, options)
    label, words = results[index]
    recognition = group_words(words, min_confidence=options.min_confidence,
                              short_word_min_confidence=options.short_word_min_confidence)
    recognition.candidate = label
    recognition.raw = list(results)
    return recognition


def merge(*recognitions: Recognition, options: OcrOptions) -> Recognition:
    """Re-selects across the raw candidates of several recognitions."""
    pool: list[tuple[str, list[Word]]] = []
    for r in recognitions:
        pool.extend(r.raw or [(r.candidate, r.words)])
    return build(pool, options)


def _confident_count(words: list[Word], options: OcrOptions) -> int:
    return sum(1 for w in words if w.alphanumeric and w.confidence >= options.min_confidence)


def recognize(
    candidates: list,
    options: OcrOptions = DEFAULT_OCR_OPTIONS,
) -> Recognition:
    """Runs every candidate image with every segmentation mode and keeps the best.

    Candidates are Candidate objects (or (label, image) pairs), most promising
    first, so early exit saves time on easy photos. When the primary modes
    read only a few words, the fallback modes get a turn on the first
    candidate: block mode (6) fails outright on some layouts that column
    mode (4) or sparse mode (11) handle.
    """
    candidates = [c if isinstance(c, Candidate) else Candidate(c[0], c[1]) for c in candidates]
    results: list[tuple[str, list[Word]]] = []
    for candidate in candidates:
        for psm in options.psms:
            words = run_tesseract(candidate.image, psm, options)
            map_boxes(words, candidate.transform)
            results.append((f"{candidate.label}/psm{psm}", words))
            real_words = [w for w in words if w.alphanumeric]
            if real_words and float(np.mean([w.confidence for w in real_words])) >= options.early_exit_confidence:
                return build(results, options)

    if candidates:
        first = candidates[0]
        for psm in options.fallback_psms:
            if max((_confident_count(words, options) for _, words in results), default=0) >= options.fallback_min_words:
                break
            words = run_tesseract(first.image, psm, options)
            map_boxes(words, first.transform)
            results.append((f"{first.label}/psm{psm}", words))
    return build(results, options)


# --- geometric union of candidates -------------------------------------------


def _polygon_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def _clip(subject: np.ndarray, clipper: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman clipping of one convex polygon by another.

    OpenCV's intersectConvexConvex returns 0 for polygons that share edges,
    which is exactly the case for the same word read from two candidates.
    """
    # Orient the clipper consistently so "inside" is well defined.
    if np.dot(clipper[:, 0], np.roll(clipper[:, 1], -1)) - np.dot(clipper[:, 1], np.roll(clipper[:, 0], -1)) < 0:
        clipper = clipper[::-1]
    output = [tuple(p) for p in subject]
    for i in range(len(clipper)):
        edge_start, edge_end = clipper[i], clipper[(i + 1) % len(clipper)]
        if not output:
            break
        polygon, output = output, []
        ex, ey = edge_end[0] - edge_start[0], edge_end[1] - edge_start[1]

        def inside(p):
            return ex * (p[1] - edge_start[1]) - ey * (p[0] - edge_start[0]) >= -1e-9

        def intersection(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            denominator = ex * dy - ey * dx
            if abs(denominator) < 1e-12:
                return q
            t = (ex * (edge_start[1] - p[1]) - ey * (edge_start[0] - p[0])) / denominator
            return (p[0] + t * dx, p[1] + t * dy)

        previous = polygon[-1]
        for current in polygon:
            if inside(current):
                if not inside(previous):
                    output.append(intersection(previous, current))
                output.append(current)
            elif inside(previous):
                output.append(intersection(previous, current))
            previous = current
    return np.array(output, dtype=np.float64) if len(output) >= 3 else np.zeros((0, 2))


def _overlap(a: Word, b: Word) -> float:
    """Intersection area of the two word quads over the smaller quad's area.

    Quads are used rather than bounding boxes because a deskewed candidate's
    boxes come back as rotated rectangles whose bounding boxes are inflated.
    """
    if a.box is None or b.box is None or a.quad is None or b.quad is None:
        return 0.0
    if a.box[2] <= b.box[0] or b.box[2] <= a.box[0] or a.box[3] <= b.box[1] or b.box[3] <= a.box[1]:
        return 0.0
    area_a = _polygon_area(a.quad.astype(np.float64))
    area_b = _polygon_area(b.quad.astype(np.float64))
    if area_a < 1e-6 or area_b < 1e-6:
        return 0.0
    clipped = _clip(a.quad.astype(np.float64), b.quad.astype(np.float64))
    if len(clipped) < 3:
        return 0.0
    return _polygon_area(clipped) / min(area_a, area_b)


def unite(results: list[tuple[str, list[Word]]], options: OcrOptions, skew_degrees: float = 0.0) -> Recognition:
    """Merges every candidate's confident words by position.

    Words are accepted greedily by confidence (longer words break ties) and a
    word is dropped when it overlaps one already accepted, so misreads of the
    same word lose to better reads and lines one candidate missed are filled
    in from another. Accepted words are clustered into lines spatially.
    """
    # Words of the best single candidate take part at the ordinary threshold;
    # words contributed by the other candidates must clear the stricter one.
    best_index = choose(results, options) if results else -1
    pool: list[Word] = []
    for index, (_, words) in enumerate(results):
        floor = options.min_confidence if index == best_index else options.union_min_confidence
        for w in words:
            if not w.alphanumeric or w.quad is None or w.confidence < floor:
                continue
            if options.short_word_min_confidence and len(w.text) <= 2 and w.text.isalpha() and w.confidence < options.short_word_min_confidence:
                continue
            if w.alnum_length == 1 and w.confidence < options.union_single_char_min_confidence:
                continue
            pool.append(w)

    pool.sort(key=lambda w: (w.confidence + min(w.alnum_length, 10), w.alnum_length), reverse=True)
    accepted: list[Word] = []
    for w in pool:
        if all(_overlap(w, a) < 0.4 for a in accepted):
            accepted.append(w)

    lines = cluster_lines(accepted, skew_degrees)
    # Report unclear words the way a single read would: those the best
    # candidate saw but could not read confidently.
    best_words = results[best_index][1] if best_index >= 0 else []
    dropped = sum(1 for w in best_words if w.alphanumeric and w.confidence < options.min_confidence)
    return Recognition(lines=lines, dropped_words=dropped, candidate="union", words=accepted, raw=list(results))


def cluster_lines(words: list[Word], skew_degrees: float = 0.0) -> list[RecognisedLine]:
    """Groups words into text lines by vertical overlap, in reading order.

    Clustering happens in the frame of the candidate that contributed the
    most words: a deskewed or perspective-corrected candidate's frame is
    level by construction, so rows survive tilt and keystone distortion. When
    that frame is the raw photo, `skew_degrees` levels it instead.
    """
    if not words:
        return []
    counts: dict[int, int] = {}
    for w in words:
        counts[id(w.transform)] = counts.get(id(w.transform), 0) + 1
    reference = next(w.transform for w in words if id(w.transform) == max(counts, key=counts.get))
    reference = np.eye(3) if reference is None else reference
    to_reference = np.linalg.inv(reference)
    # A pure scale/translation frame is the photo itself; apply the skew there.
    unrotated = abs(reference[0, 1]) < 1e-6 and abs(reference[1, 0]) < 1e-6
    theta = np.deg2rad(skew_degrees) if unrotated else 0.0
    cos, sin = np.cos(theta), np.sin(theta)

    def level(w: Word):
        homogeneous = np.hstack([w.quad.astype(np.float64), np.ones((4, 1))]) @ to_reference.T
        quad = homogeneous[:, :2] / np.maximum(homogeneous[:, 2:3], 1e-9)
        centre = quad.mean(axis=0)
        sides = [float(np.linalg.norm(quad[i] - quad[(i + 1) % 4])) for i in range(4)]
        x, y = float(centre[0]), float(centre[1])
        return x * cos - y * sin, x * sin + y * cos, min(sides)

    items = [(w, *level(w)) for w in words]  # (word, xc, yc, h)
    items.sort(key=lambda t: t[2])
    rows: list[list[tuple]] = []
    for item in items:
        _, _, yc, h = item
        for row in rows:
            row_yc = float(np.mean([t[2] for t in row]))
            row_h = float(np.median([t[3] for t in row]))
            if abs(yc - row_yc) < 0.5 * min(h, row_h) + 0.1 * max(h, row_h):
                row.append(item)
                break
        else:
            rows.append([item])

    rows.sort(key=lambda row: float(np.mean([t[2] for t in row])))
    lines = []
    for row in rows:
        row.sort(key=lambda t: t[1])
        lines.append(RecognisedLine(
            text=" ".join(t[0].text for t in row),
            confidence=round(float(np.mean([t[0].confidence for t in row])), 1),
        ))
    return lines
