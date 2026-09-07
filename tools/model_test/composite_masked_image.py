#!/usr/bin/env python3
"""Deterministically copy masked pixels from one same-size image to another."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFilter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--feather", type=float, default=0.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    destination = Image.open(args.destination).convert("RGB")
    source = Image.open(args.source).convert("RGB")
    mask = Image.open(args.mask).convert("L")
    if destination.size != source.size or destination.size != mask.size:
        raise ValueError(
            f"Image sizes differ: destination={destination.size}, "
            f"source={source.size}, mask={mask.size}"
        )
    if args.feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(args.feather))
    result = Image.composite(source, destination, mask)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)

    report = {
        "schema": "assetsstudio_masked_composite_v1",
        "destination": str(args.destination),
        "destination_sha256": sha256(args.destination),
        "source": str(args.source),
        "source_sha256": sha256(args.source),
        "mask": str(args.mask),
        "mask_sha256": sha256(args.mask),
        "feather": args.feather,
        "output": str(args.output),
        "output_sha256": sha256(args.output),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
