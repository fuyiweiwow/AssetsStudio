# FLUX.2 Klein 4B 本机三视图验证（2026-08-21）

## 结论

RTX 3060 12GB 可以在 ComfyUI 低显存模式下稳定运行 FLUX.2 Klein 4B FP8。一次联合生成的正面、右侧、背面角色图，已经能保持主要轮廓、配色、发型和服装结构，可用于角色概念与后续 Actor/Slot 建模参考。

它仍不是几何标准件生成器：胸带、隐藏配件和斗篷连接处存在轻微跨视图漂移，最终尺寸、正交投影、透明分层与附件左右关系仍需 Blender/Actor/Slot Compiler 校验。

## 本机配置与安全参数

- GPU：NVIDIA GeForce RTX 3060 12GB
- RAM：约 24GB
- ComfyUI：0.28.0
- PyTorch：2.6.0+cu124
- 启动参数：`--lowvram --disable-async-offload --disable-pinned-memory --cache-none --preview-method none --reserve-vram 1.5`
- 端口：`127.0.0.1:8190`

这些参数让 8GB 文本编码器在 CPU 上运行，FP8 扩散模型在 GPU 上运行，避免大规模 pinned memory 与异步 offload 带来的额外内存压力。

## 模型文件

模型均从 ModelScope 的官方镜像下载到 `E:\Env\ComfyUI\models`，并按上游文件大小及 safetensors 头完成校验：

- `text_encoders/qwen_3_4b.safetensors`：8,044,982,048 bytes
- `diffusion_models/flux-2-klein-4b-fp8.safetensors`：4,070,624,520 bytes
- `vae/flux2-vae.safetensors`：336,213,556 bytes

## 测试结果

### 冒烟测试

- 画布：768×768
- 步数：4
- CFG：1.0
- 总耗时：约 62 秒
- 扩散采样：约 5.5 秒
- 结果：单角色 Q 版日漫西幻方向正确，无 OOM、无系统异常

### 三视图测试

- 画布：1536×768
- 步数：4
- CFG：1.0
- Seed：20260821
- 总耗时：约 66–71 秒
- 输出：`assets/flux2_klein_western_fantasy_chibi_female_adventurer_3view.png`

验证通过项：

- 三个独立全身人物，依次为正面、右侧面、背面
- 人物大小与站姿接近一致
- 短发、绿色斗篷、米色上衣、蓝绿色裙装、深色打底裤、棕色长靴保持一致
- 背景、线条和整体日漫游戏概念图画风一致

已知偏差：

- Q 版程度约为 4 头身，仍可进一步强化到 2.5–3 头身
- 正面的肩带被模型画成交叉结构，侧面只显示单带
- 小型剑鞘、腰包等遮挡区域仍有轻微位置漂移
- 不能仅凭图片证明严格正交尺寸一致

## 可复现入口

脚本：`tools/model_test/run_comfy_flux2_klein.py`

脚本通过 ComfyUI HTTP API 调用核心节点，不依赖第三方 custom nodes。默认使用蒸馏 FP8 模型、4 步 Euler、Flux2Scheduler，并支持调整画布、提示词、seed、CFG 和输出前缀。

## 后续风格可替换设计

三视图结构与画风应拆成两层：

1. 结构层：Actor 比例、正交相机、姿势、深度/轮廓模板、Slot 边界。
2. 风格层：基础模型、LoRA 列表与权重、风格参考图、提示词预设、色板和后处理参数。

未来可以将风格层封装为 `StyleProfile`。切换 Q 版日漫、水彩、欧美卡通或像素风时，只替换 StyleProfile；结构层和 QA 合同保持不变。风格 LoRA 仍可能改变人体比例，因此每次风格切换都必须重新执行多视图轮廓与附件位置检查。

## 清理说明

已确认以下两套全量 Qwen 权重不适合当前主机，合计约 107.5GB：

- `E:\Env\models\Qwen-Image`
- `E:\Env\models\Qwen-Image-Edit-2511`

自动永久删除被当前执行环境的安全策略拦截，目录仍然存在，尚未释放空间。
