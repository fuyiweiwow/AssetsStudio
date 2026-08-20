"""Split the local Hunyuan mini checkpoint into low-peak-load component files."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--subfolder",
        default="hunyuan3d-dit-v2-mini-turbo",
        help="Checkpoint subfolder inside the model directory.",
    )
    args = parser.parse_args()
    model_dir = args.model.resolve() / args.subfolder
    source = model_dir / "model.fp16.ckpt"
    cache_dir = model_dir / "split_components"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"SPLIT_LOAD {source}", flush=True)
    checkpoint = torch.load(
        str(source), map_location="cpu", weights_only=True, mmap=True
    )
    for component in ("model", "vae", "conditioner"):
        destination = cache_dir / f"{component}.pt"
        if not destination.exists():
            print(f"SPLIT_WRITE {component} -> {destination}", flush=True)
            torch.save(checkpoint[component], str(destination))
    print(f"SPLIT_PASS cache={cache_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
