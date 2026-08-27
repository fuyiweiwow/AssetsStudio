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

旧批准数据已用 `assetsstudio_actor_core_shape_qa_v1` 重新审计。该 Gate 使用逐行自适应 LAB 分割，直接测量前视下躯干与侧视脚部：

- `front_lower_torso_width_ratio <= 0.54`；
- `side_foot_detection_ratio >= 0.80`；
- `side_foot_projection_ratio <= 1.20`。

三个旧 approved Target 全部失败并移入本地 rejected：`teacher_actor_core_d70bce_20260826_v2` 与 `teacher_actor_core_74e7acc_20260826_v2` 躯干过宽，旧 `bob_cowl` Target 的脚部投影过大。人工布尔值不得覆盖这些失败。Studio 的整幅 reference MAE 只保留为诊断，不再进入批准 Gate，因为 Source 必然包含需要移除的头发、衣服和配件。

当前只有两 Pair 通过新自动 Gate 与人工 Gate：

- `teacher_actor_core_male_80b51207_20260827_v1`：下躯干 `0.5372`，侧脚投影 `1.0964`；
- `teacher_actor_core_bob_cowl_20260827_v2`：下躯干 `0.5251`，侧脚投影 `1.1250`。

两张 Target 均由外部图像教师提出候选；教师不是生产依赖，也没有批准权限。候选随后只做逐面板等比缩放与整数平移，使人物高度、中心和地面线与 Source 对齐；工具禁止非均匀缩放和形体重绘。Pair 保留通用 StyleProfile，并仅以 `consumer_tags=["ba"]` 记录近期消费者。

两 Pair v4 使用 `prepare_flux2_actor_core_cache.py` 生成 589,824-pixel、内嵌 `use_gradient_checkpointing=True` 的缓存。2-step 烟雾训练约 8 秒通过后，正式 rank-16、12 repeats、5 epochs 共 120 steps，2026-08-27 用时约 8 分 35 秒。五个 checkpoint 均落盘；epoch-4 SHA256 为 `15BB0CBC7BE0A0163D080E936FD8789CA96FFC81339A017F9C531D6EE715AE6E`，复制到 ComfyUI 后哈希一致。模型权重和 Pair 仍只存本地，不提交 Git。

v4 的 distilled 4-step 阶梯没有任何可批准结果：

- 旧长发保留集 strength 2.0：躯干通过 `0.5379`，脚部失败 `1.2169`；
- strength 2.5：脚部通过 `1.1611`，躯干失败 `0.5621`；
- strength 3.0：脚部通过 `1.1158`，躯干有效行不足；
- 男性训练来源 strength 2.0/2.5：躯干与脚部均失败；strength 3.0 脚部通过但躯干有效行不足。

六个任务均已从 Studio 活跃候选移入本地 rejected，不能进入 Gallery、随机池、资产库或 3D。只读评审目录保留最接近通过的 distilled 2.0 图，不改变该失败结论。

为区分 LoRA 欠拟合与 Base→distilled 迁移，使用 `run_flux2_base_actor_core_diagnostic.py` 在男性训练来源执行 Base 原生对照。脚本只搜索本地 ModelScope/ComfyUI 权重，设置 `DIFFSYNTH_SKIP_DOWNLOAD=True`，使用 DiffSynth 官方磁盘映射 + FP8 暂存、BF16 计算；768×384、20 steps、seed 20260831 用时 44.86 秒。结果脚部通过 `0.8816`，但下躯干 `0.5577` 失败，且肉眼仍有手指、胸腹和裆部解剖结构。

因此 v4 的主要结论不是“只需提高 distilled strength”，也不是“只有跨模型迁移失败”，而是两 Pair/120 steps 尚未把连续无解剖细节 Actor Core 学稳。下一轮应先扩充 4–6 个形体一致、Source 遮挡多样的批准 Pair，并要求 Base 原生固定集通过后再验证 distilled。Base 对照仅为训练诊断，不得写入 RTX 3060 生产依赖。

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

批准前与历史审计：

```powershell
python .\tools\model_test\analyze_actor_core_shape.py <target.png>
python .\tools\model_test\audit_strip_to_actor_core_pairs.py
# 人工确认审计报告后，才可添加 --apply 将失败 Pair 移入 rejected
python .\tools\model_test\audit_strip_to_actor_core_pairs.py --apply
```

缓存入口会搜索已有 DiffSynth、ModelScope Base、ComfyUI 文本编码器/VAE，不要求某台机器的绝对路径：

```powershell
python .\tools\model_test\prepare_flux2_actor_core_cache.py `
  --dataset-dir <DiffSynth 导出目录> --cache-dir <缓存目录> `
  --max-pixels 589824
```

缓存完成后的训练统一使用发现式入口，不复制某台机器的绝对路径：

```powershell
python .\tools\model_test\train_flux2_actor_core_lora.py `
  --cache-dir <DiffSynth 两阶段缓存目录> `
  --output-dir <本地 LoRA 输出目录> `
  --dataset-repeat 1 --epochs 1 --max-pixels 393216
```

入口依次搜索专用环境变量、仓库工作区和相邻 ComfyUI；它把 `model_paths` 作为真实 JSON 参数数组传给 DiffSynth。若系统 Python 没有 PyTorch，会自动切换到发现的 ComfyUI Python；运行期强制 `DIFFSYNTH_SKIP_DOWNLOAD=True`。每个 cache 必须内嵌 `use_gradient_checkpointing=True`，否则在模型加载前直接拒绝。正式训练仅在三步命令生成 `epoch-0.safetensors` 后扩大数据重复和 epoch。

当教师 Target 仅有面板水平位置偏差时，可按 Source 做确定性对齐；不得用它修补几何或绕过其他 Gate：

```powershell
python .\tools\model_test\normalize_turnaround_panel_geometry.py <target.png> `
  --reference <source.png> --output <target.normalized.png> `
  --report <target.normalization.json>
```

Base 原生诊断也必须通过发现式、禁止下载的入口；该命令不属于 3060 生产工作流：

```powershell
python .\tools\model_test\run_flux2_base_actor_core_diagnostic.py `
  --source <source.png> --lora <epoch-N.safetensors> `
  --prompt-file <caption.txt> --output <diagnostic.png>
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
