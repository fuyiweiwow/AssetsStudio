"""Download the small official SDXL Canny ControlNet checkpoint."""

from huggingface_hub import snapshot_download


if __name__ == "__main__":
    output = snapshot_download(
        "diffusers/controlnet-canny-sdxl-1.0-small",
        local_dir=r"E:\env\models\controlnet-canny-sdxl-1.0-small",
        allow_patterns=["config.json", "diffusion_pytorch_model.fp16.safetensors"],
    )
    print(f"SDXL_CANNY_DOWNLOAD_PASS {output}")
