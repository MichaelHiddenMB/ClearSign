"""OpenCV preprocessing that turns a phone photo into clean inputs for Tesseract.

Pipeline: decode (honouring EXIF orientation) -> grayscale -> optional
perspective correction -> rescale so glyphs are a size Tesseract reads well ->
denoise -> optional contrast/sharpening -> polarity normalisation (dark text
on light) -> adaptive threshold -> deskew -> threshold again -> optional border.

Every knob lives in PreprocessOptions so the benchmark can compare variants;
the defaults are the configuration that won the benchmark.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class ImageDecodeError(ValueError):
    """The upload could not be decoded as an image."""


@dataclass(frozen=True)
class PreprocessOptions:
    # Tesseract is most accurate when glyphs are roughly 30-50 px tall, so the
    # image is scaled by measured text height rather than by its dimensions.
    target_text_height: float = 50.0
    min_scale: float = 0.25
    max_scale: float = 4.0
    max_long_side: int = 4000
    # bilateral | nlmeans | median | gaussian | none
    denoise: str = "bilateral"
    # Local contrast equalisation for shadows and uneven lighting.
    clahe: bool = False
    # Unsharp mask to recover slightly out-of-focus strokes.
    unsharp: bool = True
    # Adaptive threshold window and offset; the window must exceed a stroke width.
    threshold_block: int = 61
    threshold_c: float = 15.0
    # Margin of background colour added around the image; Tesseract drops
    # glyphs that touch the edge.
    border: int = 0
    deskew: bool = True
    min_skew: float = 1.0
    max_skew: float = 20.0
    # Find the sign's quadrilateral and warp it flat before everything else.
    perspective: bool = True


DEFAULT_OPTIONS = PreprocessOptions()


@dataclass
class Preprocessed:
    binary: np.ndarray
    """Single-channel uint8 image, dark text on a white background."""
    gray: np.ndarray
    """Cleaned, deskewed grayscale with the same polarity as `binary`."""
    skew_degrees: float
    """Rotation applied to straighten the text, in degrees (positive = counter-clockwise)."""
    scale: float
    """Factor applied to the original image's dimensions."""
    inverted: bool
    """Whether the photo was treated as light text on a dark background."""
    perspective_corrected: bool = False
    transform: np.ndarray = None  # type: ignore[assignment]
    """3x3 homography mapping prepared-image pixels back to input-image pixels."""


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


def preprocess(
    bgr: np.ndarray,
    options: PreprocessOptions = DEFAULT_OPTIONS,
    *,
    invert: bool | None = None,
    scale: float | None = None,
) -> Preprocessed:
    """Prepares a colour image for Tesseract; see preprocess_gray."""
    return preprocess_gray(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), options, invert=invert, scale=scale)


def preprocess_gray(
    gray: np.ndarray,
    options: PreprocessOptions = DEFAULT_OPTIONS,
    *,
    invert: bool | None = None,
    scale: float | None = None,
    skew: float | None = None,
) -> Preprocessed:
    """Prepares a grayscale image for Tesseract.

    `invert` forces the polarity decision: True treats the photo as light text
    on a dark background, False as dark on light, None decides automatically.
    `scale` overrides the automatic text-height based rescaling and `skew`
    (degrees) overrides the blob-based skew estimate.
    """
    # `transform` accumulates the inverse of every geometric step so word
    # boxes can be mapped back onto the photo.
    transform = np.eye(3, dtype=np.float64)

    corrected = False
    if options.perspective:
        gray, corrected, matrix = correct_perspective(gray)
        if corrected:
            transform = transform @ np.linalg.inv(matrix)

    if scale is None:
        gray, scale = rescale(gray, options)
    else:
        gray = _resize(gray, scale)
    transform = transform @ np.diag([1.0 / scale, 1.0 / scale, 1.0])

    gray = denoise(gray, options.denoise)
    if options.clahe:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if options.unsharp:
        blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
        gray = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)

    if invert is None:
        invert = background_is_dark(gray)
    if invert:
        gray = cv2.bitwise_not(gray)

    binary = threshold(gray, options)
    angle = 0.0 if skew is None else skew
    if options.deskew and skew is None:
        angle = estimate_skew(binary)
    if options.deskew and options.min_skew <= abs(angle) <= options.max_skew:
        gray, matrix = rotate(gray, angle)
        binary = threshold(gray, options)
        transform = transform @ np.linalg.inv(np.vstack([matrix, [0.0, 0.0, 1.0]]))
    else:
        angle = 0.0

    if options.border > 0:
        pad = options.border
        gray = cv2.copyMakeBorder(gray, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=int(np.median(gray)))
        binary = cv2.copyMakeBorder(binary, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
        transform = transform @ np.array([[1, 0, -pad], [0, 1, -pad], [0, 0, 1]], dtype=np.float64)

    return Preprocessed(
        binary=binary,
        gray=gray,
        skew_degrees=round(angle, 2),
        scale=scale,
        inverted=bool(invert),
        perspective_corrected=corrected,
        transform=transform,
    )


# --- scale -------------------------------------------------------------------


def rescale(gray: np.ndarray, options: PreprocessOptions = DEFAULT_OPTIONS) -> tuple[np.ndarray, float]:
    """Scales the image so the typical glyph is about target_text_height pixels tall."""
    text_height = estimate_text_height(gray)
    scale = options.target_text_height / text_height if text_height else 1.0
    scale = float(np.clip(scale, options.min_scale, options.max_scale))
    scale = min(scale, options.max_long_side / max(gray.shape[:2]))
    if abs(scale - 1.0) < 0.05:
        return gray, 1.0
    return _resize(gray, scale), round(scale, 3)


def _resize(gray: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 1e-3:
        return gray
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=interpolation)


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


# --- cleaning ----------------------------------------------------------------


def denoise(gray: np.ndarray, method: str) -> np.ndarray:
    if method == "bilateral":
        return cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)
    if method == "nlmeans":
        return cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    if method == "median":
        return cv2.medianBlur(gray, 3)
    if method == "gaussian":
        return cv2.GaussianBlur(gray, (3, 3), 0)
    return gray


