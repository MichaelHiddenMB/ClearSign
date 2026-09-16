import cv2
import numpy as np
import pytest

from app.preprocess import (
    ImageDecodeError,
    background_is_dark,
    decode_image,
    estimate_skew,
    preprocess,
    threshold,
)

from .helpers import render_sign


def test_decode_rejects_non_image():
    with pytest.raises(ImageDecodeError):
        decode_image(b"definitely not an image")


def test_light_on_dark_sign_is_normalised_to_dark_text_on_white():
    bgr = decode_image(render_sign(["EXIT"], fg="white", bg="#123456"))
    prepared = preprocess(bgr)
    assert prepared.binary.dtype == np.uint8
    assert np.mean(prepared.binary) > 127, "background should be white"
    # The glyph strokes should be solid, not outlines: ink pixels form thick blobs.
    ink = (prepared.binary == 0).astype(np.uint8)
    eroded = cv2.erode(ink, np.ones((5, 5), np.uint8))
    assert eroded.sum() > 0.3 * ink.sum()


def test_dark_on_light_sign_is_not_inverted():
    bgr = decode_image(render_sign(["EXIT"]))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    assert not background_is_dark(gray)


@pytest.mark.parametrize("angle", [-6.0, -3.0, 3.0, 6.0])
def test_estimate_skew_recovers_rotation(angle):
    bgr = decode_image(render_sign(["PLATFORM 2", "Trains to Downtown", "Next departure 4:12 PM"], rotate_degrees=angle))
    prepared = preprocess(bgr)
    # PIL rotates counter-clockwise for positive angles; the correction should undo it.
    assert prepared.skew_degrees == pytest.approx(-angle, abs=1.0)


def test_estimate_skew_is_zero_for_straight_text():
    bgr = decode_image(render_sign(["PLATFORM 2", "Trains to Downtown"]))
    assert abs(estimate_skew(threshold(np.asarray(bgr[:, :, 0])))) < 0.5
