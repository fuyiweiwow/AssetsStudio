#!/usr/bin/env python3
"""Apply the small, auditable Windows/offline UniRig skeleton patch set."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace(path: Path, old: str, new: str, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if old not in text:
        raise RuntimeError(f"UniRig source drift in {path}: expected patch context not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "run.py").is_file():
        raise FileNotFoundError(source / "run.py")

    replace(
        source / "src/model/parse.py",
        "from .unirig_ar import UniRigAR\nfrom .unirig_skin import UniRigSkin\n",
        "from .unirig_ar import UniRigAR\n",
        "if kwargs['__target__'] == 'unirig_skin':",
    )
    replace(
        source / "src/model/parse.py",
        "def get_model(**kwargs) -> ModelSpec:\n    MAP = {",
        "def get_model(**kwargs) -> ModelSpec:\n"
        "    if kwargs['__target__'] == 'unirig_skin':\n"
        "        from .unirig_skin import UniRigSkin\n"
        "    else:\n"
        "        UniRigSkin = None\n"
        "    MAP = {",
        "UniRigSkin = None",
    )
    replace(
        source / "src/model/parse_encoder.py",
        "from .pointcept.models.PTv3Object import get_encoder as get_encoder_ptv3obj\n"
        "from .pointcept.models.PTv3Object import PointTransformerV3Object\n",
        "",
        "get_encoder_ptv3obj = None",
    )
    replace(
        source / "src/model/parse_encoder.py",
        "    ptv3obj = PointTransformerV3Object\n",
        "",
        "get_encoder_ptv3obj = None",
    )
    replace(
        source / "src/model/parse_encoder.py",
        "def get_mesh_encoder(**kwargs):\n    MAP = {",
        "def get_mesh_encoder(**kwargs):\n"
        "    if kwargs['__target__'] == 'ptv3obj':\n"
        "        from .pointcept.models.PTv3Object import get_encoder as get_encoder_ptv3obj\n"
        "    else:\n"
        "        get_encoder_ptv3obj = None\n"
        "    MAP = {",
        "get_encoder_ptv3obj = None",
    )
    sampler = source / "src/model/michelangelo/models/tsal/sal_perceiver.py"
    replace(
        sampler,
        "from torch_cluster import fps\n",
        "",
        "Small inference-only farthest-point sampler",
    )
    replace(
        sampler,
        "import numpy as np\n\n",
        "import numpy as np\n\n\n"
        "def fps(pos, batch, ratio, random_start=False):\n"
        "    \"\"\"Small inference-only farthest-point sampler without torch-cluster.\"\"\"\n"
        "    indices = []\n"
        "    for batch_id in torch.unique(batch, sorted=True):\n"
        "        candidates = torch.nonzero(batch == batch_id, as_tuple=False).flatten()\n"
        "        count = max(1, int(round(len(candidates) * ratio)))\n"
        "        local = pos[candidates]\n"
        "        start = torch.randint(len(candidates), (1,), device=pos.device).item() if random_start else 0\n"
        "        chosen = torch.empty(count, dtype=torch.long, device=pos.device)\n"
        "        chosen[0] = start\n"
        "        distance = torch.full((len(candidates),), float('inf'), device=pos.device)\n"
        "        for index in range(1, count):\n"
        "            delta = local - local[chosen[index - 1]]\n"
        "            distance = torch.minimum(distance, (delta * delta).sum(dim=1))\n"
        "            chosen[index] = torch.argmax(distance)\n"
        "        indices.append(candidates[chosen])\n"
        "    return torch.cat(indices)\n\n",
        "Small inference-only farthest-point sampler",
    )
    unirig_ar = source / "src/model/unirig_ar.py"
    replace(
        unirig_ar,
        "from transformers import AutoModelForCausalLM, AutoConfig, LogitsProcessor, LogitsProcessorList",
        "from transformers import AutoModelForCausalLM, OPTConfig, LogitsProcessor, LogitsProcessorList",
        "OPTConfig, LogitsProcessor",
    )
    replace(
        unirig_ar,
        "        llm_config = AutoConfig.from_pretrained(**_d)",
        "        _d.pop('pretrained_model_name_or_path', None)\n        llm_config = OPTConfig(**_d)",
        "llm_config = OPTConfig(**_d)",
    )
    download = source / "src/inference/download.py"
    replace(download, "from huggingface_hub import hf_hub_download", "import os\nfrom huggingface_hub import hf_hub_download", "import os")
    replace(
        download,
        "def download(ckpt_name: str) -> str:\n    MAP = {",
        "def download(ckpt_name: str) -> str:\n"
        "    if os.path.isfile(ckpt_name):\n"
        "        return ckpt_name\n"
        "    MAP = {",
        "if os.path.isfile(ckpt_name):",
    )
    config = source / "configs/model/unirig_ar_350m_1024_81920_float32.yaml"
    replace(
        config,
        "  hidden_size: 1024\n  word_embed_proj_dim: 1024",
        "  hidden_size: 1024\n"
        "  ffn_dim: 4096\n"
        "  num_hidden_layers: 24\n"
        "  num_attention_heads: 16\n"
        "  word_embed_proj_dim: 1024",
        "  ffn_dim: 4096",
    )
    replace(config, "  _attn_implementation: flash_attention_2", "  _attn_implementation: sdpa", "  _attn_implementation: sdpa")
    replace(config, "  flash: True", "  flash: False", "  flash: False")
    (source / "ASSETSSTUDIO_SKELETON_PATCH_V1.txt").write_text(
        "offline skeleton-only patch v1\n", encoding="ascii"
    )
    print(f"UNIRIG_SKELETON_RUNTIME_PATCHED={source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
