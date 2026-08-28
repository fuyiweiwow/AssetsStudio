# RTX 3060 Actor Core 离线产线

## 责任边界

RTX 5070 Ti 只负责训练、对照实验和筛选教师级素材。它的显存、耗时和成功率不能成为 Studio 生产验收证据。RTX 3060 12GB 必须能够独立完成环境发现、缺失权重获取、LoRA 安装、1536×768 四步编辑、自动 Gate、候选销毁或人工批准、本地保存恢复和资产库写入。

训练数据、Base/BF16 训练权重和 DiffSynth 环境不属于 3060 生产依赖。生产端只需要 ComfyUI、FLUX.2 Klein 4B distilled FP8、FLUX.2 的 Qwen3-4B 文本编码器、VAE、当前 Actor Core LoRA、Studio 和本地工作区。

## 环境建立

先拉取 `main`，将 Actor Core 3060 bundle 解压到任意本地目录，然后执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup_actor_core_production.ps1 -BundleRoot <bundle目录>
```

脚本先搜索参数、环境变量、仓库相邻目录和用户目录中的 ComfyUI。已经存在且大小有效的模型不会重复下载；缺失文件只从 ModelScope 断点下载：

- `black-forest-labs/FLUX.2-klein-4b-fp8` 的 distilled FP8 Transformer；
- `Comfy-Org/flux2-klein-4B` 的 `qwen_3_4b.safetensors` 文本编码器和 `flux2-vae.safetensors`。

`qwen_3_4b.safetensors` 是 FLUX.2 的文本编码器，不是 Qwen-Image-Edit，也不引入另一条生产生图链。训练得到的 48MB Actor Core LoRA 由 bundle 提供并校验 SHA256，不从互联网下载。

## 冷启动验收

完整硬件 Gate 前先停止占用 8190 端口的 ComfyUI，再执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_actor_core_3060_validation.ps1 -BundleRoot <bundle目录> -ColdStart
```

该入口会静默启动低显存 ComfyUI，确认显卡名称为 RTX 3060 且可用显存不少于 11,000MiB，使用 bundle 中固定的未训练 Source、v6/e75 LoRA、strength 3.0、seed `20260865` 完成 1536×768/4-step 编辑。随后运行三视图与 Actor Core 形状 Gate，保存图片和 JSON，重新读取图片并核对 SHA256。只有冷启动、推理、自动 Gate 和保存恢复同时通过，才写入本地 `rtx3060_qualification.json`；Studio 健康状态随后显示 3060 已通过。

若 ComfyUI 已在运行而未指定 `-ColdStart`，只能形成 warm-runtime 记录，不能解除冷启动待验状态。5070 Ti 必须显式使用开发绕过参数，且永远只产生 prescreen 记录。

## 生产生命周期

1. 用户从已批准 StyleSeed 发起 Actor Core 编辑。
2. Studio 使用固定 distilled FP8、当前 LoRA 和四步工作流生成一个本地候选。
3. 自动 Gate 失败时，候选不得进入 Gallery、随机池或资产库；直接销毁并更换 seed。
4. 自动 Gate 通过后仍需逐项人工检查光头、无耳、无脸、无服装鞋袜、连续素体、严格 front/right/back 和统一材质。
5. 人工批准后复制到不上传的本地资产库；未批准候选立即销毁。
6. 只有已批准 Actor Core 才能进入 Hunyuan3D、AccuRig、动画适配和部件生成。

当前 v6 在固定干净 held-out Source 的五 seed 测试中为 `1/5` 自动通过，因此“生成一次必成”尚未成立。当前完整产线依赖自动 Gate 与换 seed 保证失败内容不流入下游；5070 Ti 后续继续提高教师 LoRA 的跨 seed/跨 Source 成功率。v8 增量实验虽在单图上改善脚部，但十 seed 仅 `2/10`，且压力 Source 失败，已拒绝替换 v6。

## 回退条件

出现以下任一情况，Klein 不得成为 3060 默认生产后端，应执行既定 SDXL 回退实验：

- 真实 3060 12GB 无法冷启动或完成固定 1536×768/4-step Gate；
- 推理依赖不可接受的 CPU 换页，无法形成可用的本地交互周期；
- 保存恢复后的文件或 LoRA 哈希不一致；
- 继续补充教师 Pair 后，跨 Source/跨 seed 通过率仍无法支持候选重试工作流。

bundle 不包含上游大模型，避免复制可由 ModelScope 恢复的 12GB 以上公共权重。它只保存无法从公共仓库恢复的 LoRA、固定 Source、预期样例、报告和带哈希 manifest。
