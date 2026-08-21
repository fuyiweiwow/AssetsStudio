# SDXL 本地下位替代验证（2026-08-21）

## 结论

在 RTX 3060 12GB、Windows 环境下，`SDXL base 1.0 FP16 + CPU offload` 可以稳定加载并完成文生图、图生图和 Canny ControlNet 图生图测试；本轮没有复现蓝屏。它可以作为安全的本地概念图和标准件草图后端，但暂时不能替换 GPT ImageGen 的标准件生产职责。

## 本地模型

- 基础模型：`AI-ModelScope/stable-diffusion-xl-base-1.0` 的 FP16 Diffusers 文件。
- 控制模型：`diffusers/controlnet-canny-sdxl-1.0-small`，通过官方 Hugging Face 权重下载。
- 本地路径：`E:\env\models\sdxl-base-1.0-fp16`、`E:\env\models\controlnet-canny-sdxl-1.0-small`。
- 运行方式：`StableDiffusionXLPipeline` / `StableDiffusionXLImg2ImgPipeline` / `StableDiffusionXLControlNetImg2ImgPipeline`，CPU offload，512×512，20 步。

## 已完成测试

| 测试 | 结果 | 判断 |
| --- | --- | --- |
| 512×512 文生图，20 步 | 输出可用的青绿色服装概念图，但会自行补出袖子、手臂等身体细节 | 适合草图，不适合直接作为 Slot 几何真相 |
| 图生图，strength 0.45 | 角色、白底和视角保持好，服装改动很小 | 适合保守修图 |
| 图生图，strength 0.75 | 服装变化明显，但角色/造型漂移增大 | 可批量产出候选，必须人工筛选 |
| Canny ControlNet，control 0.70 / strength 0.65 | 轮廓和视角稳定，但基本保留原服装 | 轮廓保护有效，换装力度不足 |
| Canny ControlNet，control 0.35 / strength 0.75 | 保留人物轮廓，同时得到深青绿色服装变化 | 是当前最平衡的本地参数，但仍未形成严格多视图一致性 |

测试输出位于 `E:\env\outputs\qwen_standard_slot_test_20260820`，包括 `sdxl_text_torso_front_20steps.png`、`sdxl_img2img_front_strength075.png` 和 `sdxl_canny_img2img_front_balanced.png`。

## 与当前标准件流程的关系

当前流程合同是：

`Actor 校准图 -> Slot 多视图设计 -> RGB/RGBA 分离 -> Hunyuan3D-2MV 来源网格 -> ActorProfile/Slot Compiler -> front/right/back/left 与动作 QA`

SDXL 本身只负责其中的“Slot 多视图设计”候选图，不能保证一次生成严格的正交 front/right/back/left，也不负责 RGBA 分离、网格、UV、骨骼或动作验收。三/四视图若用 SDXL，应对每个视角独立生成，再使用同一 seed、同一设计描述、输入视图轮廓约束和人工/程序化 QA；不能把四张图直接视为一致资产。

## 当前决策

1. 本地默认实验后端采用 `SDXL + Canny ControlNet`，用于低风险草图、轮廓保护和失败候选批量生成。
2. GPT ImageGen 继续作为标准件生产参考图默认后端，直到本地方案通过四视图对应、RGBA 前景分离、Hunyuan 来源网格和动作 QA。
3. Qwen-Image / Edit-2511 原始 57GB safetensors 在本机 Windows 上暂停运行；已发生两次 `0x1A` 蓝屏，不能为了质量继续重跑。

## 官方资料

- [Stable Diffusion XL base 1.0 模型卡](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [ModelScope SDXL 镜像](https://modelscope.cn/models/AI-ModelScope/stable-diffusion-xl-base-1.0)
- [官方 SDXL Canny ControlNet 小模型](https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0-small)
- [Diffusers ControlNet 文档](https://huggingface.co/docs/diffusers/using-diffusers/controlnet)
- [当前项目标准件流程与模型筛选](./local_model_environment_2026-08-20.md)
