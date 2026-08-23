# 本地参考图三/四视图验证（2026-08-23）

## 决策

当前主机已经能够本地生成风格稳定、角色一致、方向可用的三视图，并能扩展为项目合同需要的四向图。通过路线是：

`已批准正面角色锚点 -> FLUX.2 Klein 4B ReferenceLatent 编辑 -> 视角分类 -> 分栏注册与重排 -> 自动/人工 QA -> Hunyuan3D-2MV`

这轮不再采用 `Animagine/Pony + ControlNet/IP-Adapter` 作为生产三视图生成器。它们可以快速画概念稿，但不能独立保证侧面/背面的几何与服装一致。`image_gen` 继续作为高质量身份/风格锚点的安全回退；本地 FLUX.2 路线在完成一次下游 Hunyuan 重建前，先作为 `candidate` 后端，而不是无条件替换默认后端。

## 本机与模型

- GPU：RTX 3060 12GB。
- ComfyUI：`0.28.0`，PyTorch `2.6.0+cu124`。
- 本地生成模型：`flux-2-klein-4b-fp8.safetensors`。
- 文本编码器：`qwen_3_4b.safetensors`。
- VAE：`flux2-vae.safetensors`。
- 安全启动：`--lowvram --disable-async-offload --disable-pinned-memory --cache-none --preview-method none --reserve-vram 1.5`。
- 生成参数：蒸馏模型、Euler、4 steps、CFG 1.0；三视图 `1536x768`，四视图 `2048x768`。

FLUX.2 Klein 官方同时支持文生图、单参考编辑和多参考编辑。当前脚本已按 ComfyUI 官方编辑工作流，把同一个 VAE latent 接入正、负两路 `ReferenceLatent`，不再把参考图只当作提示词附属信息。

## 输入与结果

参考输入为本轮从批准比例锚点派生的正面冒险者：

- `E:\env\outputs\local_threeview_20260823\actor_v2_animagine_canny_front.png`

三视图软 3D 结果：

- `assets/flux2_klein_reference_adventurer_turnaround_3d_20260823.png`

四向原始结果：

- `assets/flux2_klein_reference_adventurer_turnaround_4view_3d_20260823.png`

四向注册后结果与独立面板：

- `assets/flux2_klein_reference_adventurer_turnaround_4view_registered_20260823.png`
- `assets/flux2_klein_reference_adventurer_registered_20260823/front.png`
- `assets/flux2_klein_reference_adventurer_registered_20260823/right.png`
- `assets/flux2_klein_reference_adventurer_registered_20260823/back.png`
- `assets/flux2_klein_reference_adventurer_registered_20260823/left.png`

人工检查通过：

- 是同一个短棕发、蓝眼、红围巾、蓝短夹克、米色内搭、腰带/腰包、短裤和棕靴角色；
- 正面、左右严格侧面和背面均存在，没有动作姿势、额外人物、额外肢体或道具；
- 四向保持软质 3D 日漫手办风，比本轮 SD1.5 和 SDXL/MV-Adapter 输出更接近项目锚点；
- 头身比保持紧凑，没有回到普通 3H 以上成人动漫体型。

注册后自动报告：`assets/flux2_klein_reference_adventurer_turnaround_4view_registered_20260823.metrics.json`。

| 指标 | 结果 | Gate |
| --- | ---: | ---: |
| 四向人物高度 CV | `0.0048` | `<= 0.05` |
| 落脚线范围 | `0.0000` | `<= 0.03` |
| 分栏中心最大偏移 | `0.0088` | `<= 0.08` |
| 跨视图色彩直方图最低相关性 | `0.8292` | `>= 0.55` |

自动 Gate 全部通过。该报告只证明构图、尺度、落脚线和色彩连续性；视角语义、附件左右关系和真实 3D 几何仍必须人工检查，并由 Hunyuan/Blender 多视图 QA 继续验证。

## 必须保留的后处理

四向生成时，提示词要求 `front/right/back/left`，模型实际返回 `front/right/left/back`。因此不得按面板位置盲目命名文件。

正确步骤：

1. 生成联合画布；
2. 通过人工或视觉分类器识别每一栏的真实视角；
3. 使用 `tools/model_test/normalize_turnaround_panels.py` 分栏、居中、统一落脚线并重排；
4. 使用 `tools/model_test/analyze_turnaround_sheet.py` 执行自动 Gate；
5. 只有自动 Gate 与人工视角/服装检查都通过，才进入 RGBA 和 Hunyuan3D-2MV。

本轮实际重排命令的语义参数是：

`--detected-order front,right,left,back --canonical-order front,right,back,left`

## 被否决的本地分支

### SD1.5 + IP-Adapter + anime lineart ControlNet

显存占用低、速度快，正面身份和主色可保留，但侧面经常退化为 3/4 视角，背面出现额外弧形结构，人物比例也跨视图漂移。保留为概念迭代工具，不进入生产三视图。

### Animagine XL 3.1 + MV-Adapter I2MV SDXL

I2MV 权重已经从 ModelScope 下载到：

`E:\env\models\mv-adapter\mvadapter_i2mv_sdxl.safetensors`（`3,602,537,816` bytes）

官方版本组合与低显存组合均复现了 reference-attention cache 缺失；诊断报告显示 70 个 reference layer 未建立有效缓存，输出为块状/多角色伪影。它不是显存 OOM，但当前 Windows/PyTorch/源码组合不可作为本项目后端。

### 旧 T2MV “通过”记录

重新目视检查 `animagine_mvadapter_4view_768.png` 后，原报告所称“通过”撤销。画面存在明显块状伪影和角色不一致，不能因为脚本正常结束就判定生产通过。

## Krea 的位置

Krea 是云端产品/API，不是可下载到本机的模型运行时。网上的 Krea 三视图示例通常仍依赖其托管参考编辑模型与提示词工作流。它可以作为云端对照实验，但不能解决离线部署。本轮本地 FLUX.2 ReferenceLatent 已复现了其中最重要的“以批准角色图约束多视图”思路。

## 下一 Gate

把注册后的 `front/right/back/left` 分别生成 RGB/RGBA，并用当前 RTX 3060 安全参数跑一次 Hunyuan3D-2MV。只有重建网格的正、侧、背、左轮廓及发型/耳朵/服装附件通过 Blender QA，才把本地 FLUX.2 后端从 `candidate` 升为默认；否则保留 `image_gen -> 本地 ReferenceLatent 补视图` 的混合流程。

## Studio 集成

第一阶段的纯提示词三视图已接入 Studio 顶部“本地三视图”页面。页面、受限本地桥接、一键启动和环境重建说明见：

- `docs/features/F009-local-prompt-turnaround-studio.md`
- `docs/workflows/studio_local_turnaround_setup.md`
- `tools/model_test/studio_local_generation_api.py`
- `tools/start_studio_local_generation.ps1`

当前 Studio 入口故意只交付原始候选并标记 `visual_review_required`。本文件验证通过的 ReferenceLatent、视角分类、自动重排和 Hunyuan 排队将在 F009 第二阶段接入，不能在第一阶段页面中伪装为已完成。

## 官方资料

- [FLUX.2 Klein 4B 官方模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [ComfyUI FLUX.2 Klein 官方教程](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [ComfyUI ReferenceLatent 文档](https://docs.comfy.org/built-in-nodes/ReferenceLatent)
- [MV-Adapter 官方实现](https://github.com/huanngzh/MV-Adapter)
- [ModelScope MV-Adapter 镜像](https://modelscope.cn/models/AI-ModelScope/mv-adapter)
