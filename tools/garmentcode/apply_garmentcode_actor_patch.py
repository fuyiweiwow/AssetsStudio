"""Idempotently add Actor sleeve fields to the pinned GarmentCode checkout."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PINNED_COMMIT = "d449629979028123a5c4dc9e732a2ec19b7fce31"
REPLACEMENTS = {
    "assets/garment_programs/bodice.py": (
        """        min_cwidth = body['_armscye_depth']
        v = design['sleeve']['connecting_width']['v']
        design['sleeve']['connecting_width']['v'] = min(min_cwidth + min_cwidth * v, max_cwidth)""",
        """        if 'actor_sleeve_connecting_width' in body:
            # Actor-complete authoring supplies the measured armscye opening
            # directly.  The generic GarmentCode relative parameter remains
            # the fallback for ordinary mean-body designs.
            design['sleeve']['connecting_width']['v'] = min(
                float(body['actor_sleeve_connecting_width']), max_cwidth
            )
        else:
            min_cwidth = body['_armscye_depth']
            v = design['sleeve']['connecting_width']['v']
            design['sleeve']['connecting_width']['v'] = min(min_cwidth + min_cwidth * v, max_cwidth)""",
    ),
    "assets/garment_programs/sleeves.py": (
        """        end_width = design['end_width']['v'] * abs(open_shape[0].start[1] - open_shape[-1].end[1])
        # Ensure it fits regardless of parameters
        end_width = max(end_width, body['wrist'] / 2)""",
        """        if 'actor_sleeve_cuff_circumference' in body:
            # The Actor-complete measurement is the full cuff circumference;
            # this panel is one half of the front/back sleeve pair.
            end_width = float(body['actor_sleeve_cuff_circumference']) / 2.0
        else:
            end_width = design['end_width']['v'] * abs(open_shape[0].start[1] - open_shape[-1].end[1])
            # Ensure it fits regardless of parameters
            end_width = max(end_width, body['wrist'] / 2)""",
    ),
}
SLEEVE_LENGTH_OLD = "        length = design['length']['v'] * (body['arm_length'] - opening_length)"
SLEEVE_LENGTH_NEW = """        if 'actor_sleeve_length' in body:
            length = float(body['actor_sleeve_length'])
        else:
            length = design['length']['v'] * (body['arm_length'] - opening_length)"""


def replace_once(source: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if new in source:
        return source, False
    if source.count(old) != 1:
        raise RuntimeError(f"cannot find exactly one clean source block: {label}")
    return source.replace(old, new, 1), True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmentcode-root", required=True, type=Path)
    options = parser.parse_args()
    root = options.garmentcode_root.resolve()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if commit != PINNED_COMMIT:
        raise RuntimeError(f"GarmentCode commit mismatch: {commit} != {PINNED_COMMIT}")

    changed = []
    for relative, (old, new) in REPLACEMENTS.items():
        path = root / relative
        # The upstream sleeve source contains a few trailing spaces.  Remove
        # only end-of-line whitespace before matching the pinned source blocks.
        source = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n"
        source, did_change = replace_once(source, old, new, relative)
        if relative.endswith("sleeves.py"):
            source, length_changed = replace_once(
                source, SLEEVE_LENGTH_OLD, SLEEVE_LENGTH_NEW, "actor sleeve length"
            )
            did_change = did_change or length_changed
        if did_change:
            path.write_text(source, encoding="utf-8")
            changed.append(relative)
    print(f"GARMENTCODE_ACTOR_PATCH_APPLIED changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
