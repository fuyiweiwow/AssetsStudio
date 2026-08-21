from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--front-clear-left", type=int, default=0)
    return parser.parse_args()


def keep_largest_component(image: Image.Image, threshold: int) -> tuple[Image.Image, int, int]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    pixels = alpha.load()
    visited = bytearray(width * height)
    largest: list[tuple[int, int]] = []
    component_count = 0
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if visited[offset] or pixels[x, y] <= threshold:
                continue
            component_count += 1
            queue = deque([(x, y)])
            visited[offset] = 1
            component: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.popleft()
                component.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_offset = next_y * width + next_x
                    if visited[next_offset] or pixels[next_x, next_y] <= threshold:
                        continue
                    visited[next_offset] = 1
                    queue.append((next_x, next_y))
            if len(component) > len(largest):
                largest = component
    keep = set(largest)
    cleaned_alpha = Image.new("L", rgba.size, 0)
    cleaned_pixels = cleaned_alpha.load()
    for x, y in keep:
        cleaned_pixels[x, y] = pixels[x, y]
    rgba.putalpha(cleaned_alpha)
    return rgba, component_count, len(largest)


def main() -> int:
    options = arguments()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    for view in ("front", "right", "back", "left"):
        source = options.input_dir / f"{view}_rgba.png"
        output = options.output_dir / f"{view}_rgba.png"
        cleaned, components, pixels = keep_largest_component(
            Image.open(source), options.alpha_threshold
        )
        if view == "front" and options.front_clear_left > 0:
            alpha = cleaned.getchannel("A")
            alpha.paste(0, (0, 0, options.front_clear_left, alpha.height))
            cleaned.putalpha(alpha)
        if pixels == 0:
            raise RuntimeError(f"no foreground component found: {source}")
        cleaned.save(output)
        print(f"{view}: components={components} retained_pixels={pixels} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
