# Actor Core 图像编辑训练

## 当前结论

`strip_to_actor_core` 是通用实验室任务，不绑定 `ba`：输入带身份、头发、服装和配件的风格角色图，输出同姿态、同头身比、无身份无部件的连续 Actor Core。

Qwen-Image-Edit-2511 Q3_K_M 与 Q4_K_S 均已完成相同种子的两阶段对照。两者都能稳定去掉头发、眼睛、服装和配件并保持 front/right/back，但都会把被服装遮挡的身体补成偏梨形/鼓肚体。Q3 的局部编辑曾新增背面圆形标记；Q4 能保持表面干净，却仍忽略窄躯干轮廓参考。量化不是主要瓶颈，继续堆叠零样本提示词已停止。

## 配对数据合同

- Source/control：完整风格角色图；允许带项目标签，但任务标签始终是 `strip_to_actor_core`。
- Target：同尺寸、同布局、同姿态的无身份 Actor Core。
- Mask：可选，只记录人工校正范围，不作为 Target 的替代品。
- 候选、批准和拒绝数据全部位于 `workspace/training/strip_to_actor_core/`，不上传 Git。
- `candidate` 不进入训练。只有人工确认全部 Gate 并显式注册为 `approved` 的 pair 才能导出。
- 失败生成图和 `build_actor_core_silhouette_guide.py` 产生的二值轮廓只能帮助人工标注，不得直接冒充批准 Target。仓库不提供规则变形 Target 生成器。

人工 Gate：

1. 光头、无耳、无五官；
2. 无头发、服装、鞋和配件；
3. 单一连续、无性征、无表面标记的玩具式素体壳；
4. 窄而轻微收束的躯干，不是梨形婴儿体；
5. front/right/back 描述同一个体积；
6. 无缝线、孔洞、圆点、合成接缝或背景污染。

## 本地注册与导出

注册候选时不要添加 `--approve`：

```powershell
python .\tools\model_test\register_strip_to_actor_core_pair.py `
  --source <完整角色图> `
  --target <人工校正素体图> `
  --mask <可选校正掩码> `
  --style-profile-id qstyle_anime_western_fantasy_no_face_v1 `
  --consumer-tag ba `
  --caption "convert the character into the canonical blank Actor Core while preserving pose, proportions and views"
```

人工检查完成后才可用 `--approve --confirm-manual-gates` 注册批准版本。导出器只读取批准 pair，并生成 Musubi Tuner 要求的 target `image_directory`、source `control_directory`、同名 caption 和 `dataset.toml`：

```powershell
python .\tools\model_test\export_strip_to_actor_core_dataset.py --validate-only
python .\tools\model_test\export_strip_to_actor_core_dataset.py
```

数据目录遵循 Musubi Tuner 的 [control-image dataset contract](https://github.com/kohya-ss/musubi-tuner/blob/main/docs/dataset_config.md)。训练使用其 [Qwen-Image `edit-2511` 路径](https://github.com/kohya-ss/musubi-tuner/blob/main/docs/qwen_image.md)。12GB 显存首轮保持 768×384、batch 1、FP8 DiT、FP8 VL、gradient checkpointing 和 block swap。没有至少一组批准 pair 时，不下载 BF16 训练权重，也不启动训练。
