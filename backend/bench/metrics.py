"""Accuracy metrics for OCR output against ground-truth lines."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip().lower()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def cer(predicted: list[str], truth: list[str]) -> float:
    """Character error rate of the joined text; 0 is perfect, can exceed 1 with junk."""
    a = normalise(" ".join(truth))
    b = normalise(" ".join(predicted))
    return levenshtein(a, b) / max(1, len(a))


def tokens(lines: list[str]) -> Counter:
    return Counter(t.strip(".,;:!?()[]\"'") for t in normalise(" ".join(lines)).split() if t.strip(".,;:!?()[]\"'"))


def word_prf(predicted: list[str], truth: list[str]) -> tuple[float, float, float]:
    """Word-level precision, recall and F1 on bags of words."""
    p, t = tokens(predicted), tokens(truth)
    hit = sum((p & t).values())
    precision = hit / max(1, sum(p.values()))
    recall = hit / max(1, sum(t.values()))
    f1 = 0.0 if hit == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def line_recall(predicted: list[str], truth: list[str]) -> float:
    """Fraction of ground-truth lines reproduced exactly (after normalisation)."""
    got = {normalise(l) for l in predicted}
    return sum(normalise(l) in got for l in truth) / max(1, len(truth))