def background_is_dark(gray: np.ndarray) -> bool:
    """True when most of the image is dark, i.e. the sign is light text on a dark ground.

    Adaptive thresholding only produces clean glyphs when text is darker than
    its surroundings; on light-on-dark signs it draws outlines around each
    letter instead, so the grayscale is inverted first. Otsu's split separates
    ink from ground, and the larger class is taken to be the ground.
    """
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bool(np.mean(otsu) < 127)


def threshold(gray: np.ndarray, options: PreprocessOptions = DEFAULT_OPTIONS) -> np.ndarray:
    """Adaptive threshold that copes with uneven lighting, producing dark-on-white."""
    block = max(3, options.threshold_block | 1)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=block, C=options.threshold_c
    )
    # Remove speckle without eroding strokes.
    return cv2.medianBlur(binary, 3)


# --- geometry ----------------------------------------------------------------


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
        angles.append(_normalise(angle))

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


def rotate(gray: np.ndarray, degrees: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotates about the centre, growing the canvas so nothing is cropped.

    Returns the rotated image and the 2x3 affine matrix that was applied.
    """
    height, width = gray.shape[:2]
    centre = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(centre, degrees, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(height * sin + width * cos)
    new_h = int(height * cos + width * sin)
    matrix[0, 2] += new_w / 2.0 - centre[0]
    matrix[1, 2] += new_h / 2.0 - centre[1]
    border = int(np.median(gray))
    rotated = cv2.warpAffine(gray, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR, borderValue=border)
    return rotated, matrix


def correct_perspective(gray: np.ndarray) -> tuple[np.ndarray, bool, np.ndarray]:
    """Finds the largest convex quadrilateral (the sign) and warps it to a rectangle.

    Returns (image, corrected, homography); the image and an identity matrix
    come back unchanged when no convincing sign outline is found.
    """
    height, width = gray.shape[:2]
    working_scale = min(1.0, 800.0 / max(height, width))
    small = _resize(gray, working_scale) if working_scale < 1.0 else gray
    edges = cv2.Canny(cv2.GaussianBlur(small, (5, 5), 0), 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    image_area = small.shape[0] * small.shape[1]

    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        area = cv2.contourArea(approx)
        if area < 0.12 * image_area or area > 0.97 * image_area:
            continue
        quad = _order_corners(approx.reshape(4, 2).astype(np.float32) / working_scale)
        (tl, tr, br, bl) = quad
        target_w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        target_h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if target_w < 40 or target_h < 20:
            continue
        aspect = target_w / target_h
        if aspect < 0.2 or aspect > 12:
            continue
        destination = np.array(
            [[0, 0], [target_w - 1, 0], [target_w - 1, target_h - 1], [0, target_h - 1]], dtype=np.float32
        )
        matrix = cv2.getPerspectiveTransform(quad, destination)
        warped = cv2.warpPerspective(gray, matrix, (target_w, target_h), flags=cv2.INTER_LINEAR)
        return warped, True, matrix.astype(np.float64)
    return gray, False, np.eye(3, dtype=np.float64)


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Orders four points as top-left, top-right, bottom-right, bottom-left."""
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).ravel()
    return np.array(
        [points[np.argmin(sums)], points[np.argmin(diffs)], points[np.argmax(sums)], points[np.argmax(diffs)]],
        dtype=np.float32,
    )
