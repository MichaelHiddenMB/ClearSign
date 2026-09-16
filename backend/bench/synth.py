"""Generates synthetic sign photos with ground truth for benchmarking.

Each sample is a sign (text block, optional frame) placed in a scene, then
distorted the way phone photos are: perspective, rotation, uneven lighting,
blur, sensor noise, JPEG compression and distance (small text).
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SUPPLEMENTAL = "/System/Library/Fonts/Supplemental/"
FONT_FILES: list[tuple[str, str, int]] = [
    ("Arial", SUPPLEMENTAL + "Arial.ttf", 0),
    ("Arial Bold", SUPPLEMENTAL + "Arial Bold.ttf", 0),
    ("Arial Black", SUPPLEMENTAL + "Arial Black.ttf", 0),
    ("Arial Narrow Bold", SUPPLEMENTAL + "Arial Narrow Bold.ttf", 0),
    ("Helvetica", "/System/Library/Fonts/Helvetica.ttc", 0),
    ("Helvetica Bold", "/System/Library/Fonts/Helvetica.ttc", 1),
    ("Helvetica Neue", "/System/Library/Fonts/HelveticaNeue.ttc", 0),
    ("DIN Alternate Bold", SUPPLEMENTAL + "DIN Alternate Bold.ttf", 0),
    ("DIN Condensed Bold", SUPPLEMENTAL + "DIN Condensed Bold.ttf", 0),
    ("Futura", SUPPLEMENTAL + "Futura.ttc", 0),
    ("Avenir Next", "/System/Library/Fonts/Avenir Next.ttc", 0),
    ("Verdana", SUPPLEMENTAL + "Verdana.ttf", 0),
    ("Verdana Bold", SUPPLEMENTAL + "Verdana Bold.ttf", 0),
    ("Trebuchet MS", SUPPLEMENTAL + "Trebuchet MS.ttf", 0),
    ("Tahoma", SUPPLEMENTAL + "Tahoma.ttf", 0),
    ("Georgia Bold", SUPPLEMENTAL + "Georgia Bold.ttf", 0),
    ("Impact", SUPPLEMENTAL + "Impact.ttf", 0),
    ("Courier New Bold", SUPPLEMENTAL + "Courier New Bold.ttf", 0),
    ("DejaVu Sans Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ("Liberation Sans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 0),
]

# (name, foreground, background, low_contrast)
PALETTES: list[tuple[str, tuple[int, int, int], tuple[int, int, int], bool]] = [
    ("black on white", (20, 20, 20), (250, 250, 250), False),
    ("white on black", (245, 245, 245), (15, 15, 15), False),
    ("white on navy", (255, 255, 255), (11, 61, 145), False),
    ("white on green", (255, 255, 255), (0, 106, 78), False),
    ("black on yellow", (10, 10, 10), (255, 205, 0), False),
    ("white on red", (255, 255, 255), (190, 20, 30), False),
    ("red on white", (200, 20, 30), (250, 250, 250), False),
    ("yellow on black", (255, 220, 60), (10, 10, 10), False),
    ("white on blue", (255, 255, 255), (30, 90, 200), False),
    ("navy on cream", (20, 33, 61), (246, 240, 225), False),
    ("black on orange", (10, 10, 10), (240, 120, 30), False),
    ("dark grey on grey", (70, 70, 75), (165, 165, 170), True),
    ("grey on white", (140, 140, 145), (250, 250, 250), True),
    ("white on light blue", (255, 255, 255), (120, 170, 230), True),
]

TEXTS: list[list[str]] = [
    ["PLATFORM 2", "Trains to Downtown"],
    ["EXIT"],
    ["NO PARKING", "8AM - 6PM", "MON - FRI"],
    ["Gate B12", "Boarding 14:35"],
    ["WET FLOOR"],
    ["Push"],
    ["Main Street"],
    ["OPEN", "Mon-Sat 9:00-17:30", "Sun Closed"],
    ["Coffee $3.50", "Latte $4.25", "Bagel $2.00"],
    ["CAUTION", "Hot surface"],
    ["SPEED", "LIMIT", "25"],
    ["Pharmacy", "Second floor"],
    ["Room 204", "Dr A Patel"],
    ["Emergency exit", "Keep clear"],
    ["Bus 42", "to Airport", "every 15 min"],
    ["Elevator", "Out of service"],
    ["SALE", "50% off"],
    ["Please queue here"],
    ["Ticket office", "Closed"],
    ["Northbound", "Next train 12 min"],
    ["DO NOT ENTER"],
    ["Bike lane"],
    ["Library", "Quiet zone"],
    ["Max weight 1000 kg"],
    ["Mind the gap"],
    ["Tickets", "Cash only"],
    ["Parking", "Level P3"],
    ["Baggage claim", "Carousel 7"],
    ["Welcome to", "Riverside Park"],
    ["Fire extinguisher"],
    ["Reception", "Please ring bell"],
    ["Lost and found"],
    ["Zone A", "Bays 1-24"],
    ["Route 66", "West"],
    ["Wheelchair access", "Use ramp"],
    ["Hours", "Mon 8-5", "Tue 8-5", "Wed 8-8"],
    ["Terminal 1", "Departures"],
    ["Toilets", "First floor"],
    ["Staff only"],
    ["Danger", "High voltage"],
    ["Fresh bread", "baked daily"],
    ["Way out"],
    ["Bakery", "Est. 1952"],
    ["King Street", "Bridge Road"],
    ["Ward 7", "Visiting 2-8pm"],
    ["Museum", "Free entry"],
    ["Slippery when wet"],
    ["Recycling", "Glass and cans"],
    ["Meeting room 3"],
    ["Left luggage", "Open 6am to 11pm"],
]


@dataclass
class Sample:
    id: str
    jpeg: bytes
    lines: list[str]
    tags: list[str]
    font: str
    palette: str
    text_px: float
    params: dict = field(default_factory=dict)


def available_fonts() -> list[tuple[str, str, int]]:
    fonts = []
    for name, path, index in FONT_FILES:
        try:
            ImageFont.truetype(path, 32, index=index)
            fonts.append((name, path, index))
        except OSError:
            continue
    if not fonts:
        raise RuntimeError("No TrueType fonts found for the benchmark.")
    return fonts


def generate(count: int, seed: int = 1) -> list[Sample]:
    rng = random.Random(seed)
    fonts = available_fonts()
    return [_make_sample(f"synth-{seed}-{i:03d}", rng, fonts) for i in range(count)]


def _make_sample(sample_id: str, rng: random.Random, fonts) -> Sample:
    lines = list(rng.choice(TEXTS))
    font_name, font_path, font_index = rng.choice(fonts)
    palette_name, fg, bg, low_contrast = rng.choice(PALETTES)
    size = rng.randint(36, 120)
    font = ImageFont.truetype(font_path, size, index=font_index)

    # --- sign panel ---
    pad = int(size * rng.uniform(0.4, 1.2))
    line_gap = int(size * rng.uniform(1.25, 1.7))
    widths = [font.getlength(line) for line in lines]
    sign_w = int(max(widths)) + pad * 2
    sign_h = line_gap * len(lines) + pad * 2 - (line_gap - size) // 2
    sign = Image.new("RGB", (sign_w, sign_h), bg)
    draw = ImageDraw.Draw(sign)
    centred = rng.random() < 0.5
    for i, (line, w) in enumerate(zip(lines, widths)):
        x = (sign_w - w) / 2 if centred else pad
        draw.text((x, pad + i * line_gap), line, fill=fg, font=font)
    framed = rng.random() < 0.45
    if framed:
        inset = max(2, pad // 3)
        draw.rectangle([inset, inset, sign_w - inset - 1, sign_h - inset - 1], outline=fg, width=rng.randint(2, 6))

    # --- scene ---
    fraction = rng.uniform(0.45, 1.0)
    in_scene = fraction < 0.92
    if in_scene:
        canvas_w = int(sign_w / fraction)
        canvas_h = int(sign_h / rng.uniform(fraction * 0.8, 1.0))
        canvas_h = max(canvas_h, sign_h + 2)
        canvas = _scene_background(rng, canvas_w, canvas_h, bg)
        ox = rng.randint(0, canvas_w - sign_w)
        oy = rng.randint(0, canvas_h - sign_h)
        canvas.paste(sign, (ox, oy))
    else:
        canvas = sign

    image = np.asarray(canvas).astype(np.float32)

    # --- geometry: rotation + perspective in one homography ---
    h, w = image.shape[:2]
    angle = rng.uniform(-8, 8) if rng.random() < 0.6 else 0.0
    jitter = rng.uniform(0.0, 0.10) if rng.random() < 0.5 else 0.0
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = src.copy()
    for k in range(4):
        dst[k, 0] += rng.uniform(-jitter, jitter) * w
        dst[k, 1] += rng.uniform(-jitter, jitter) * h
    homography = cv2.getPerspectiveTransform(src, dst)
    rotation = np.vstack([cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0), [0, 0, 1]])
    matrix = rotation @ homography
    corners = cv2.perspectiveTransform(src.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    min_xy = corners.min(axis=0)
    max_xy = corners.max(axis=0)
    shift = np.array([[1, 0, -min_xy[0]], [0, 1, -min_xy[1]], [0, 0, 1]], dtype=np.float64)
    matrix = shift @ matrix
    out_w, out_h = int(math.ceil(max_xy[0] - min_xy[0])), int(math.ceil(max_xy[1] - min_xy[1]))
    fill = _scene_fill(rng, bg)
    image = cv2.warpPerspective(image, matrix, (out_w, out_h), flags=cv2.INTER_LINEAR, borderValue=fill)

    # --- distance: scale so text ends up at a chosen pixel height ---
    text_px = math.exp(rng.uniform(math.log(13), math.log(110)))
    scale = text_px / size
    scale = min(scale, 2200 / max(out_w, out_h))
    scale = max(scale, 320 / max(out_w, out_h))
    text_px = size * scale
    image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)

    # --- photometric ---
    image = _illuminate(rng, image)
    cast = np.array([rng.uniform(0.9, 1.1) for _ in range(3)], dtype=np.float32)
    image = image * cast
    blur_sigma = 0.0
    motion = 0
    roll = rng.random()
    if roll < 0.45:
        blur_sigma = rng.uniform(0.4, 1.6)
        image = cv2.GaussianBlur(image, (0, 0), blur_sigma)
    elif roll < 0.62:
        motion = rng.choice([3, 5, 7, 9])
        kernel = np.zeros((motion, motion), dtype=np.float32)
        kernel[motion // 2, :] = 1.0 / motion
        image = cv2.filter2D(image, -1, kernel)
    noise_sigma = rng.uniform(0, 10) if rng.random() < 0.65 else 0.0
    if noise_sigma:
        image = image + np.random.default_rng(rng.randint(0, 2**31)).normal(0, noise_sigma, image.shape).astype(np.float32)
    image = np.clip(image, 0, 255).astype(np.uint8)
    quality = rng.randint(40, 95)
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="JPEG", quality=quality)

    tags = []
    if text_px < 20:
        tags.append("small")
    if blur_sigma > 0.9 or motion >= 5:
        tags.append("blur")
    if noise_sigma > 6:
        tags.append("noise")
    if jitter > 0.03:
        tags.append("perspective")
    if abs(angle) > 2:
        tags.append("rotated")
    if low_contrast:
        tags.append("lowcontrast")
    if _luminance(bg) < _luminance(fg):
        tags.append("light-on-dark")
    if in_scene:
        tags.append("scene")
    if framed:
        tags.append("framed")
    if quality < 55:
        tags.append("jpeg")
    if not any(t in tags for t in ("small", "blur", "noise", "perspective", "rotated", "lowcontrast")):
        tags.append("clean")

    return Sample(
        id=sample_id,
        jpeg=buffer.getvalue(),
        lines=lines,
        tags=tags,
        font=font_name,
        palette=palette_name,
        text_px=round(text_px, 1),
        params={
            "angle": round(angle, 2),
            "jitter": round(jitter, 3),
            "blur": round(blur_sigma, 2),
            "motion": motion,
            "noise": round(noise_sigma, 1),
            "jpeg": quality,
            "size": size,
        },
    )


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _scene_fill(rng: random.Random, sign_bg: tuple[int, int, int]) -> tuple[float, float, float]:
    base = rng.choice([(120, 120, 120), (180, 170, 150), (90, 100, 110), (200, 200, 205), (60, 60, 60)])
    return tuple(float(c) for c in base)


def _scene_background(rng: random.Random, w: int, h: int, sign_bg: tuple[int, int, int]) -> Image.Image:
    kind = rng.choice(["solid", "gradient", "texture", "clutter"])
    base = rng.choice([(120, 120, 120), (180, 170, 150), (90, 100, 110), (200, 200, 205), (60, 60, 60), (150, 130, 110)])
    if kind == "solid":
        return Image.new("RGB", (w, h), base)
    arr = np.zeros((h, w, 3), dtype=np.float32) + np.array(base, dtype=np.float32)
    if kind == "gradient":
        ramp = np.linspace(0.6, 1.3, w, dtype=np.float32)[None, :, None]
        arr = arr * ramp
    elif kind == "texture":
        noise = np.random.default_rng(rng.randint(0, 2**31)).normal(0, 25, (h, w, 1)).astype(np.float32)
        arr = arr + cv2.GaussianBlur(noise, (0, 0), 2)[:, :, None]
    else:
        seed_rng = np.random.default_rng(rng.randint(0, 2**31))
        for _ in range(rng.randint(4, 12)):
            x0, y0 = int(seed_rng.integers(0, w)), int(seed_rng.integers(0, h))
            x1, y1 = min(w, x0 + int(seed_rng.integers(20, w // 2 + 21))), min(h, y0 + int(seed_rng.integers(20, h // 2 + 21)))
            colour = seed_rng.integers(30, 220, 3).astype(np.float32)
            arr[y0:y1, x0:x1] = colour
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _illuminate(rng: random.Random, image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    if rng.random() < 0.7:
        theta = rng.uniform(0, 2 * math.pi)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        ramp = (xs * math.cos(theta) + ys * math.sin(theta))
        ramp = (ramp - ramp.min()) / max(1e-6, ramp.max() - ramp.min())
        low = rng.uniform(0.5, 0.95)
        gain = low + (1.0 - low) * ramp
        image = image * gain[:, :, None]
    if rng.random() < 0.4:
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        r2 = ((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2
        strength = rng.uniform(0.15, 0.5)
        image = image * (1.0 - strength * r2)[:, :, None]
    return image
