"""Renders synthetic sign photos so the pipeline can be tested without fixtures."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render_sign(
    lines: list[str],
    *,
    fg: str = "black",
    bg: str = "white",
    size: int = 72,
    rotate_degrees: float = 0.0,
    image_format: str = "JPEG",
) -> bytes:
    """Draws lines of text on a sign-like background, optionally tilted."""
    font = load_font(size)
    padding = size
    line_height = int(size * 1.5)
    width = max(int(font.getlength(line)) for line in lines) + padding * 2
    height = line_height * len(lines) + padding * 2

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((padding, padding + i * line_height), line, fill=fg, font=font)

    if rotate_degrees:
        image = image.rotate(rotate_degrees, expand=True, fillcolor=bg, resample=Image.BICUBIC)

    buffer = io.BytesIO()
    image.save(buffer, format=image_format, quality=92)
    return buffer.getvalue()
