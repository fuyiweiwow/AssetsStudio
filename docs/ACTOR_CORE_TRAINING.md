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

`teacher_actor_core_d70bce_20260826_v2` 与 `teacher_actor_core_74e7acc_20260826_v2` 均已通过自动 Gate 与六项人工 Gate。第二枚 Target 使用已批准长发风格种子约束布局和比例、首枚已批准 Target 约束无耳素体几何，由可选图像教师提出；来源模型没有参与批准决定。两个较弱候选已拒绝，旧未居中版本和 Qwen 失败版本均位于本地 rejected 目录，不参与导出。

Klein distilled 的同分辨率预筛选也已运行：4 steps、FP8、低显存模式、16GB 卡预留 5GB，10.32 秒完成；整卡基线 1,739MiB、峰值 13,427MiB、增量 11,688MiB。它证明推理接近 12GB 范围，但零样本仍保留头发和衣物，因此只算“显存预筛选通过、任务质量失败”。真实 RTX 3060 仍必须复测。

首轮最小过拟合已于 2026-08-26 完成：DiffSynth 两阶段缓存、Klein Base 4B、1 Pair、rank 16、100 steps、约 7 分 11 秒；它证明了数据合同可训练，但 distilled strength 1.3 仍生成耳朵，现已被 v2 取代并移出 Studio 有效预览。

第二轮于 2026-08-27 从头训练：2 approved Pairs、rank 16、120 steps、最大 589,824 pixels、约 8 分 36 秒；5070 Ti 训练峰值约 12.66GB。产物 `teacher_v2_2pair_rank16_120step` 的 epoch-4 checkpoint 已回载到 Klein distilled FP8，SHA256 为 `B8D82DF6848BC23237FFB0BCA14C261535AB85F5AE0386EC1B062F2AC9C4AB4C`。权重仍只保存在本地模型目录，不提交 Git。

v2 的诊断结论是“训练任务已学会，生产强度与泛化仍待验收”：Base BF16 计算/CPU offload 在训练来源上可稳定输出无耳、统一灰色 Actor Core，768×384/20-step 约 45.9 秒，Torch 峰值分配约 5.1GB；因此不是 LoRA 键未加载。distilled 4-step 在两个训练来源上需 strength 2.0 才去除可见耳朵，在未参与训练的 BA 三视图保留集上需 strength 3.0。保留集结果已无可见耳朵，但右侧视图脚部存在双轮廓伪影，所以仅为人工评审候选，不得入库，也不得成为 Studio 默认后端。

Studio 的“Actor Core 本地推理预览”区只展示三张当前有效候选：两个训练来源的 strength 2.0 结果和一个 BA 保留集的 strength 3.0 结果。失败的 v1、低强度探针与 Base 诊断图全部移入本地 rejected 目录，不出现在有效预览中。

第三组 `teacher_actor_core_bob_cowl_20260827_v1` 已于 2026-08-27 批准：Source 使用同一 StyleProfile 但采用短发、兜帽、披肩、腰带、手套与靴子的不同部件轮廓；Target 继续使用双参考教师方法。Target 初稿因第三面板偏左未通过中心 Gate，没有绕过检查；随后用 `normalize_turnaround_panel_centers.py` 按 Source 前景中心仅做 0/22/42px 整数水平平移，不缩放、不变形。规范化后 `height_cv=0.0013`、`ground_range=0.0023`、`center_max_offset=0.0515`、最低色彩相关性 `0.9922`，并通过六项人工 Gate。该 Source 是本地训练候选，不等于第三枚已发布风格种子。

三 Pair v3 训练曾在当前 Windows GPU 会话中尝试：589,824-pixel/180-step 正式运行与 393,216-pixel/3-step 烟雾运行都出现 SM 100%、约 62W、数分钟无 checkpoint 的异常慢路径；停止两套 Comfy 后仍可复现，排除数据数量、缓存 token 形状和 Comfy 竞争是唯一原因。两次运行均已人工终止，没有产生 v3 权重，不能作为质量结论。下次必须在 GPU/主机重启后的干净会话先完成 3-step 烟雾 Gate，再启动正式训练。

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

当教师 Target 仅有面板水平位置偏差时，可按 Source 做确定性对齐；不得用它修补几何或绕过其他 Gate：

```powershell
python .\tools\model_test\normalize_turnaround_panel_centers.py <target.png> `
  --reference <source.png> --output <target.normalized.png> `
  --report <target.normalization.json>
```

导出器生成 DiffSynth 图像编辑合同：Target 为 `image`，Source 为 `edit_image`。ModelScope 官方 Klein Base LoRA 示例和训练参数位于：<https://github.com/modelscope/DiffSynth-Studio/blob/main/examples/flux2/model_training/lora/FLUX.2-klein-base-4B.sh>。

旧 Musubi/Qwen 导出器只保留为可选实验适配器：

```powershell
python .\tools\model_test\export_strip_to_actor_core_dataset.py --validate-only
```

## 训练与 3060 验收

没有至少一组人工批准 Pair 时，不下载 Base 训练权重、不安装训练环境、不启动 LoRA。模型优先从 ModelScope 下载，只取训练所需文件并支持断点续传；禁止把模型权重提交到 Git。

训练入口先运行 `tools/setup_flux2_actor_core_training.ps1` 搜索环境并只取 ModelScope 必需文件。首轮实测使用 rank 16、batch 1、最大 589,824 pixels、gradient checkpointing 和两阶段缓存；这个训练配置约需 12.7GB，不承诺在 3060 上训练。后续可降低 rank/分辨率做本机实验，但远程训练不是风险，生产推理依赖远程或大显存才是风险。正式训练前必须先做 1 epoch/每 Pair 1 次的烟雾训练并确认 checkpoint 落盘；若 GPU 长时间低功耗满占用且没有 checkpoint，停止运行、保留缓存并在干净 GPU 会话复测。

每枚 LoRA 必须通过真实 3060 Gate：

1. 峰值显存不超过约 11.5GB，不 OOM；
2. 本机离线完成参考图编辑；
3. 正常冷启动、保存和恢复；
4. 输出通过六项 Actor Core 人工 Gate；
5. Studio 不需要 Qwen 或远程教师即可调用；
6. 若失败，停止 Klein 生产采用并进入 SDXL 回退实验。
