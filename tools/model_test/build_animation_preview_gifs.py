#!/usr/bin/env python3
"""Build four lightweight review GIFs from Blender motion sample frames."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--duration-ms", type=int, default=294)
    args = parser.parse_args()
    report_path = args.report.resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    outputs: dict[str, str] = {}
    contact_rows: list[list[Image.Image]] = []
    for direction, paths in report["preview_frames"].items():
        frames = [Image.open(path).convert("RGB") for path in paths]
        if not frames:
            raise RuntimeError(f"no preview frames for {direction}")
        destination = report_path.parent / f"{direction}.gif"
        frames[0].save(
            destination,
            save_all=True,
            append_images=frames[1:],
            duration=args.duration_ms,
            loop=0,
            optimize=True,
        )
        contact_rows.append(frames)
        outputs[direction] = str(destination)
    tile = 200
    sheet = Image.new(
        "RGB",
        (tile * max(len(row) for row in contact_rows), tile * len(contact_rows)),
        (18, 24, 34),
    )
    for row_index, frames in enumerate(contact_rows):
        for column_index, frame in enumerate(frames):
            sheet.paste(frame.resize((tile, tile), Image.Resampling.LANCZOS), (column_index * tile, row_index * tile))
            frame.close()
    contact_sheet = report_path.parent / "four_direction_contact_sheet.png"
    sheet.save(contact_sheet)
    sheet.close()
    report["preview_gifs"] = outputs
    report["contact_sheet"] = str(contact_sheet)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "ASSETSSTUDIO_ANIMATION_PREVIEW_GIFS_PASS "
        f"directions={len(outputs)} report={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
