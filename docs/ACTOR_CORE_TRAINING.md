# Actor Core 图像编辑训练

## 已确定的技术边界

`strip_to_actor_core` 是通用实验室任务：输入完整风格角色三视图，输出同布局、同姿态、同头身比的无身份无部件 Actor Core。它不绑定 `ba`，`ba` 只是一枚消费者标签。

生产链必须能在 RTX 3060 12GB 上离线推理。训练可以临时使用远程或更大显存，但训练产物必须回到 3060 上完成最终编辑；不能做到这一点的模型不得成为 Studio 默认后端。

当前后端分工：

| 层 | 默认选择 | 是否必需 | 职责 |
| --- | --- | --- | --- |
| 生产推理 | FLUX.2 Klein 4B distilled FP8 | 是 | 4 步本地编辑，加载任务 LoRA，目标硬件为 3060 12GB |
| LoRA 训练 | FLUX.2 Klein 4B Base | 训练时 | 学习 `strip_to_actor_core`；可远程训练 |
| 教师 Target | 人工绘制或可选远程教师 | 否 | 只提出候选 Target，不能自动批准 |
| Qwen-Image-Edit | 可选实验教师 | 否 | 不再是 Studio、数据或生产推理依赖 |
| 回退 | SDXL + LoRA/ControlNet/InstructPix2Pix | 条件回退 | Klein 训练产物无法在 3060 通过硬件 Gate 时启用 |

Black Forest Labs 将 4B Base 定位为有限硬件微调/LoRA版本，将 distilled 4B 定位为快速生产推理版本：<https://github.com/black-forest-labs/flux2/blob/main/README.md>。ModelScope 的 Base 仓库为 `black-forest-labs/FLUX.2-klein-base-4B`：<https://modelscope.cn/models/black-forest-labs/FLUX.2-klein-base-4B>。

## 数据合同与可迁移性

权威数据是模型无关的 `source + target + 可选 mask + caption + Gate + provenance`，schema 为 `schemas/strip_to_actor_core_pair.schema.json`。任何训练器导出都是可重建适配层，不得反过来污染原始 Pair。

- Source：已批准风格角色三视图。
- Target：同尺寸、同布局、同姿态的标准 Actor Core。
- Mask：可选人工校正范围，不是 Target 替代品。
- Provenance：记录 Target 是人工、远程教师还是本地模型生成；来源与人工批准相互独立。
- Candidate、approved、rejected 全部位于 `workspace/training/strip_to_actor_core/`，不上传 Git。
- 只有人工逐项确认全部 Gate 并显式批准的 Pair 才能导出训练集。

人工 Gate：

1. 光头、无耳、无任何五官；
2. 无头发、服装、鞋、手套和配件；
3. 单一连续、无性征、无表面标记的玩具式素体壳；
4. 躯干窄且轻微收束，不是梨形或鼓肚婴儿体；
5. front/right/back 描述同一体积；
6. 无缝线、孔洞、圆点、合成接缝或背景污染。

## 当前可确认预览

`teacher_actor_core_d70bce_20260826_v2` 已通过自动 Gate 与六项人工 Gate，并登记为首组 approved Pair。Target 由可选远程教师提出，随后只做 1px 面板居中规范化；来源模型没有参与批准决定。旧未居中版本和 Qwen 失败版本位于本地 rejected 目录，不参与导出。

Klein distilled 的同分辨率预筛选也已运行：4 steps、FP8、低显存模式、16GB 卡预留 5GB，10.32 秒完成；整卡基线 1,739MiB、峰值 13,427MiB、增量 11,688MiB。它证明推理接近 12GB 范围，但零样本仍保留头发和衣物，因此只算“显存预筛选通过、任务质量失败”。真实 RTX 3060 仍必须复测。

首轮最小过拟合已于 2026-08-26 完成：DiffSynth 两阶段缓存、Klein Base 4B、1 Pair、rank 16、100 steps、约 7 分 11 秒；训练期间 5070 Ti 峰值约 12,671MiB。LoRA 回载到 Klein distilled FP8 后，1536×768/4-step 约 10.3 秒。它已能去除头发、服装、鞋和配件并保持三视图，但仍生成耳朵；strength 1.3 可消除肤色面区并统一灰色外壳，仍未通过“无耳”Gate。Studio 的“Actor Core 本地推理预览”区展示这两张本地结果和已知问题，均不得入库。

## 注册与导出

候选注册示例：

```powershell
python .\tools\model_test\register_strip_to_actor_core_pair.py `
  --source <已批准风格角色图> `
  --target <人工或教师候选素体图> `
  --style-profile-id qstyle_anime_western_fantasy_no_face_v1 `
  --target-producer remote_teacher `
  --target-generator <教师标识> `
  --consumer-tag ba `
  --caption "convert the supplied character into the canonical blank Actor Core while preserving layout, pose and proportions"
```

人工确认前不要添加 `--approve`。确认完成后才可使用 `--approve --confirm-manual-gates` 重新登记批准版本。

FLUX.2 / ModelScope DiffSynth 导出：

```powershell
python .\tools\model_test\export_strip_to_actor_core_diffsynth_dataset.py --validate-only
python .\tools\model_test\export_strip_to_actor_core_diffsynth_dataset.py
```

导出器生成 DiffSynth 图像编辑合同：Target 为 `image`，Source 为 `edit_image`。ModelScope 官方 Klein Base LoRA 示例和训练参数位于：<https://github.com/modelscope/DiffSynth-Studio/blob/main/examples/flux2/model_training/lora/FLUX.2-klein-base-4B.sh>。

旧 Musubi/Qwen 导出器只保留为可选实验适配器：

```powershell
python .\tools\model_test\export_strip_to_actor_core_dataset.py --validate-only
```

## 训练与 3060 验收

没有至少一组人工批准 Pair 时，不下载 Base 训练权重、不安装训练环境、不启动 LoRA。模型优先从 ModelScope 下载，只取训练所需文件并支持断点续传；禁止把模型权重提交到 Git。

训练入口先运行 `tools/setup_flux2_actor_core_training.ps1` 搜索环境并只取 ModelScope 必需文件。首轮实测使用 rank 16、batch 1、最大 589,824 pixels、gradient checkpointing 和两阶段缓存；这个训练配置约需 12.7GB，不承诺在 3060 上训练。后续可降低 rank/分辨率做本机实验，但远程训练不是风险，生产推理依赖远程或大显存才是风险。

每枚 LoRA 必须通过真实 3060 Gate：

1. 峰值显存不超过约 11.5GB，不 OOM；
2. 本机离线完成参考图编辑；
3. 正常冷启动、保存和恢复；
4. 输出通过六项 Actor Core 人工 Gate；
5. Studio 不需要 Qwen 或远程教师即可调用；
6. 若失败，停止 Klein 生产采用并进入 SDXL 回退实验。
