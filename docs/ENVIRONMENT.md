# 环境发现与模型资产

## 发现规则

所有入口按顺序搜索：显式命令行参数、专用环境变量、AssetsStudio 相邻目录、用户目录常见安装位置与模型缓存。找不到时必须列出已检查位置并停止；文档和代码不得依赖某台机器的盘符绝对路径。

常用环境变量：

- `ASSETSSTUDIO_COMFY_ROOT`：可选 ComfyUI 根目录；
- `ASSETSSTUDIO_PYTHON`：可选 Python 可执行文件或命令；
- `ASSETSSTUDIO_DIFFSYNTH_ROOT`：可选 DiffSynth-Studio 源码根目录；
- `ASSETSSTUDIO_FLUX2_BASE_ROOT`：可选 ModelScope FLUX.2 Klein Base 模型根目录；
- `ASSETSSTUDIO_ACTOR_CORE_LORA`：可选 Actor Core LoRA 文件；相对路径按 ComfyUI `models/loras` 解析，绝对路径也必须位于该目录内。未设置时搜索 `models/loras/assetsstudio/strip_to_actor_core*.safetensors` 并选取最近更新的本地权重；
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

训练工具使用 ModelScope 团队维护的 DiffSynth-Studio。模型权重只从 ModelScope 下载；源码在 GitHub 不稳定时可使用 Gitee 镜像。它支持 FLUX.2 图像编辑、LoRA、FP8、gradient checkpointing、CPU offload 和两阶段缓存。训练环境不是 Studio 启动依赖；只有满足以下条件才安装：

1. 至少一组 Pair 已人工批准；
2. 明确选择本机小规模验证或远程训练机；
3. 磁盘空间与系统内存检查通过；
4. 下载计划只包含所需文件并使用 ModelScope 断点续传。

入口会搜索 ComfyUI、Python 与已有 DiffSynth 源码，并复用 ComfyUI 中的文本编码器/VAE。不要把当前机器盘符写进命令：

```powershell
.\tools\setup_flux2_actor_core_training.ps1
```

已存在缓存后的训练也不得手写模型绝对路径或嵌套 JSON：

```powershell
python .\tools\model_test\train_flux2_actor_core_lora.py `
  --cache-dir <缓存目录> --output-dir <输出目录> `
  --dataset-repeat 1 --epochs 1 --max-pixels 393216
```

该入口搜索 `ASSETSSTUDIO_COMFY_ROOT`、`ASSETSSTUDIO_DIFFSYNTH_ROOT`、`ASSETSSTUDIO_FLUX2_BASE_ROOT` 及仓库相邻/工作区位置，并验证实际 marker 文件后再启动训练。系统 Python 缺少 PyTorch 时会自动切换到 ComfyUI Python；子进程固定 `DIFFSYNTH_SKIP_DOWNLOAD=True`。它还会读取每个 `.pth`，若数据处理阶段没有把 `use_gradient_checkpointing=True` 写入 cache，则在加载 4B 模型前停止并要求重建缓存。

脚本只下载 `transformer/*`、`tokenizer/*` 和 `model_index.json`。2026-08-26 的已验证环境为 DiffSynth 2.1.2（源码提交 `6343deda`）、Python 3.10.20、PyTorch 2.11.0+cu128；这些是运行记录，不是硬编码路径或强制精确版本。2026-08-27 的两 Pair/rank-16/120-step 实测约 8 分 36 秒、训练峰值约 12.66GB，仍不构成 3060 训练承诺。

模型已齐全的训练会话由入口设置 `DIFFSYNTH_SKIP_DOWNLOAD=True`，确保运行期只加载已发现的本地权重。数据处理与训练两个阶段都必须启用 gradient checkpointing；该标志会固化进 cache，不能只在训练阶段补传。正式训练前先停止或卸载其他 GPU 模型并运行每 Pair 一次的 1-epoch 烟雾训练；只有 checkpoint 正常落盘后才扩大 steps。若出现 GPU 长时间低功耗满占用且无 checkpoint，先比较 cache 的 `use_gradient_checkpointing`，再判断 GPU/驱动会话，不通过降低验收标准掩盖。

Base 常规推理约需 13GB 显存，常规 LoRA 示例按约 24GB 设计，因此 RTX 3060 不承担“必须舒适训练”的承诺。训练可远程完成；LoRA + distilled 推理必须回到真实 3060 验收。

## Qwen-Image-Edit 的状态

Qwen-Image-Edit 已从必需环境和默认验证中移除。历史 Q3 零样本实验用于记录失败模式；它可作为可选远程/本地教师，但 Studio 启动、Pair schema、FLUX 导出和生产推理均不得依赖它。旧环境脚本与推理脚本仅为可恢复实验适配器，后续项目瘦身时可单独归档或删除。

## RTX 3060 12GB 硬门槛

- 生产编辑必须离线运行；目标峰值显存约 11.5GB 以下；
- 当前 5070 Ti 限额测试只能预筛选，不能替代真实 3060；v2 distilled 结果还需要 strength 2.0–3.0，强度变化本身不会显著增加权重显存，但输出质量必须逐张过 Gate；
- 零样本 Klein distilled 1536×768/4-step 预筛选增量峰值为 11,688MiB；加载 rank-16 LoRA 的 5070 Ti 运行会根据 16GB 总量多驻留权重，记录到 13,819MiB 增量，不能据此推断 3060 必然 OOM；
- 若训练后 LoRA 不能在 3060 稳定加载和编辑，则 Klein 不进入生产，改做 SDXL 回退验证；
- 系统内存与页面文件只用于可接受的权重换入，不能把极慢 CPU 换页包装成“可用”。

## Hunyuan3D 与纹理

优先从 ModelScope 获取官方 `Tencent-Hunyuan/Hunyuan3D-2mv`。只保留形状模型 `config.yaml` 与拆分后的 `model.pt`、`vae.pt`、`conditioner.pt`；拆分成功后完整 checkpoint 是可删除的重复运行资产。

Hunyuan 阶段只生成单一封闭无纹理形体。3060 的纹理方案是低分辨率语义色块、共享材质、2K 或更小图集、烘焙 AO/法线和按需局部重绘；不要把高分辨率多视图纹理扩散塞进形体生成阶段。
