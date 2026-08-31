# AssetsStudio

AssetsStudio 是一个通用、本地优先的美术素材供给实验室。BombAdventure（`ba`）是当前消费者标签，不是 Studio 的项目边界。

当前唯一生产链：

`StyleProfile → 风格种子 → 无部件 Actor Core → Hunyuan3D 形体 → 手工 AccuRIG → 动作库适配/变形 QA → Slot 部件 → Recipe/组合预览`

旧 Actor、完整角色直出、GarmentCode 扫参、历史 Gallery 与失败候选已从当前工作树移除；精确历史仍可从 Git 恢复。

## 启动

双击 `start-local-generation-studio.bat`，或：

```powershell
.\start-local-generation-studio.bat --no-open
```

入口会搜索 ComfyUI 与 Python，并检查 FLUX.2 Klein 所需模型。Studio 地址是 `http://127.0.0.1:4173/`。生产推理硬目标是 RTX 3060 12GB：默认使用 Klein 4B distilled FP8；Klein Base 仅用于 LoRA 训练，Qwen/远程教师均为可选数据来源而非运行依赖。

两枚当前已批准风格种子随 Git 位于 `references/style_profiles/published_seeds/`。首次在新机器启动 API 时会自动引入本地种子库；模型权重仍需按环境文档从 ModelScope 获取。

当前本机 Studio 只显示一枚实验 Actor Core `actor_core_v6_seed20260867_hy3d_v1`。它已通过单连通、封闭、四向轮廓和绑定减面 Gate；头顶轻微起伏作为已知问题保留，因此只用于继续验证绑定与模块配件链，尚不是最终生产 canonical。它的专属 AccuRIG FBX 已生成并等待人工标定；旧 Actor 仅保留为隐藏的 AccuRIG/动作技术基线。

可选 Actor Core LoRA 训练环境由 `tools/setup_flux2_actor_core_training.ps1` 搜索并补齐；它复用已有 ComfyUI 文本编码器/VAE，只从 ModelScope 下载缺失的 Base 诊断 Transformer 与 tokenizer。生产 LoRA 针对 distilled 权重族原生训练：优先用 `convert_comfy_flux2_fp8_to_diffsynth_bf16.py` 复用已发现的本地 scaled-FP8 权重；本地来源不满足完整性校验时才从 ModelScope 补齐。训练权重、Pair、缓存和预览继续位于忽略的 `workspace/`。

## 当前文档

- [当前工作流](docs/CURRENT_WORKFLOW.md)
- [环境发现与模型](docs/ENVIRONMENT.md)
- [Actor Core 图像编辑训练](docs/ACTOR_CORE_TRAINING.md)
- [AccuRIG 手工交接](docs/ACCURIG_HANDOFF.md)
- [骨骼动画资产与自动适配](docs/ANIMATION_RETARGET.md)
- [本地资产生命周期](docs/ASSET_LIFECYCLE.md)

## 验证

```powershell
python .\tools\build_studio_style_slot_registry.py
python .\tools\validate_style_slot_profiles.py
python .\tools\validate_accessory_generation_contract.py
python .\tools\validate_studio_local_generation.py --check-models --check-local-assets
cd .\studio
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

人工 Rig 暂不可用时，可在未绑定 T-Pose 上继续独立配件静态适配：

```powershell
.\tools\run_tpose_accessory_experiment.ps1 -Seed 20260832
```

该入口只产生静态候选；骨骼、蒙皮和动画 Gate 不会被自动标记为通过。详见 [未绑定 T-Pose 配件工作流](docs/TPOSE_ACCESSORY_WORKFLOW.md)。

除 `references/style_profiles/published_seeds/` 中已批准的可移植种子包外，`workspace/`、模型权重和第三方运行时均保持本地，不上传 Git。
