# DressCode 参数化服装生成工作流

## 当前状态

这是 AssetsStudio 的新服装主路线，首个候选为 Q 版日漫 JRPG 风格的魔法师长袍与兜帽。DressCode 负责版型和材质候选生成，AssetsStudio 负责参数合同、Actor 适配、审查和发布。

现有 `milestones/tops/garmentcode_short_sleeve_v1/` 只作为旧服装基线和回归对照，不再决定新服装类别的生成方式。

## 系统边界

```text
服装简报/结构提示
  -> DressCode SewingGPT
  -> sewing pattern + panel/stitch manifest
  -> 受限参数变体生成器
  -> 布料/几何有效性检查
  -> 当前 Actor 适配与仿真
  -> Blender 权威 GLB、四向帧和 Walk GIF
  -> 人工审查
  -> recipe/候选注册表/随机池
```

DressCode 不是直接替代 Actor 绑定和游戏资产审查的黑盒。每一个生成结果都必须带有输入提示、seed、模型版本、版型清单、材质清单和输出哈希。

## 本地环境

- DressCode 源码：`third_party/DressCode/`
- Python 环境：`E:\Env\DressCode\`
- UV 缓存：`E:\Env\cache\uv-dresscode\`
- 已验证版本：Python 3.9.25、PyTorch 2.0.0+cu117、diffusers 0.24.0、transformers 4.35.2、accelerate 0.24.1、huggingface-hub 0.19.4、Gradio 4.8.0
- Windows Cairo 运行库：复用 `E:\Env\GarmentCode\pygarment\pattern\cairo_dlls\libcairo-2.dll`
- DressCode 权重：已下载 SewingGPT checkpoint 和 captions；源码使用的权重链接到 `E:\Env` 缓存
- Stable Diffusion：本机已有 SD 1.5，但 DressCode SewingGPT 需要 SD 2.1 的 1024 维文本特征。当前已下载 `Manojb/stable-diffusion-2-1-base` 镜像的 Diffusers 权重到 `E:\Env\DressCode\models--Manojb--stable-diffusion-2-1-base`，并通过 Junction 接入 DressCode 期望的模型目录；该镜像页面标注为从 StabilityAI 基础模型克隆，进入正式里程碑前仍需复核来源与授权。
- GarmentCode 仿真：源码位于 `third_party/GarmentCode/`；官方定制 Warp 位于 `E:\Env\NvidiaWarp-GarmentCode`，应将它放在 `PYTHONPATH` 的前面，不能用通用 Warp 替代，因为 GarmentCode 依赖额外的 `warp.collision` 和 cloth XPBD 接口。

如需重新拉取或更新 SD 2.1，在完成 Hugging Face 授权后，可在 PowerShell 中下载到环境盘（当前已完成）：

```powershell
& E:\Env\DressCode\Scripts\huggingface-cli.exe login
& E:\Env\DressCode\Scripts\huggingface-cli.exe download stabilityai/stable-diffusion-2-1-base `
  --local-dir E:\Env\DressCode\models--Manojb--stable-diffusion-2-1-base `
  --local-dir-use-symlinks True --resume-download
