# Actor Core 图像编辑训练

## 已确定的技术边界

`strip_to_actor_core` 是通用实验室任务：输入完整风格角色三视图，输出同布局、同姿态、同头身比的无身份无部件 Actor Core。它不绑定 `ba`，`ba` 只是一枚消费者标签。

生产链必须能在 RTX 3060 12GB 上离线推理。训练可以临时使用远程或更大显存，但训练产物必须回到 3060 上完成最终编辑；不能做到这一点的模型不得成为 Studio 默认后端。

当前后端分工：

| 层 | 默认选择 | 是否必需 | 职责 |
| --- | --- | --- | --- |
| 生产推理 | FLUX.2 Klein 4B distilled FP8 | 是 | 4 步本地编辑，加载任务 LoRA，目标硬件为 3060 12GB |
| 可学习性诊断 | FLUX.2 Klein 4B Base LoRA | 训练时 | 验证 Pair/Target 是否能学会；不得直接迁移成生产 LoRA |
| 生产 LoRA 训练 | FLUX.2 Klein 4B distilled-native | 训练时 | 对生产权重族原生学习 `strip_to_actor_core`；可远程训练 |
| 教师 Target | 人工绘制或可选远程教师 | 否 | 只提出候选 Target，不能自动批准 |
| Qwen-Image-Edit | 可选实验教师 | 否 | 不再是 Studio、数据或生产推理依赖 |
| 回退 | SDXL + LoRA/ControlNet/InstructPix2Pix | 条件回退 | Klein 训练产物无法在 3060 通过硬件 Gate 时启用 |

Black Forest Labs 将 4B Base 定位为有限硬件微调/LoRA版本，将 distilled 4B 定位为快速生产推理版本：<https://github.com/black-forest-labs/flux2/blob/main/README.md>。ModelScope 的 Base 仓库为 `black-forest-labs/FLUX.2-klein-base-4B`：<https://modelscope.cn/models/black-forest-labs/FLUX.2-klein-base-4B>。

## 数据合同与可迁移性

权威数据是模型无关的 `source + target + 可选 mask + caption + Gate + provenance`，schema 为 `schemas/strip_to_actor_core_pair.schema.json`。任何训练器导出都是可重建适配层，不得反过来污染原始 Pair。

- Source：已批准风格角色三视图。
- Target：同尺寸、同布局、同姿态的标准 Actor Core。
- Mask：可选人工校正范围，不是 Target 替代品。
- Provenance：记录 Target 是人工、远程教师还是本地模型生成；同时记录唯一几何权威 ID/SHA256 与确定性对齐操作；来源与人工批准相互独立。
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

当前训练集只有一个几何权威：`actor_core_male_canonical_v1`，原始 Target SHA256 为 `6c68f26074a1ecdda00b00e372901cf3538b1448349de6f72ed556177b57d5e5`。外部图像教师只提出过候选；最终数据不再为不同 Source 生成不同 Target。所有 Target 都必须从这张权威图出发，只做逐面板等比缩放与整数平移以对齐 Source 的高度、中心和地面线；工具禁止非均匀缩放、局部变形和形体重绘。

四个 approved Pair 均通过自动/人工 Gate，并声明相同 authority ID/SHA256：

- `canonical_actor_core_male_20260827_v1`：下躯干 `0.5372`，侧脚 `1.0964`；
- `canonical_actor_core_bob_cowl_20260827_v1`：下躯干 `0.5395`，侧脚 `1.1099`；
- `canonical_actor_core_scout_cape_20260827_v1`：下躯干 `0.5374`，侧脚 `1.0976`；
- `canonical_actor_core_longhair_d70b_20260827_v1`：下躯干 `0.5392`，侧脚 `1.1098`。

`audit_strip_to_actor_core_pairs.py` 现在同时审计每张 Target 的形体 Gate 和跨 Pair 几何权威一致性；缺少 authority 字段、ID/SHA256 不一致或对齐操作未声明都会失败。Pair 保留通用 StyleProfile，并仅以 `consumer_tags=["ba"]` 记录近期消费者。

v5 Base 使用版本化导出、四 Pair、589,824-pixel gradient-checkpointing cache、rank 16、6 repeats、5 epochs，共 120 steps。五个 checkpoint 均落盘；epoch-4 SHA256 为 `1672F079545A3BCFAB26F5D4A19B05918DDE0BD028D0D82314E91F8620CB1624`。在未参与训练的长发 `74e7...` Source 上，768×384、20-step、seed 20260841 的 Base 原生对照同时通过：躯干 `0.5369`、侧脚 `1.1932`。因此四 Pair/canonical Target 已经能让 Base 学会任务。

