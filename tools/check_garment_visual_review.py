"""Audit rendered garment review frames and create a human-review record.

This is intentionally a second gate beside the Blender fit detector.  Signed
distance and topology checks cannot prove side silhouette coverage or a clean
back crotch opening, so this script measures the highlighted garment mask in
the actual 4-direction x 8-frame Gallery renders and always leaves a pending
human review decision.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


DIRECTIONS = ("front", "right", "back", "left")


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fit-report", type=Path)
    parser.add_argument("--gallery-path", type=str, default="")
    parser.add_argument("--garment-kind", choices=("auto", "pants", "tshirt"), default="auto")
    parser.add_argument("--highlight-color", default="0.08,0.30,0.85,1.0")
    parser.add_argument("--side-coverage-threshold", type=float, default=0.65)
    return parser.parse_args()


def highlight_mask(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[:, :, :3].astype(np.int16)
    return (
        (rgb[:, :, 2] - rgb[:, :, 0] > 35)
        & (rgb[:, :, 2] - rgb[:, :, 1] > 35)
        & (rgb[:, :, 2] > 60)
    )


def component_count(mask: np.ndarray) -> int:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    count = 0
    for y, x in zip(*np.where(mask)):
        if visited[y, x]:
            continue
        count += 1
        queue: deque[tuple[int, int]] = deque([(int(y), int(x))])
        visited[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
    return count


def inspect_frame(path: Path, direction: str, side_threshold: float, garment_kind: str) -> dict[str, object]:
    rgba = np.array(Image.open(path).convert("RGBA"))
    actor = rgba[:, :, 3] > 10
    garment = highlight_mask(rgba)
    ys, _xs = np.where(actor)
    if not len(ys):
        return {"status": "fail", "reason": "empty_actor_alpha", "path": str(path)}
    top = int(ys.min())
    bottom = int(ys.max())
    if garment_kind == "tshirt":
        upper_start = top + round((bottom - top) * 0.20)
        upper_end = top + round((bottom - top) * 0.68)
        roi_garment = garment[upper_start : upper_end + 1]
        components = component_count(roi_garment)
        garment_pixels = int(roi_garment.sum())
        return {
            "path": str(path),
            "direction": direction,
            "upper_body_roi": [upper_start, upper_end],
            "upper_body_garment_pixels": garment_pixels,
            "upper_body_component_count": components,
            "tshirt_upper_body_status": "fail" if garment_pixels < 100 else "pass_or_review",
            "tshirt_shoulders_cuffs_status": "manual_review",
        }

    lower_start = top + round((bottom - top) * 0.68)
    lower_end = top + round((bottom - top) * 0.90)
    roi_actor = actor[lower_start : lower_end + 1]
    roi_garment = garment[lower_start : lower_end + 1]
    row_ratios = []
    for actor_row, garment_row in zip(roi_actor, roi_garment):
        actor_count = int(actor_row.sum())
        if actor_count >= 10:
            row_ratios.append(float(garment_row.sum() / actor_count))
    coverage = float(np.median(row_ratios)) if row_ratios else 0.0
    components = component_count(roi_garment)
    side_fail = direction in {"right", "left"} and coverage < side_threshold
    back_fail = direction == "back" and components > 1
    return {
        "path": str(path),
        "direction": direction,
        "lower_body_roi": [lower_start, lower_end],
        "garment_pixels": int(roi_garment.sum()),
        "median_lower_body_coverage": round(coverage, 4),
        "garment_component_count": components,
        "side_outer_thigh_status": "fail" if side_fail else "pass_or_review",
        "back_crotch_continuity_status": "fail" if back_fail else "pass_or_review",
    }


def main() -> int:
    options = args()
    render_dir = options.render_dir.resolve()
    garment_kind = options.garment_kind
    if garment_kind == "auto":
        garment_kind = "tshirt" if any(token in str(render_dir).lower() for token in ("tshirt", "shirt")) else "pants"
    expected = [render_dir / f"{direction}_{frame:02d}.png" for direction in DIRECTIONS for frame in range(8)]
    missing = [str(path) for path in expected if not path.is_file()]
    frames = []
    for direction in DIRECTIONS:
        for frame in range(8):
            path = render_dir / f"{direction}_{frame:02d}.png"
            if path.is_file():
                frames.append(inspect_frame(path, direction, options.side_coverage_threshold, garment_kind))

    side_failures = [item for item in frames if item.get("side_outer_thigh_status") == "fail"]
    back_failures = [item for item in frames if item.get("back_crotch_continuity_status") == "fail"]
    upper_body_failures = [item for item in frames if item.get("tshirt_upper_body_status") == "fail"]
    if garment_kind == "tshirt":
        automatic_status = "fail_visual" if missing or upper_body_failures else "review_required"
    else:
        automatic_status = "fail_visual" if missing or side_failures or back_failures else "review_required"
    fit_status = None
    if options.fit_report and options.fit_report.is_file():
        fit_payload = json.loads(options.fit_report.read_text(encoding="utf-8"))
        fit_status = fit_payload.get("status")

    if garment_kind == "tshirt":
        human_review = {
            "status": "pending",
            "reviewer": "",
            "reviewed_at": "",
            "front_coverage": "pending",
            "shoulder_connection": "pending",
            "cuff_exit": "pending",
            "side_silhouette": "pending",
            "face_and_expression": "pending",
            "bone_animation": "pending",
            "notes": "Human review is mandatory; automatic checks only verify upper-body garment pixels.",
        }
        human_acceptance = [
            "human_review.shoulder_connection == pass",
            "human_review.cuff_exit == pass",
            "human_review.side_silhouette == pass",
            "human_review.bone_animation == pass",
        ]
    else:
        human_review = {
            "status": "pending",
            "reviewer": "",
            "reviewed_at": "",
            "front_coverage": "pending",
            "side_outer_thigh": "pending",
            "back_crotch_continuity": "pending",
            "face_and_expression": "pending",
            "bone_animation": "pending",
            "notes": "Human review is mandatory; automatic visual checks never authorize success by themselves.",
        }
        human_acceptance = [
            "human_review.side_outer_thigh == pass",
            "human_review.back_crotch_continuity == pass",
            "human_review.bone_animation == pass",
        ]

    report = {
        "schema": "assetslab_garment_visual_review_v1",
        "render_dir": str(render_dir),
        "gallery_path": options.gallery_path,
        "garment_kind": garment_kind,
        "fit_report": str(options.fit_report.resolve()) if options.fit_report else None,
        "mechanical_fit_status": fit_status,
        "automatic_visual_status": automatic_status,
        "missing_frames": missing,
        "thresholds": {
            "side_coverage_median_min": options.side_coverage_threshold,
            "back_max_expected_components": 1,
        },
        "failures": {
            "tshirt_upper_body": upper_body_failures,
            "side_outer_thigh": side_failures,
            "back_crotch_continuity": back_failures,
        },
        "frames": frames,
        "human_review": human_review,
        "acceptance": {
            "success_requires": [
                "mechanical_fit_status == pass",
                "automatic_visual_status == review_required",
                "human_review.status == approved",
                *human_acceptance,
            ],
            "status": "not_accepted",
        },
    }
    output = options.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "automatic_visual_status": automatic_status}, indent=2))
    return 1 if automatic_status == "fail_visual" else 0


if __name__ == "__main__":
    raise SystemExit(main())