```

授权前不要把 `runwayml/stable-diffusion-v1-5` 目录改名冒充 SD 2.1；SewingGPT 的文本特征维度和训练分布不同。

运行 DressCode 时必须从其源码根目录执行，并设置：

```powershell
$env:PYTHONPATH = (Resolve-Path .\packages).Path
$env:PATH = "E:\Env\GarmentCode\pygarment\pattern\cairo_dlls;$env:PATH"
& E:\Env\DressCode\Scripts\python.exe .\nn\evaluation_scripts\predict_class.py -c .\models\infer.yaml
```

本地模型页面：[Manojb/stable-diffusion-2-1-base](https://huggingface.co/Manojb/stable-diffusion-2-1-base)。当前已用 `StableDiffusionPipeline.from_pretrained(..., local_files_only=True)` 校验，`text_hidden=1024`、`cross_attention_dim=1024`。

正式运行前还要把 `system.json` 中的 output 改为本地生成目录；仿真和渲染路径不能写入用户原始机器路径。

## 魔法师长袍首轮提示策略

预训练模型先从相近类别开始，而不是期待新类别零样本完成全部结构。首轮候选应分别记录：

- 长款 dress/robe 主体：强调 full-length、layered hem、center closure、fantasy mage silhouette；
- hooded jacket 结构：用于获得可缝合兜帽和肩部连接的起始版型；
- sleeve 变体：优先长袖或宽袖，再由参数约束袖口和袖长；
- 材质提示：wool/linen cloth、clean stylized trim、low-frequency pattern，避免照片级纹理。

如果多个组件通过 DressCode 的多服装提示生成，必须在输出清单中保留每个组件的来源和偏移；合并后的长袍不能抹掉原始 panel/stitch 信息。

## 参数化顺序

先固定版型拓扑和接缝关系，再逐步开放以下参数：

1. 长袍长度、下摆宽度和前开衩；
2. 袖长、袖宽和袖口形状；
3. 兜帽高度、深度、开口和后垂量；
4. 领口、前中线、腰部收束和滚边宽度；
5. 主色、辅色、滚边色和低频材质图案。

改变前四类参数必须重新生成/检查版型和 Actor 适配；只改变最后一类外观参数可以留在 Studio 交互预览层。

## DressCode -> GarmentCode -> Actor 实际命令

canonical pattern 的最小静态检查和 Actor 烟雾仿真由同一个适配器完成。PowerShell 中先让定制 Warp 排在源码路径前：

```powershell
$env:PYTHONPATH = ((Resolve-Path E:\Env\NvidiaWarp-GarmentCode).Path + ";" + (Resolve-Path third_party\GarmentCode).Path)
& E:\Env\GarmentCode\.venv\Scripts\python.exe tools\garmentcode\run_dresscode_pattern_bridge.py `
  --spec milestones\robes\mage_suit_v1\runs\seed_17081501\dresscode_outputs\260815-11-48-38\000\pred_0\parameterized\canonical_template_v1.json `
  --output milestones\robes\mage_suit_v1\garmentcode_bridge\canonical_template_v1_actor_smoke `
  --resolution 2.0 `
  --body-obj milestones\tops\garmentcode_short_sleeve_v1\inputs\collision_body.obj `
  --body-measurements milestones\tops\garmentcode_short_sleeve_v1\inputs\body_measurements.yaml `
  --body-segmentation milestones\tops\garmentcode_short_sleeve_v1\inputs\collision_segmentation.json `
  --simulate --max-steps 60
```

随后用 `tools\garmentcode\export_garmentcode_panel_membership.py` 生成精确 panel membership，再用 `tools\blender\transfer_garmentcode_sim_to_actor.py` 做分区蒙皮转移，最后用 `tools\blender\export_actor_transfer_glb.py` 导出 GLB。当前 smoke 结果必须先通过穿透、自交和四向人工审查，才可进入正式候选。

## 验收输出

每个候选 run 至少输出：

- recipe JSON；
- DressCode 提示和模型版本；
- 原始版型、参数化版型和 panel/stitch manifest；
- 材质/PBR 贴图或材质配方；
- Actor 适配 GLB/Blend；
- 正、右、背、左四向静帧和 Walk GIF；
- 几何有效性、穿体和审查报告。

候选状态依次为 `candidate -> reviewed -> promoted`；未通过的结果保留失败原因，但不能进入正式随机池。

## 旧路线迁移规则

- 不删除 F006 文件和已生成资产，它们用于视觉回归和迁移对照；
- 不再为 F006 增加新的短袖版型扫掠作为主开发任务；
- 新服装类别必须先创建 DressCode recipe 和候选目录，再接入 Studio；
- GarmentCode 可作为历史/对照依赖，但不能覆盖 DressCode 生成的版型来源。