同一 v5 Base LoRA 直接迁移到 distilled FP8 的 held-out 阶梯仍全部失败：

- strength 2.0：躯干 `0.5479`，侧脚 `1.2674`；
- strength 2.5：躯干 `0.5510`，侧脚 `1.2174`；
- strength 3.0：躯干 `0.5542`，侧脚 `1.2000`。

这组对照把问题明确归类为 Base→distilled 权重族迁移失败，不再继续提高跨族 LoRA 强度。

为复用本机已有生产权重且避免重复下载，`convert_comfy_flux2_fp8_to_diffsynth_bf16.py` 使用 Comfy 自身 FLUX 键映射与 checkpoint 内记录的 `weight_scale`，把 scaled-FP8 融合张量确定性反量化为 DiffSynth BF16 训练键。转换结果 169/169 tensor 与本地官方 Base 的键/shape 模板一致，80 个 FP8 融合源均使用自己的 scale；Base 文件只提供键名/shape，不提供任何数值。报告固定 `downloaded=false`。DiffSynth 识别结果为 Klein 4B distilled（5 double blocks、20 single blocks、`guidance_embeds=false`），4-step smoke 完成反向训练。

distilled-native 正式训练沿用相同四 Pair/cache，rank 16、6 repeats、5 epochs，共 120 steps，2026-08-27 用时约 8 分 33 秒。epoch-4 SHA256 为 `EC414439CECC5E23BA8B9D4A5FCF65DCCDE0634B4AF1555B4FA89DCDD16FEEFD`；96-step checkpoint SHA256 为 `9F9BAB1DB19C4F409E8B92784111365B23BCC9E3EFE2B742719902796B4208DB`。

held-out 结果中，96-step/strength 2.5 是当前视觉最佳：头发、服装、五官、耳朵和身份内容已清除，严格 front/right/back 成立，躯干通过 `0.5395`，但侧脚仍为 `1.3415`，未达到 `<=1.20`。72-step 尚未稳定检测躯干；120-step/strength 3.0 开始把中间侧视拉向正面。继续堆训练步数或强度会换来视角坍缩，已停止。

所有自动失败候选均已通过 Studio 生命周期从活跃目录删除。只读评审目录保留 Source、唯一 canonical Target、Base 通过图与 distilled-native 视觉最佳图；它们不进入 Gallery、随机池、资产库或 3D。当前下一步是保持同一几何权威，对小腿到脚区域增加训练权重或确定性裁片，而不是放宽 Gate 或新增另一套素体。

## 注册与导出

候选注册示例：

```powershell
python .\tools\model_test\register_strip_to_actor_core_pair.py `
  --source <已批准风格角色图> `
  --target <人工或教师候选素体图> `
  --style-profile-id qstyle_anime_western_fantasy_no_face_v1 `
  --target-producer remote_teacher `
  --target-generator <教师标识> `
  --target-geometry-authority-id <唯一 Actor Core 几何 ID> `
  --target-geometry-authority-sha256 <原始 canonical Target SHA256> `
  --target-geometry-operation <逐面板等比缩放和平移说明> `
  --consumer-tag ba `
  --caption "convert the supplied character into the canonical blank Actor Core while preserving layout, pose and proportions"
```

人工确认前不要添加 `--approve`。确认完成后才可使用 `--approve --confirm-manual-gates` 重新登记批准版本。

FLUX.2 / ModelScope DiffSynth 导出：

```powershell
python .\tools\model_test\export_strip_to_actor_core_diffsynth_dataset.py --validate-only
python .\tools\model_test\export_strip_to_actor_core_diffsynth_dataset.py `
  --output-dir <新的版本化导出目录>
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

入口依次搜索专用环境变量、仓库工作区和相邻 ComfyUI；它把 `model_paths` 作为真实 JSON 参数数组传给 DiffSynth。若系统 Python 没有 PyTorch，会自动切换到发现的 ComfyUI Python；运行期强制 `DIFFSYNTH_SKIP_DOWNLOAD=True`。每个 cache 必须内嵌 `use_gradient_checkpointing=True`，否则在模型加载前直接拒绝。正式训练仅在每 Pair 一次的 1-epoch smoke 生成 `epoch-0.safetensors` 后扩大数据重复和 epoch。

生产 LoRA 必须针对 distilled 权重族原生训练。本机已存在 Comfy scaled-FP8 Transformer 时，可先做不下载、可审计的 BF16 训练转换；路径均为搜索/发现后的占位符，不得复制当前机器盘符：

