"""OpenCV preprocessing that turns a phone photo into a clean binary image for Tesseract.

Pipeline: decode (honouring EXIF orientation) -> grayscale -> rescale to a size
Tesseract reads well -> edge-preserving denoise -> adaptive threshold -> estimate
skew from the text lines -> rotate -> threshold again -> ensure dark text on white.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Tesseract is most accurate when glyphs are roughly 30-50 px tall, so the
# image is scaled by measured text height rather than by its dimensions.
TARGET_TEXT_HEIGHT = 40.0
MIN_SCALE = 0.25
MAX_SCALE = 4.0
MAX_LONG_SIDE = 4000
# Adaptive threshold window; wider than a stroke at the target text height so
# stroke interiors are compared against real background.
THRESHOLD_BLOCK = 61
# Skew corrections outside this range are almost certainly mis-estimates.
MAX_SKEW_DEGREES = 20.0
MIN_SKEW_DEGREES = 0.3


class ImageDecodeError(ValueError):
    """The upload could not be decoded as an image."""


@dataclass
class Preprocessed:
    binary: np.ndarray
    """Single-channel uint8 image, dark text on a white background."""
    skew_degrees: float
    """Rotation applied to straighten the text, in degrees (positive = counter-clockwise)."""
    scale: float
    """Factor applied to the original image's dimensions."""


def decode_image(data: bytes) -> np.ndarray:
    """Decodes bytes to a BGR array, applying the EXIF orientation phones record."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            rgb = np.asarray(im.convert("RGB"))
    except (UnidentifiedImageError, OSError, ValueError) as err:
        raise ImageDecodeError("The file is not an image that can be read.") from err
    if rgb.size == 0:
        raise ImageDecodeError("The image is empty.")
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def preprocess(bgr: np.ndarray, *, invert: bool | None = None) -> Preprocessed:
    """Prepares an image for Tesseract.

    `invert` forces the polarity decision: True treats the photo as light text
    on a dark background, False as dark on light, None decides automatically.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray, scale = rescale(gray)
    gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)
    if invert is None:
        invert = background_is_dark(gray)
    if invert:
        gray = cv2.bitwise_not(gray)

    first_pass = threshold(gray)
    angle = estimate_skew(first_pass)
    if MIN_SKEW_DEGREES <= abs(angle) <= MAX_SKEW_DEGREES:
        gray = rotate(gray, angle)
        binary = threshold(gray)
    else:
        angle = 0.0
        binary = first_pass

    return Preprocessed(binary=binary, skew_degrees=round(angle, 2), scale=scale)


def rescale(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Scales the image so the typical glyph is about TARGET_TEXT_HEIGHT pixels tall."""
    text_height = estimate_text_height(gray)
    scale = TARGET_TEXT_HEIGHT / text_height if text_height else 1.0
    scale = float(np.clip(scale, MIN_SCALE, MAX_SCALE))
    scale = min(scale, MAX_LONG_SIDE / max(gray.shape[:2]))
    if abs(scale - 1.0) < 0.05:
        return gray, 1.0
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=interpolation)
    return resized, round(scale, 3)


def estimate_text_height(gray: np.ndarray) -> float | None:
    """Median height of glyph-sized connected components, or None if there are none.

    Otsu's threshold is crude on real photos but good enough to find the
    letter-shaped blobs whose heights give the scale of the text.
    """
    height, width = gray.shape[:2]
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if np.mean(otsu) > 127:
        otsu = cv2.bitwise_not(otsu)
    count, _, stats, _ = cv2.connectedComponentsWithStats(otsu, connectivity=8)
    heights = []
    for i in range(1, count):
        w, h, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
        if h < 6 or h > height * 0.5 or w > width * 0.5 or area < 20:
            continue
        if w / h > 6 or h / w > 12:
            continue
        heights.append(h)
    if len(heights) < 3:
        return None
    return float(np.median(heights))


def background_is_dark(gray: np.ndarray) -> bool:
    """True when most of the image is dark, i.e. the sign is light text on a dark ground.

    Adaptive thresholding only produces clean glyphs when text is darker than
    its surroundings; on light-on-dark signs it draws outlines around each
    letter instead, so the grayscale is inverted first. Otsu's split separates
    ink from ground, and the larger class is taken to be the ground.
    """
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bool(np.mean(otsu) < 127)


def threshold(gray: np.ndarray) -> np.ndarray:
    """Adaptive threshold that copes with uneven lighting, producing dark-on-white."""
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=THRESHOLD_BLOCK, C=15
    )
    # Remove speckle without eroding strokes.
    return cv2.medianBlur(binary, 3)


def estimate_skew(binary: np.ndarray) -> float:
    """Estimates text rotation by fitting boxes around dilated text lines.

    Words are smeared horizontally so each text line becomes one blob; the
    median angle of the long, thin blobs is the skew. Using the median of many
    lines is far more robust than one box around all text pixels.
    """
    height, width = binary.shape[:2]
    ink = cv2.bitwise_not(binary)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, width // 40), 3))
    merged = cv2.dilate(ink, kernel, iterations=2)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles: list[float] = []
    for contour in contours:
        (_, _), (w, h), angle = cv2.minAreaRect(contour)
        if w < h:
            w, h = h, w
            angle -= 90.0
        if h < 8 or w < width * 0.08 or w / max(h, 1) < 2.5:
            continue
        angle = _normalise(angle)
        angles.append(angle)

    if not angles:
        return 0.0
    return float(np.median(angles))


def _normalise(angle: float) -> float:
    """Maps any angle to the equivalent in (-45, 45]."""
    while angle > 45.0:
        angle -= 90.0
    while angle <= -45.0:
        angle += 90.0
    return angle


def rotate(gray: np.ndarray, degrees: float) -> np.ndarray:
    """Rotates about the centre, growing the canvas so nothing is cropped."""
    height, width = gray.shape[:2]
    centre = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(centre, degrees, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(height * sin + width * cos)
    new_h = int(height * cos + width * sin)
    matrix[0, 2] += new_w / 2.0 - centre[0]
    matrix[1, 2] += new_h / 2.0 - centre[1]
    border = int(np.median(gray))
    return cv2.warpAffine(gray, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR, borderValue=border)
