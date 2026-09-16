"""Prints what every stage of the pipeline saw for one image.

    .venv/bin/python -m bench.inspect bench/real/shoreham.jpg [--set key=value ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.pipeline import run
from app.preprocess import decode_image

from .run import build_options, parse_set


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--set", action="append", default=[])
    parser.add_argument("--words", action="store_true", help="list every word of every candidate")
    parser.add_argument("--draw", default=None, help="write the photo with accepted word boxes and the detection region")
    parser.add_argument("--dump", default=None, help="directory to write the prepared gray/binary images into")
    args = parser.parse_args(argv)
    options = build_options(dict(parse_set(s) for s in args.set))
    bgr = decode_image(Path(args.image).read_bytes())
    result = run(bgr, options)
    d = result.detection
    print(f"image {bgr.shape[1]}x{bgr.shape[0]}")
    if d:
        print(f"detect: scale={d.scale:.3f} region={d.region} text_height={d.text_height and round(d.text_height, 1)} words={len(d.words)}")
    p = result.prepared
    print(f"prepared: {p.gray.shape[1]}x{p.gray.shape[0]} scale={p.scale} skew={p.skew_degrees} inverted={p.inverted} perspective={p.perspective_corrected}")
    print(f"chosen: {result.recognition.candidate}")
    for line in result.recognition.lines:
        print(f"   {line.confidence:5.1f}  {line.text}")
    if args.draw:
        import cv2

        canvas = bgr.copy()
        if d and d.region:
            x0, y0, x1, y1 = d.region
            cv2.rectangle(canvas, (x0, y0), (x1, y1), (255, 0, 0), 3)
        accepted = {id(w) for w in result.recognition.words}
        pool = [w for _, words in result.recognition.raw for w in words
                if w.box is not None and w.alphanumeric and w.confidence >= options.ocr.union_min_confidence]
        for w in sorted(pool, key=lambda w: id(w) in accepted):
            bx0, by0, bx1, by1 = (int(v) for v in w.box)
            colour = (0, 200, 0) if id(w) in accepted else (0, 0, 255)
            cv2.rectangle(canvas, (bx0, by0), (bx1, by1), colour, 2)
            cv2.putText(canvas, f"{w.text} {w.confidence:.0f}", (bx0, max(12, by0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
            cv2.putText(canvas, f"{w.text} {w.confidence:.0f}", (bx0, max(12, by0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255) if id(w) in accepted else (200, 200, 255), 1)
        cv2.imwrite(args.draw, canvas)
        print(f"wrote {args.draw} ({len(pool)} pool words, {len(accepted)} accepted)")
    if args.dump:
        import cv2

        out = Path(args.dump)
        out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "prepared-gray.png"), p.gray)
        cv2.imwrite(str(out / "prepared-binary.png"), p.binary)
        print(f"wrote prepared images to {out}")
    print("candidates:")
    for label, words in result.recognition.raw:
        real = [w for w in words if w.alphanumeric]
        conf = [w for w in real if w.confidence >= options.ocr.min_confidence]
        mean = sum(w.confidence for w in real) / len(real) if real else 0
        print(f"  {label:<24} words={len(real):3d} confident={len(conf):3d} mean={mean:5.1f}  " +
              " ".join(f"{w.text}({w.confidence:.0f})" for w in (real if args.words else conf)[:40]))


if __name__ == "__main__":
    sys.exit(main())
