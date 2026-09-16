"""Tests for the two-pass pipeline, candidate selection and junk filtering."""

import io
import random

import numpy as np
import pytest
from PIL import Image

from app.ocr import OcrOptions, Word, _overlap, choose, cluster_lines, group_words, map_boxes, unite
from app.pipeline import DEFAULT_PIPELINE, detect_text, run, skew_from_words
from app.preprocess import decode_image, preprocess

from .helpers import render_sign


def word(text, conf, line=1, **kw):
    return Word(text=text, confidence=conf, block=1, paragraph=1, line=line, left=0, top=0, width=10, height=10, **kw)


def test_group_words_drops_punctuation_only_words():
    result = group_words([word("|", 95), word("EXIT", 96), word("‘", 90)], min_confidence=60)
    assert [l.text for l in result.lines] == ["EXIT"]
    assert result.dropped_words == 0  # junk is removed silently, not counted as unclear


def test_group_words_applies_short_word_rule():
    words = [word("a", 70), word("oe", 65), word("A", 92), word("12", 65), word("Zone", 90)]
    result = group_words(words, min_confidence=60, short_word_min_confidence=80)
    assert [l.text for l in result.lines] == ["A 12 Zone"]
    assert result.dropped_words == 2


def test_guarded_selection_prefers_clean_result_unless_it_reads_far_less():
    options = OcrOptions(select="guarded", guard_fraction=0.5, min_confidence=70)
    many_with_junk = [word("PLATFORM", 85), word("2", 80), word("Trains", 82), word("tl", 72), word("ae", 71)]
    few_but_clean = [word("PLATFORM", 96), word("2", 95), word("Trains", 94)]
    only_one = [word("PLATFORM", 99)]
    results = [("a", many_with_junk), ("b", few_but_clean), ("c", only_one)]
    assert results[choose(results, options)][0] == "b"  # 3 of 5 confident words, higher mean
    # "c" has the best mean but reads too little to be eligible.


