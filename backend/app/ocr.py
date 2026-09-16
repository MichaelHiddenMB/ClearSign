"""Tesseract recognition with per-word confidence filtering."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytesseract
from pytesseract import Output

# Tesseract page segmentation modes.
PSM_SPARSE_TEXT = 11


@dataclass
class RecognisedLine:
    text: str
    confidence: float


@dataclass
class Recognition:
    lines: list[RecognisedLine]
    dropped_words: int


def recognize(binary: np.ndarray, *, min_confidence: float, language: str, psm: int) -> Recognition:
    """Runs Tesseract and groups confident words back into lines.

    The first pass assumes a block of text (the common case for a sign). If it
    yields nothing, sparse-text mode is tried, which copes with scattered labels.
    """
    result = _run(binary, min_confidence=min_confidence, language=language, psm=psm)
    if not result.lines and psm != PSM_SPARSE_TEXT:
        result = _run(binary, min_confidence=min_confidence, language=language, psm=PSM_SPARSE_TEXT)
    return result


def _run(binary: np.ndarray, *, min_confidence: float, language: str, psm: int) -> Recognition:
    data = pytesseract.image_to_data(
        binary, lang=language, config=f"--oem 3 --psm {psm}", output_type=Output.DICT
    )
    return group_words(data, min_confidence=min_confidence)


def group_words(data: dict, *, min_confidence: float) -> Recognition:
    """Groups Tesseract's word table into lines, dropping low-confidence words.

    Tesseract reports confidence -1 for non-word rows (blocks, paragraphs,
    lines); only rows with real text and a confidence are considered words.
    """
    lines: dict[tuple[int, int, int], list[tuple[str, float]]] = {}
    order: list[tuple[int, int, int]] = []
    dropped = 0

    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        if conf < min_confidence:
            dropped += 1
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append((text, conf))

    recognised = []
    for key in order:
        words = lines[key]
        recognised.append(
            RecognisedLine(
                text=" ".join(w for w, _ in words),
                confidence=round(sum(c for _, c in words) / len(words), 1),
            )
        )
    return Recognition(lines=recognised, dropped_words=dropped)