```powershell
python .\tools\model_test\convert_comfy_flux2_fp8_to_diffsynth_bf16.py `
  --input <发现到的 Comfy distilled scaled-FP8 Transformer> `
  --output <本地转换目录>/diffusion_pytorch_model.safetensors `
  --key-template <发现到的官方 DiffSynth FLUX.2 4B Transformer> `
  --report <本地转换报告.json>

python .\tools\model_test\train_flux2_actor_core_lora.py `
  --cache-dir <DiffSynth 两阶段缓存目录> `
  --output-dir <本地 distilled-native LoRA 输出目录> `
  --transformer-path <转换后的本地 distilled BF16 Transformer> `
  --dataset-repeat 1 --epochs 1 --max-pixels 589824
```

转换器只接受 checkpoint 自带 scale 的 FP8 权重，并强制与官方 4B 键/shape 模板 169/169 对齐；模板只用于结构校验，绝不补写 Base 权重。没有可验证 scaled-FP8 时，不得近似转换，应通过 ModelScope 获取官方 distilled 训练权重或停止该实验。

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

## 2026-08-28 数据覆盖与 distilled-native 复核

局部 latent 脚部加权已用固定 held-out 条件证伪：相对 v5/e96 基线，它没有改善脚部且破坏了全局躯干映射。该实验的脚本、活跃候选和 Comfy LoRA 均未进入仓库或 Studio 默认路径；不得继续沿用局部损失加权。

canonical 对齐仍只允许逐面板等比缩放与平移。`normalize_turnaround_panel_geometry.py` 现在显式记录插值方式，并默认使用 bicubic；长发 `74e7...` 的同一 canonical Target 在 Lanczos4 下因轮廓振铃得到躯干 `0.5408`，bicubic 下为 `0.5374`，在不放宽 `0.54` Gate 的情况下通过。当前六个 approved Pair 均声明同一 authority ID/SHA256；新增的两类强脚部 Source 为长发靴装 `74e7...` 和严格侧面短发学徒 `a098...`。

五 Pair v6 distilled-native 训练使用 589,824 pixels、rank 16、5 repeats、5 epochs，共 125 steps。视觉与 Gate 的当前折中点为 75-step / strength 3.0，LoRA SHA256 为 `f0656f068ca5a76092af289a3129451e3faace67467f552c85ab27a97131da4c`。在未参与训练的短发男性强靴 Source、seed `20260861` 上，旧 v5/e96/2.5 为躯干 `0.5102`、侧脚 `1.2628`；v6/e75/3.0 为躯干 `0.5118`、侧脚 `1.0972`，两项同时通过。

六 Pair v7 的 96-step / strength 2.5 虽在上述单一 held-out 上得到躯干 `0.4851`、侧脚 `1.1277`，但视觉出现过度剥离，并在第二张未训练 Source 上得到躯干 `0.5741` 而失败。因此 v7 不成为 Studio 默认权重；不得以单图自动指标覆盖跨 Source 视觉稳定性。

Studio 当前只保留 v6/e75 作为生成候选的默认 LoRA，默认强度为 3.0。它不是已批准资产：任一输出仍必须逐张通过自动 Gate 与人工六项 Gate；失败候选直接销毁并重试，不进入 Gallery、随机池、资产库或 Hunyuan3D。真实 RTX 3060 12GB 冷启动、4-step 编辑、保存恢复和峰值显存 Gate 仍待用户机器验证；5070 Ti 的 1536×768 运行记录不能替代该硬件验收。

## 2026-08-28 跨 seed 与增量训练复核

使用当前 Studio 默认提示词、同一未训练短发男性强靴 Source、v6/e75/strength 3.0 复测五个 seed，仅 `20260865` 同时通过自动 Gate，躯干为 `0.5324`、侧脚为 `0.9809`，通过率 `1/5`。其余输出普遍保留可见的鞋状前投影；这不是检测器误伤。此前单张最佳图只能证明链路具备能力，不能证明权重已风格稳定。

以 v6/e75 为 checkpoint，在六 Pair canonical 缓存上分别继续 6/12/18/24 step。12 step 以后迅速破坏躯干或脚部；只有 `+6 step / strength 2.0` 在 seed 61 和 65 上通过，但扩到十 seed 后仅 `2/10`，且两个幸运 seed 在侧面双靴歧义压力 Source 上均失败。因此该 v8 实验权重全部退出 Comfy/Studio 搜索路径，只保留在本地 rejected/训练证据目录，不替换 v6。

5070 Ti 的后续职责是继续增加真实多样 Source 与唯一 canonical Target 的教师 Pair，并提高跨 Source/跨 seed 通过率。3060 生产链不得依赖训练环境；其完整环境、冷启动、推理、Gate、保存恢复和回退合同见 `docs/RTX3060_PRODUCTION.md`。
