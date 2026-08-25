# 环境发现与模型资产

## 发现规则

所有入口按以下顺序解析环境：

1. 显式命令行参数；
2. 专用环境变量；
3. AssetsStudio 相邻目录；
4. 用户目录中的常见安装位置或模型缓存。

找不到时应列出已检查位置并停止，不在文档中写死盘符。

### ComfyUI / FLUX.2

- `ASSETSSTUDIO_COMFY_ROOT`：可选 ComfyUI 根目录。
- `ASSETSSTUDIO_PYTHON`：可选 Python 可执行文件或命令。
- 启动器也会搜索相邻 `ComfyUI`、其 `.venv`/`venv`/嵌入式 Python、当前虚拟环境和 PATH。

需要：

- `flux-2-klein-4b-fp8.safetensors`
- `qwen_3_4b.safetensors`
- `flux2-vae.safetensors`

### Hunyuan3D

- `HUNYUAN3D_SOURCE`：可选官方源码根目录。
- `HUNYUAN3D_MODEL_ROOT`：可选 `Hunyuan3D-2mv` 模型根目录。
- 默认还搜索相邻 `Hunyuan3D_Experiment` 与 ModelScope/Hugging Face 缓存。

优先用 ModelScope 获取官方 `Tencent-Hunyuan/Hunyuan3D-2mv`。只保留形状模型的 `config.yaml` 与拆分后的 `model.pt`、`vae.pt`、`conditioner.pt`；拆分成功后完整 checkpoint 是可删除的重复运行资产。

### 素体图像模型增强

- 当前强编辑基线是 Qwen-Image-Edit-2511。推理主模型使用 ModelScope `unsloth/Qwen-Image-Edit-2511-GGUF` 的 Q3_K_M 量化；文本编码器和 VAE 使用 ModelScope `Comfy-Org/Qwen-Image_ComfyUI`。不从 Hugging Face 下载，不把模型文件提交到 Git。
- 运行节点使用 `city96/ComfyUI-GGUF`，固定提交 `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`。当前验证环境为 ComfyUI `0d80858061b511bd38c8cef4c235ef8e01040822`、Python 3.10.20、PyTorch 2.11.0+cu128。
- `tools/setup_qwen_actor_core_environment.ps1` 按 `-ComfyRoot`、`ASSETSSTUDIO_COMFY_ROOT`、项目相邻 `ComfyUI`、用户目录 `ComfyUI` 的顺序搜索环境；Python 按 `-Python`、`ASSETSSTUDIO_PYTHON`、ComfyUI 虚拟环境和 PATH 搜索。脚本会安装固定版本节点、从 ModelScope 断点下载并按精确文件大小校验。
- 推理所需文件如下，路径均相对 ComfyUI 根目录：
  - `models/diffusion_models/qwen-image-edit-2511-Q3_K_M.gguf`：9,920,805,472 bytes；
  - `models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`：9,384,670,680 bytes；
  - `models/vae/qwen_image_vae.safetensors`：253,806,246 bytes。
- 安装或恢复环境：`powershell -ExecutionPolicy Bypass -File .\tools\setup_qwen_actor_core_environment.ps1`。只检查不修改：追加 `-CheckOnly`。
- 固定基线由 `tools/model_test/run_comfy_qwen_image_edit.py` 提交到 ComfyUI。首次实验采用 20 steps、CFG 4、Euler/simple、AuraFlow shift 3.1、`index_timestep_zero` reference latent method，并把失败候选仅写入 ComfyUI `output/assetsstudio`。
- LoRA 训练环境尚未安装。只有在两阶段通用编辑仍无法稳定通过 Gate 时，才引入 Musubi Tuner 的 Qwen-Image/Edit-2511 训练路径；12GB 显存配置必须启用 FP8、VL 编码器 FP8、gradient checkpointing、block swap，并将首轮训练分辨率限制在 768 或更低。
- LoRA 的任务不是固定一个项目角色，而是学习 `strip_to_actor_core`：输入完整风格角色，输出同姿态、同头身比、无身份无部件的标准素体。项目和风格通过标签与独立 StyleProfile 控制。
- FLUX.2 Klein 4B 保留用于快速风格种子和配件草案，不再作为标准 Actor Core 的权威编辑模型。

## RTX 3060 12 GiB

- Qwen Actor Core 基线使用 Q3_K_M 主模型和 FP8 文本编码器；启动 ComfyUI 时使用 `--lowvram --cache-none --preview-method none`，保留 DynamicVRAM 和异步权重卸载。当前 16GB 验证机峰值约 13.2GB，12GB 会增加 CPU/RAM 换入，建议 32GB 以上系统内存和系统管理的页面文件。
- FLUX 使用 FP8、`--lowvram`、关闭 pinned memory/异步 offload、无预览缓存。
- Hunyuan 使用拆分权重、CPU offload、较低 octree resolution，再由 Blender 做拓扑与预览。
- 纹理不在 Hunyuan 形体阶段解决。优先采用低分辨率语义色块、共享材质、2K 或更小图集、烘焙 AO/法线和按需局部重绘；不要在 12 GiB 显存上把高分辨率多视图纹理扩散绑进形体生成。

验证当前机器：

```powershell
python .\tools\validate_studio_local_generation.py --check-models
```
