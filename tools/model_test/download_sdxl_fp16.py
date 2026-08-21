"""Download only the FP16 Diffusers files for the local SDXL fallback."""

from modelscope import snapshot_download


if __name__ == "__main__":
    output = snapshot_download(
        "AI-ModelScope/stable-diffusion-xl-base-1.0",
        local_dir=r"E:\env\models\sdxl-base-1.0-fp16",
        allow_file_pattern=[
            "model_index.json",
            "configuration.json",
            "scheduler/*",
            "text_encoder/config.json",
            "text_encoder/model.fp16.safetensors",
            "text_encoder_2/config.json",
            "text_encoder_2/model.fp16.safetensors",
            "tokenizer/*",
            "tokenizer_2/*",
            "unet/config.json",
            "unet/diffusion_pytorch_model.fp16.safetensors",
            "vae/config.json",
            "vae/diffusion_pytorch_model.fp16.safetensors",
        ],
    )
    print(f"SDXL_DOWNLOAD_PASS {output}")
