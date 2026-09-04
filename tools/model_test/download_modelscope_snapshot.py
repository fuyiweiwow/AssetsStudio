#!/usr/bin/env python3
"""Download one explicitly requested ModelScope snapshot to a local directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from modelscope import snapshot_download


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-patterns",
        nargs="*",
        help="Optional ModelScope file globs; omit to download the complete snapshot.",
    )
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        args.model_id,
        local_dir=str(output),
        allow_patterns=args.allow_patterns or None,
    )
    print(f"MODELSCOPE_SNAPSHOT_READY={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
