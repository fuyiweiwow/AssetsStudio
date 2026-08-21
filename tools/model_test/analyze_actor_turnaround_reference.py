"""Measure a four-view Actor reference sheet before 3D reconstruction.

The input directory must contain front.png, right.png, back.png, and left.png.
Outputs are intentionally image-source diagnostics rather than model QA: one
foreground mask and JSON record per view plus aligned silhouette overlays.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


VIEWS = ("front", "right", "back", "left")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--head-count-min", type=float, default=1.90)
    parser.add_argument("--head-count-max", type=float, default=2.30)
    parser.add_argument("--height-drift-ratio-max", type=float, default=0.025)
    parser.add_argument("--ground-drift-px-max", type=int, default=8)
    parser.add_argument("--side-mirror-iou-min", type=float, default=0.88)
    parser.add_argument("--front-back-iou-min", type=float, default=0.88)
    return parser.parse_args()


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        raise RuntimeError("no foreground component found")
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    output = np.zeros_like(mask)
    output[labels == index] = 255
    return output


def foreground_mask(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    # The archived splitter centers a narrow source panel on a white square.
    # Running GrabCut on the square would classify the whole gray panel as one
    # foreground rectangle, so first recover the non-white panel bounds.
    nonwhite = np.mean(np.abs(image.astype(np.int16) - 255), axis=(0, 2)) > 1.0
    panel_columns = np.flatnonzero(nonwhite)
    if panel_columns.size == 0:
        raise RuntimeError("could not locate the source panel inside the square image")
    panel_x0 = int(panel_columns[0])
    panel_x1 = int(panel_columns[-1]) + 1
    panel = image[:, panel_x0:panel_x1]
    panel_width = panel.shape[1]
    margin_x = max(4, int(panel_width * 0.06))
    margin_y = max(4, int(height * 0.08))
    rect = (
        margin_x,
        margin_y,
        panel_width - margin_x * 2,
        height - margin_y * 2,
    )
    grab_mask = np.zeros((height, panel_width), np.uint8)
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(
        panel,
        grab_mask,
        rect,
        background_model,
        foreground_model,
        7,
        cv2.GC_INIT_WITH_RECT,
    )
    panel_mask = np.where(
        (grab_mask == cv2.GC_FGD) | (grab_mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    panel_mask = cv2.morphologyEx(panel_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    panel_mask = largest_component(panel_mask)
    mask = np.zeros((height, width), np.uint8)
    mask[:, panel_x0:panel_x1] = panel_mask
    return mask


def bbox_for(mask: np.ndarray) -> tuple[int, int, int, int]:
    points = cv2.findNonZero(mask)
    if points is None:
        raise RuntimeError("empty foreground mask")
    return tuple(int(value) for value in cv2.boundingRect(points))


def centroid_for(mask: np.ndarray) -> tuple[float, float]:
    moments = cv2.moments(mask, binaryImage=True)
    if moments["m00"] == 0:
        raise RuntimeError("empty foreground moments")
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def neck_row(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> int:
    x, y, width, height = bbox
    row_widths = np.count_nonzero(mask[:, x : x + width], axis=1).astype(np.float32)
    row_widths = cv2.GaussianBlur(row_widths.reshape(-1, 1), (1, 15), 0).ravel()
    start = y + int(height * 0.34)
    end = y + int(height * 0.58)
    return start + int(np.argmin(row_widths[start:end]))


def analyze_view(path: Path, output_dir: Path) -> tuple[np.ndarray, dict[str, object]]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read {path}")
    mask = foreground_mask(image)
    bbox = bbox_for(mask)
    centroid = centroid_for(mask)
    neck_y = neck_row(mask, bbox)
    x, y, width, height = bbox
    head_height = neck_y - y + 1
    analysis = {
        "schema": "assetsstudio_actor_reference_view_analysis_v1",
        "source": str(path.resolve()),
        "image_size": [int(image.shape[1]), int(image.shape[0])],
        "component_count": 1,
        "foreground_area_px": int(np.count_nonzero(mask)),
        "bbox_xywh": [x, y, width, height],
        "centroid_xy": [round(centroid[0], 3), round(centroid[1], 3)],
        "top_y": y,
        "ground_y": y + height - 1,
        "neck_y": neck_y,
        "head_height_px": head_height,
        "visual_head_count": round(height / head_height, 4),
    }
    cv2.imwrite(str(output_dir / f"{path.stem}_mask.png"), mask)
    (output_dir / f"{path.stem}.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return mask, analysis


def aligned(mask: np.ndarray, target_center_x: float, target_ground_y: int) -> np.ndarray:
    bbox = bbox_for(mask)
    center_x = bbox[0] + bbox[2] / 2.0
    ground_y = bbox[1] + bbox[3] - 1
    matrix = np.float32(
        [[1, 0, round(target_center_x - center_x)], [0, 1, target_ground_y - ground_y]]
    )
    return cv2.warpAffine(mask, matrix, (mask.shape[1], mask.shape[0]), flags=cv2.INTER_NEAREST)


def compare_masks(
    reference: np.ndarray,
    candidate: np.ndarray,
    overlay_path: Path,
    mirror_candidate: bool = False,
) -> dict[str, float]:
    if mirror_candidate:
        candidate = cv2.flip(candidate, 1)
    ref_bbox = bbox_for(reference)
    target_center = ref_bbox[0] + ref_bbox[2] / 2.0
    target_ground = ref_bbox[1] + ref_bbox[3] - 1
    candidate = aligned(candidate, target_center, target_ground)
    ref_bool = reference > 0
    candidate_bool = candidate > 0
    intersection = int(np.count_nonzero(ref_bool & candidate_bool))
    union = int(np.count_nonzero(ref_bool | candidate_bool))
    iou = intersection / union if union else 0.0
    overlay = np.full((*reference.shape, 3), 245, np.uint8)
    overlay[ref_bool] = (255, 170, 0)
    overlay[candidate_bool] = (0, 220, 255)
    overlay[ref_bool & candidate_bool] = (100, 220, 100)
    cv2.imwrite(str(overlay_path), overlay)
    return {
        "iou": round(iou, 6),
        "reference_bbox_width": ref_bbox[2],
        "reference_bbox_height": ref_bbox[3],
        "candidate_bbox_width": bbox_for(candidate)[2],
        "candidate_bbox_height": bbox_for(candidate)[3],
    }


def main() -> None:
    args = parse_args()
    source_analysis = args.output_dir / "source_analysis"
    validation = args.output_dir / "validation"
    source_analysis.mkdir(parents=True, exist_ok=True)
    validation.mkdir(parents=True, exist_ok=True)

    masks: dict[str, np.ndarray] = {}
    analyses: dict[str, dict[str, object]] = {}
    for view in VIEWS:
        masks[view], analyses[view] = analyze_view(
            args.input_dir / f"{view}.png", source_analysis
        )

    side = compare_masks(
        masks["right"], masks["left"], validation / "side_mirror_overlay.png", True
    )
    front_back = compare_masks(
        masks["front"], masks["back"], validation / "front_back_overlay.png"
    )
    heights = [int(analyses[view]["bbox_xywh"][3]) for view in VIEWS]
    grounds = [int(analyses[view]["ground_y"]) for view in VIEWS]
    front_head_count = float(analyses["front"]["visual_head_count"])
    height_drift_ratio = (max(heights) - min(heights)) / max(heights)
    ground_drift_px = max(grounds) - min(grounds)
    gates = {
        "one_component_each_view": all(
            analyses[view]["component_count"] == 1 for view in VIEWS
        ),
        "front_head_count_in_visual_band": (
            args.head_count_min <= front_head_count <= args.head_count_max
        ),
        "height_drift": height_drift_ratio <= args.height_drift_ratio_max,
        "ground_drift": ground_drift_px <= args.ground_drift_px_max,
        "side_mirror_iou": side["iou"] >= args.side_mirror_iou_min,
        "front_back_iou": front_back["iou"] >= args.front_back_iou_min,
    }
    report = {
        "schema": "assetsstudio_actor_multiview_reference_validation_v1",
        "views": list(VIEWS),
        "measurements": {
            "height_px": dict(zip(VIEWS, heights)),
            "height_drift_ratio": round(height_drift_ratio, 6),
            "ground_y": dict(zip(VIEWS, grounds)),
            "ground_drift_px": ground_drift_px,
            "front_visual_head_count": front_head_count,
            "side_mirror": side,
            "front_back": front_back,
        },
        "thresholds": {
            "front_visual_head_count": [args.head_count_min, args.head_count_max],
            "height_drift_ratio_max": args.height_drift_ratio_max,
            "ground_drift_px_max": args.ground_drift_px_max,
            "side_mirror_iou_min": args.side_mirror_iou_min,
            "front_back_iou_min": args.front_back_iou_min,
        },
        "gates": gates,
        "status": "pass" if all(gates.values()) else "fail",
    }
    report_path = validation / "multiview_consistency.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"ACTOR_TURNAROUND_REFERENCE_{report['status'].upper()} report={report_path.resolve()}")


if __name__ == "__main__":
    main()
