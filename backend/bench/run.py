"""Benchmark runner: evaluates pipeline variants on synthetic and real sign photos.

    .venv/bin/python -m bench.run --variants baseline,best-model --n 120
    .venv/bin/python -m bench.run --variants baseline --set ocr.psms=6,11 --set preprocess.border=20

Results print as a table and are written to a JSON file.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

from app.ocr import OcrOptions
from app.pipeline import PipelineOptions, run
from app.preprocess import PreprocessOptions, decode_image

from . import synth
from .metrics import cer, line_recall, word_prf

CACHE = Path(os.environ.get("BENCH_CACHE", Path(__file__).resolve().parent / ".cache"))
BEST_MODEL = str(Path(__file__).resolve().parent.parent / "tessdata")

# Named variants are dicts of dotted overrides applied on top of the defaults.
VARIANTS: dict[str, dict] = {
    "defaults": {},
    # The pipeline as first written: one pass, adaptive threshold only, fast model, block mode.
    "baseline": {"ocr.tessdata_dir": None, "ocr.psms": (6,), "pipeline.inputs": ("binary",), "preprocess.border": 0,
                 "ocr.do_invert": True, "preprocess.target_text_height": 40, "pipeline.detect": False,
                 "pipeline.smooth_candidate": False, "preprocess.perspective": False, "preprocess.unsharp": False,
                 "ocr.min_confidence": 60, "ocr.short_word_min_confidence": 0, "ocr.select": "confident",
                 "ocr.early_exit_confidence": 101, "ocr.union": False, "ocr.fallback_psms": (11,),
                 "ocr.fallback_min_words": 1, "pipeline.multi_scale": False},
    "multiscale": {"pipeline.multi_scale": True},
    "multiscale2": {"pipeline.multi_scale": True, "pipeline.multi_scale_ratio": 2.0},
    "multiscale3": {"pipeline.multi_scale": True, "pipeline.multi_scale_ratio": 3.0},
    "no-detect": {"pipeline.detect": False},
    "detect-psm3": {"pipeline.detect_psm": 3},
    "detect-psm12": {"pipeline.detect_psm": 12},
    "detect1200": {"pipeline.detect_long_side": 1200},
    "detect2000": {"pipeline.detect_long_side": 2000},
    "detconf30": {"pipeline.detect_min_confidence": 30},
    "detconf55": {"pipeline.detect_min_confidence": 55},
    "margin1": {"pipeline.margin_factor": 1.0},
    "margin3": {"pipeline.margin_factor": 3.0},
    "pct35": {"pipeline.height_percentile": 35},
    "pct65": {"pipeline.height_percentile": 65},
    "smooth": {"pipeline.smooth_candidate": True},
    "short80": {"ocr.short_word_min_confidence": 80},
    "no-invert": {"ocr.do_invert": False},
    "h35": {"preprocess.target_text_height": 35},
    "h45": {"preprocess.target_text_height": 45},
    "h55": {"preprocess.target_text_height": 55},
    "best-model": {"ocr.tessdata_dir": BEST_MODEL},
    "fast-model": {"ocr.tessdata_dir": None},
    "gray": {"pipeline.inputs": ("gray",)},
    "binary": {"pipeline.inputs": ("binary",)},
    "both": {"pipeline.inputs": ("binary", "gray")},
    "gray-first": {"pipeline.inputs": ("gray", "binary")},
    "h30": {"preprocess.target_text_height": 30},
    "h40": {"preprocess.target_text_height": 40},
    "h50": {"preprocess.target_text_height": 50},
    "h60": {"preprocess.target_text_height": 60},
    "border20": {"preprocess.border": 20},
    "psm6": {"ocr.psms": (6,)},
    "psm4": {"ocr.psms": (4,)},
    "psm3": {"ocr.psms": (3,)},
    "psm11": {"ocr.psms": (11,)},
    "psm6+11": {"ocr.psms": (6, 11)},
    "psm6+4": {"ocr.psms": (6, 4)},
    "psm6+4+11": {"ocr.psms": (6, 4, 11)},
    "clahe": {"preprocess.clahe": True},
    "unsharp": {"preprocess.unsharp": True},
    "nlmeans": {"preprocess.denoise": "nlmeans"},
    "median": {"preprocess.denoise": "median"},
    "nodenoise": {"preprocess.denoise": "none"},
    "perspective": {"preprocess.perspective": True},
    "no-deskew": {"preprocess.deskew": False},
    "oem1": {"ocr.oem": 1},
    "do-invert": {"ocr.do_invert": True},
    "select-mean": {"ocr.select": "mean"},
    "select-sum": {"ocr.select": "sum"},
    "conf50": {"ocr.min_confidence": 50},
    "conf70": {"ocr.min_confidence": 70},
    "block41": {"preprocess.threshold_block": 41},
    "block91": {"preprocess.threshold_block": 91},
    "c8": {"preprocess.threshold_c": 8},
    "c25": {"preprocess.threshold_c": 25},
    "early90": {"ocr.early_exit_confidence": 90},
    "persp-both": {"preprocess.perspective": True, "pipeline.perspective_fallback": True},
    "persp-only": {"preprocess.perspective": True, "pipeline.perspective_fallback": False},
    "no-persp": {"preprocess.perspective": False},
    "select-conf": {"ocr.select": "confident"},
    "select-guarded": {"ocr.select": "guarded"},
    "guard50": {"ocr.select": "guarded", "ocr.guard_fraction": 0.5},
    "guard85": {"ocr.select": "guarded", "ocr.guard_fraction": 0.85},
    "h40": {"preprocess.target_text_height": 40},
    "border0": {"preprocess.border": 0},
    "conf60": {"ocr.min_confidence": 60},
    "no-unsharp": {"preprocess.unsharp": False},
    "short0": {"ocr.short_word_min_confidence": 0},
    "detect1600": {"pipeline.detect_long_side": 1600},
    "h55+border20": {"preprocess.target_text_height": 55, "preprocess.border": 20},
    "h55+detect1200": {"preprocess.target_text_height": 55, "pipeline.detect_long_side": 1200},
    "border20+detect1200": {"preprocess.border": 20, "pipeline.detect_long_side": 1200},
    "h55+border20+detect1200": {"preprocess.target_text_height": 55, "preprocess.border": 20, "pipeline.detect_long_side": 1200},
    "h50": {"preprocess.target_text_height": 50},
    "union": {"ocr.union": True},
    "no-union": {"ocr.union": False},
    "union70": {"ocr.union": True, "ocr.union_min_confidence": 70},
    "union80": {"ocr.union": True, "ocr.union_min_confidence": 80},
    "union85": {"ocr.union": True, "ocr.union_min_confidence": 85},
    "no-skew-words": {"pipeline.skew_from_words": False},
    "no-polarity-words": {"pipeline.polarity_from_words": False},
    "reliable60": {"pipeline.reliable_confidence": 60},
    "reliable80": {"pipeline.reliable_confidence": 80},
    "fb-none": {"ocr.fallback_psms": ()},
    "fb-11": {"ocr.fallback_psms": (11,)},
    "fb-4": {"ocr.fallback_psms": (4,)},
    "fb-4-11": {"ocr.fallback_psms": (4, 11)},
    "fb-min2": {"ocr.fallback_min_words": 2},
    "fb-min5": {"ocr.fallback_min_words": 5},
    "single80": {"ocr.union_single_char_min_confidence": 80},
    "single90": {"ocr.union_single_char_min_confidence": 90},
    "skew-words": {"pipeline.skew_source": "words"},
    "skew-blobs": {"pipeline.skew_source": "blobs"},
    "skew-agree": {"pipeline.skew_source": "agree"},
    "no-seed": {"pipeline.seed_confidence": 200},
    "seed80": {"pipeline.seed_confidence": 80},
    "seed92": {"pipeline.seed_confidence": 92},
    "no-rescue": {"pipeline.rescue_min_words": 0, "pipeline.orientation_rescue": False},
    "no-orient": {"pipeline.orientation_rescue": False},
    "no-retry": {"pipeline.detect_retry_long_side": 0},
    "rescue3": {"pipeline.rescue_min_words": 3},
    "no-component-guard": {"pipeline.max_binary_components": 0},
    "components3000": {"pipeline.max_binary_components": 3000},
    "components10000": {"pipeline.max_binary_components": 10000},
    "early85": {"ocr.early_exit_confidence": 85},
    "early95": {"ocr.early_exit_confidence": 95},
    "early-off": {"ocr.early_exit_confidence": 101},
    "max4000": {"preprocess.max_long_side": 4000},
    "max2600": {"preprocess.max_long_side": 2600},
}


def build_options(overrides: dict) -> PipelineOptions:
    pre, ocr, pipe = {}, {}, {}
    for key, value in overrides.items():
        section, _, name = key.partition(".")
        {"preprocess": pre, "ocr": ocr, "pipeline": pipe}[section][name] = value
    return PipelineOptions(preprocess=PreprocessOptions(**pre), ocr=OcrOptions(**ocr), **pipe)


def parse_set(raw: str) -> tuple[str, object]:
    key, _, value = raw.partition("=")
    if value.lower() in ("true", "false"):
        return key, value.lower() == "true"
    if value.lower() in ("none", "null"):
        return key, None
    if "," in value:
        return key, tuple(_scalar(v) for v in value.split(",") if v != "")
    if key in ("ocr.psms", "pipeline.inputs"):
        return key, (_scalar(value),)
    return key, _scalar(value)


def _scalar(value: str):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def load_dataset(count: int, seed: int, real_manifest: str | None) -> list[dict]:
    """Synthetic samples are cached on disk so every variant sees identical bytes."""
    samples = []
    if count > 0:
        folder = CACHE / f"synth-{seed}-{count}"
        index = folder / "index.json"
        if not index.exists():
            folder.mkdir(parents=True, exist_ok=True)
            generated = synth.generate(count, seed)
            for s in generated:
                (folder / f"{s.id}.jpg").write_bytes(s.jpeg)
            index.write_text(json.dumps([{k: v for k, v in asdict(s).items() if k != "jpeg"} for s in generated]))
        for entry in json.loads(index.read_text()):
            entry["path"] = str(folder / f"{entry['id']}.jpg")
            entry["source"] = "synthetic"
            samples.append(entry)
    if real_manifest:
        base = Path(real_manifest).parent
        for entry in json.loads(Path(real_manifest).read_text()):
            samples.append({
                "id": entry["file"],
                "path": str(base / entry["file"]),
                "lines": entry["lines"],
                "tags": ["real"] + entry.get("tags", []),
                "source": "real",
            })
    return samples


def _init_worker():
    # One Tesseract thread per process; the pool provides the parallelism.
    os.environ["OMP_THREAD_LIMIT"] = "1"


def evaluate_one(args: tuple[dict, dict, int]) -> dict:
    sample, overrides, upscale = args
    options = build_options(overrides)
    bgr = decode_image(Path(sample["path"]).read_bytes())
    if upscale:
        import cv2

        factor = upscale / max(bgr.shape[:2])
        bgr = cv2.resize(bgr, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC if factor > 1 else cv2.INTER_AREA)
    started = time.perf_counter()
    try:
        result = run(bgr, options)
        predicted = [l.text for l in result.recognition.lines]
        candidate = result.recognition.candidate
    except Exception as err:  # keep the benchmark going; count it as a total miss
        predicted, candidate = [], f"error: {err}"
    elapsed = time.perf_counter() - started
    precision, recall, f1 = word_prf(predicted, sample["lines"])
    return {
        "id": sample["id"],
        "source": sample["source"],
        "tags": sample["tags"],
        "truth": sample["lines"],
        "predicted": predicted,
        "candidate": candidate,
        "cer": cer(predicted, sample["lines"]),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "line_recall": line_recall(predicted, sample["lines"]),
        "seconds": elapsed,
    }


def summarise(rows: list[dict]) -> dict:
    def mean(key):
        return statistics.fmean(r[key] for r in rows) if rows else 0.0

    latencies = sorted(r["seconds"] for r in rows)
    return {
        "n": len(rows),
        "cer": mean("cer"),
        "f1": mean("f1"),
        "precision": mean("precision"),
        "recall": mean("recall"),
        "line_recall": mean("line_recall"),
        "exact": sum(r["cer"] == 0 for r in rows) / max(1, len(rows)),
        "p50_ms": 1000 * latencies[len(latencies) // 2] if latencies else 0,
        "p90_ms": 1000 * latencies[int(len(latencies) * 0.9)] if latencies else 0,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variants", default="defaults", help="comma-separated variant names")
    parser.add_argument("--set", action="append", default=[], help="override applied to every variant, e.g. ocr.psms=6,11")
    parser.add_argument("--n", type=int, default=120, help="number of synthetic samples")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--real", default=None, help="path to a real-photo manifest.json")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--out", default=str(CACHE / "results.json"))
    parser.add_argument("--show-misses", type=int, default=0, help="print the N worst samples per variant")
    parser.add_argument("--upscale", type=int, default=0, help="resize every image so its long side is this many px (simulates phone uploads)")
    args = parser.parse_args(argv)

    samples = load_dataset(args.n, args.seed, args.real)
    common = dict(parse_set(s) for s in args.set)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    report: dict[str, dict] = {}

    print(f"{len(samples)} samples ({sum(s['source'] == 'real' for s in samples)} real), {args.jobs} workers")
    header = f"{'variant':<16} {'CER':>7} {'wordF1':>7} {'lineRec':>8} {'exact':>6} {'p50ms':>7} {'p90ms':>7}"
    print(header)
    print("-" * len(header))
    for name in variants:
        overrides = {**common, **VARIANTS[name]}
        with ProcessPoolExecutor(max_workers=args.jobs, initializer=_init_worker) as pool:
            rows = list(pool.map(evaluate_one, [(s, overrides, args.upscale) for s in samples], chunksize=2))
        overall = summarise(rows)
        by_tag = defaultdict(list)
        for r in rows:
            for t in r["tags"]:
                by_tag[t].append(r)
        report[name] = {"overrides": {k: (list(v) if isinstance(v, tuple) else v) for k, v in overrides.items()},
                        "overall": overall, "by_tag": {t: summarise(v) for t, v in sorted(by_tag.items())}, "rows": rows}
        print(f"{name:<16} {overall['cer']:>7.3f} {overall['f1']:>7.3f} {overall['line_recall']:>8.3f} "
              f"{overall['exact']:>6.2f} {overall['p50_ms']:>7.0f} {overall['p90_ms']:>7.0f}", flush=True)
        if args.show_misses:
            for r in sorted(rows, key=lambda r: -r["cer"])[: args.show_misses]:
                print(f"   {r['id']:<18} cer={r['cer']:.2f} tags={','.join(r['tags'])} via {r['candidate']}")
                print(f"      truth: {r['truth']}")
                print(f"      got:   {r['predicted']}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    if len(variants) > 1:
        print("\nper-tag CER:")
        tags = sorted({t for v in report.values() for t in v["by_tag"]})
        print(f"{'tag':<14}" + "".join(f"{v:>12}" for v in variants))
        for t in tags:
            print(f"{t:<14}" + "".join(f"{report[v]['by_tag'].get(t, {'cer': float('nan')})['cer']:>12.3f}" for v in variants))


if __name__ == "__main__":
    sys.exit(main())