def scene_with_sign(lines, *, angle=0.0, size=64, fg="black", bg="white"):
    """Places a rendered sign on a textured background, the way phone photos look."""
    sign = Image.open(io.BytesIO(render_sign(lines, size=size, fg=fg, bg=bg, rotate_degrees=angle))).convert("RGB")
    rng = np.random.default_rng(7)
    texture = rng.integers(90, 170, (sign.height * 2, sign.width * 2, 3)).astype(np.uint8)
    canvas = Image.fromarray(texture)
    canvas.paste(sign, (sign.width // 2, sign.height // 2))
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_detect_text_finds_the_sign_region_and_height():
    bgr = decode_image(scene_with_sign(["PLATFORM 2", "Trains to Downtown"], size=64))
    gray = bgr[:, :, 1]
    detection = detect_text(gray, DEFAULT_PIPELINE)
    assert detection.region is not None
    x0, y0, x1, y1 = detection.region
    height, width = gray.shape
    # The sign sits in the middle half of the canvas; the region must cover it.
    assert x0 <= width * 0.3 and x1 >= width * 0.7
    assert y0 <= height * 0.3 and y1 >= height * 0.7
    assert 30 <= detection.text_height <= 90


def test_pipeline_reads_a_tilted_sign_in_a_cluttered_scene():
    bgr = decode_image(scene_with_sign(["EXIT", "Keep right"], angle=4, size=72))
    result = run(bgr, DEFAULT_PIPELINE)
    texts = [l.text.upper() for l in result.recognition.lines]
    assert "EXIT" in texts
    assert "KEEP RIGHT" in texts
    assert not any(set(t) <= set("|.,'‘’-_ ") for t in texts), "no punctuation-only lines"


def test_pipeline_reads_light_on_dark_sign_in_a_light_scene():
    bgr = decode_image(scene_with_sign(["SMEDGATAN"], fg="white", bg="#101010", size=80))
    result = run(bgr, DEFAULT_PIPELINE)
    assert "SMEDGATAN" in [l.text.upper() for l in result.recognition.lines]


def test_preprocess_still_works_without_detection():
    bgr = decode_image(render_sign(["Mind the gap", "Stand behind the line"], rotate_degrees=-5))
    prepared = preprocess(bgr)
    assert prepared.skew_degrees == pytest.approx(5, abs=1.5)
    assert prepared.binary.shape == prepared.gray.shape


def placed(text, conf, left, top, width, height, line=1):
    w = Word(text=text, confidence=conf, block=1, paragraph=1, line=line, left=left, top=top, width=width, height=height)
    return w


def test_union_keeps_best_read_of_a_word_and_fills_missing_lines():
    a = [placed("Welcome", 90, 0, 0, 100, 20), placed("HARLO", 92, 0, 40, 200, 60)]
    b = [placed("HARLOW", 95, 0, 40, 210, 60), placed("MUSEUM", 96, 0, 110, 220, 60)]
    map_boxes(a, None)
    map_boxes(b, None)
    result = unite([("a", a), ("b", b)], OcrOptions(min_confidence=70, union_min_confidence=75))
    assert [l.text for l in result.lines] == ["Welcome", "HARLOW", "MUSEUM"]


def test_cluster_lines_levels_a_tilted_sign():
    # Two rows of words on a sign tilted by 6 degrees: row 1 rises across the width.
    import math
    theta = math.radians(10)
    rows = []
    for row, y in enumerate((0, 120)):
        for i, text in enumerate(("Max", "weight", "1000", "kg")):
            x = i * 250
            w = placed(text, 90, int(x * math.cos(theta) + y * math.sin(theta)), int(-x * math.sin(theta) + y * math.cos(theta)), 120, 40, line=row + 1)
            rows.append(w)
    map_boxes(rows, None)
    assert len(cluster_lines(rows, skew_degrees=0.0)) > 2  # unlevelled rows fragment
    # The text rises to the right, so the pipeline's skew is -10 and it levels with +10.
    levelled = cluster_lines(rows, skew_degrees=10.0)
    assert [l.text for l in levelled] == ["Max weight 1000 kg", "Max weight 1000 kg"]


def test_skew_from_words_ignores_distant_words_sharing_a_line_id():
    neighbours = [placed("Welcome", 90, 0, 100, 200, 40), placed("to", 90, 220, 100, 60, 40)]
    far_away = placed("Harlow", 85, 1200, 400, 150, 30)  # same sparse-mode line id, different row
    assert abs(skew_from_words(neighbours + [far_away])) < 0.5
    # Rising text: each box bottom sits at the word's left end, 8 px higher per 120 px of run.
    rising = [placed("Mind", 90, 0, 100, 100, 40), placed("the", 90, 120, 92, 80, 40), placed("gap", 90, 220, 84, 80, 40)]
    assert skew_from_words(rising) == pytest.approx(-3.8, abs=0.5)


def test_overlap_handles_coincident_and_rotated_quads():
    a = placed("Pharmacy", 96, 0, 0, 1, 1)
    a.quad = np.array([[120, 58], [465, 136], [444, 217], [96, 137]], dtype=np.float32)
    b = placed("Pharmacy", 90, 0, 0, 1, 1)
    b.quad = np.array([[119, 60], [465, 137], [444, 217], [96, 137]], dtype=np.float32)
    for w in (a, b):
        w.box = (float(w.quad[:, 0].min()), float(w.quad[:, 1].min()), float(w.quad[:, 0].max()), float(w.quad[:, 1].max()))
    assert _overlap(a, b) > 0.95
    c = placed("floor", 96, 600, 0, 100, 40)
    map_boxes([c], None)
    assert _overlap(a, c) == 0.0
    d = placed("Ph", 96, 100, 60, 120, 120)  # sits inside the Pharmacy quad
    map_boxes([d], None)
    assert _overlap(a, d) > 0.6


def test_cluster_lines_uses_the_level_frame_of_a_corrected_candidate():
    # Words read from a candidate that was rotated by 12 degrees: level in its own
    # frame, tilted in the photo. No skew hint is needed to keep the rows intact.
    import math
    theta = math.radians(12)
    rotation = np.array([[math.cos(theta), -math.sin(theta), 0], [math.sin(theta), math.cos(theta), 0], [0, 0, 1]])
    words = []
    for row, y in enumerate((0, 120)):
        for i, text in enumerate(("Bus", "42", "to", "Airport")):
            words.append(placed(text, 90, i * 220, y, 150, 40, line=row + 1))
    map_boxes(words, rotation)
    assert [l.text for l in cluster_lines(words, skew_degrees=0.0)] == ["Bus 42 to Airport", "Bus 42 to Airport"]


def test_pipeline_reads_a_photo_stored_sideways():
    import cv2

    bgr = decode_image(scene_with_sign(["Platform 2", "Trains to Downtown"], size=72))
    sideways = cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)
    result = run(sideways, DEFAULT_PIPELINE)
    texts = [l.text.upper() for l in result.recognition.lines]
    assert result.detection is not None and result.detection.rotation in (90, 270)
    assert "PLATFORM 2" in texts and "TRAINS TO DOWNTOWN" in texts


def test_pipeline_handles_phone_resolution_scene():
    import cv2

    bgr = decode_image(scene_with_sign(["Ticket office", "Closed"], size=64))
    factor = 4000 / max(bgr.shape[:2])
    big = cv2.resize(bgr, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    result = run(big, DEFAULT_PIPELINE)
    texts = [l.text.upper() for l in result.recognition.lines]
    assert "TICKET OFFICE" in texts and "CLOSED" in texts


def test_decode_image_accepts_heic():
    pillow_heif = pytest.importorskip("pillow_heif")
    sign = Image.open(io.BytesIO(render_sign(["EXIT"]))).convert("RGB")
    buffer = io.BytesIO()
    try:
        pillow_heif.from_pillow(sign).save(buffer, format="HEIF", quality=90)
    except Exception as err:  # encoder not available in this build
        pytest.skip(f"HEIF encoder unavailable: {err}")
    bgr = decode_image(buffer.getvalue())
    assert bgr.shape[:2] == (sign.height, sign.width)
