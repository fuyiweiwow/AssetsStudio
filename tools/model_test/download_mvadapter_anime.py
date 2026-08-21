"""Download the local Anime SDXL base and MV-Adapter text-to-multiview weight."""

from huggingface_hub import snapshot_download


if __name__ == "__main__":
    anime_path = snapshot_download(
        "cagliostrolab/animagine-xl-3.1",
        local_dir=r"E:\env\models\animagine-xl-3.1",
        allow_patterns=[
            "model_index.json",
            "scheduler/*",
            "text_encoder/*",
            "text_encoder_2/*",
            "tokenizer/*",
            "tokenizer_2/*",
            "unet/*",
            "vae/*",
        ],
    )
    adapter_path = snapshot_download(
        "huanngzh/mv-adapter",
        local_dir=r"E:\env\models\mv-adapter",
        allow_patterns=["mvadapter_t2mv_sdxl.safetensors"],
    )
    print(f"ANIME_MODEL_DOWNLOAD_PASS {anime_path}")
    print(f"MVADAPTER_WEIGHT_DOWNLOAD_PASS {adapter_path}")
