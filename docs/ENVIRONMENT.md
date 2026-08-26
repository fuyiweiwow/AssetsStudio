# 环境发现与模型资产

## 发现规则

所有入口按顺序搜索：显式命令行参数、专用环境变量、AssetsStudio 相邻目录、用户目录常见安装位置与模型缓存。找不到时必须列出已检查位置并停止；文档和代码不得依赖某台机器的盘符绝对路径。

常用环境变量：

- `ASSETSSTUDIO_COMFY_ROOT`：可选 ComfyUI 根目录；
- `ASSETSSTUDIO_PYTHON`：可选 Python 可执行文件或命令；
- `HUNYUAN3D_SOURCE`：可选 Hunyuan3D 官方源码根目录；
- `HUNYUAN3D_MODEL_ROOT`：可选 Hunyuan3D-2mv 模型根目录。

## 默认生产推理：FLUX.2 Klein 4B

Studio 默认只要求以下 ComfyUI 文件：

- `models/diffusion_models/flux-2-klein-4b-fp8.safetensors`
- `models/text_encoders/qwen_3_4b.safetensors`
- `models/vae/flux2-vae.safetensors`

这里的 `qwen_3_4b.safetensors` 是 FLUX.2 Klein 的文本编码器，不代表生产链使用 Qwen-Image-Edit。

启动器使用 `--lowvram --cache-none --preview-method none`，并关闭 pinned memory 与异步 offload；入口负责搜索环境而不是要求固定目录。检查：

```powershell
python .\tools\validate_studio_local_generation.py --check-models
```

## 可选训练环境：Klein Base + DiffSynth

LoRA 训练主候选是 ModelScope `black-forest-labs/FLUX.2-klein-base-4B`。完整仓库约 23.74GB，其中 Base Transformer 单文件约 7.75GB；不要在没有批准 Pair 时下载整仓，也不要重复下载已经存在的文本编码器/VAE。

训练工具优先使用 ModelScope `modelscope/DiffSynth-Studio`。它支持 FLUX.2 图像编辑、LoRA、FP8、gradient checkpointing、CPU offload 和两阶段缓存。训练环境尚未作为 Studio 必需环境安装；只有满足以下条件才安装：

1. 至少一组 Pair 已人工批准；
2. 明确选择本机小规模验证或远程训练机；
3. 磁盘空间与系统内存检查通过；
4. 下载计划只包含所需文件并使用 ModelScope 断点续传。

Base 常规推理约需 13GB 显存，常规 LoRA 示例按约 24GB 设计，因此 RTX 3060 不承担“必须舒适训练”的承诺。训练可远程完成；LoRA + distilled 推理必须回到真实 3060 验收。

## Qwen-Image-Edit 的状态

Qwen-Image-Edit 已从必需环境和默认验证中移除。历史 Q3 零样本实验用于记录失败模式；它可作为可选远程/本地教师，但 Studio 启动、Pair schema、FLUX 导出和生产推理均不得依赖它。旧环境脚本与推理脚本仅为可恢复实验适配器，后续项目瘦身时可单独归档或删除。

## RTX 3060 12GB 硬门槛

- 生产编辑必须离线运行；目标峰值显存约 11.5GB 以下；
- 当前 5070 Ti 限额测试只能预筛选，不能替代真实 3060；
- 当前 Klein distilled 1536×768/4-step 测试增量峰值 11,688MiB，任务质量仍需 LoRA；
- 若训练后 LoRA 不能在 3060 稳定加载和编辑，则 Klein 不进入生产，改做 SDXL 回退验证；
- 系统内存与页面文件只用于可接受的权重换入，不能把极慢 CPU 换页包装成“可用”。

## Hunyuan3D 与纹理

优先从 ModelScope 获取官方 `Tencent-Hunyuan/Hunyuan3D-2mv`。只保留形状模型 `config.yaml` 与拆分后的 `model.pt`、`vae.pt`、`conditioner.pt`；拆分成功后完整 checkpoint 是可删除的重复运行资产。

Hunyuan 阶段只生成单一封闭无纹理形体。3060 的纹理方案是低分辨率语义色块、共享材质、2K 或更小图集、烘焙 AO/法线和按需局部重绘；不要把高分辨率多视图纹理扩散塞进形体生成阶段。
