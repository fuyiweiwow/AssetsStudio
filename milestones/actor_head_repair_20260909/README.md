# 可移植头部修复检查点

包含用户 AccuRIG 原始绑定、已验证修复 FBX、修复前后报告、四向图和本地走路测试源。无需下载 AI 模型或重新人工标定。`walk_source.fbx` 只作为当前项目动作诊断输入，不是生成模型权重。

依赖：Python 标准库和 Blender 4.5（NumPy 使用 Blender 自带版本）。Blender 可通过 `--blender` 或 `BLENDER_PATH` 指定，也可由脚本发现。

```powershell
python tools/model_test/actor_head_checkpoint.py verify
python tools/model_test/actor_head_checkpoint.py replay --output workspace/head_replay
python tools/model_test/actor_head_checkpoint.py walk --output workspace/walk_replay
```

输出目录必须不存在。成功时输出 `HEAD_REPLAY_PASS`，并生成可编辑 Blend、FBX、32 姿态报告和 25 张检查图。复现验证几何、权重与变形指标；FBX 的导出元数据可能使新文件整文件哈希不同。

现成修复文件为 `repaired.fbx`，原始输入为 `source_accurig.fbx`。极端颈肩褶皱及完整动作验收仍有边界，详见 [修复说明](../../docs/ACCURIG_HEAD_REPAIR_20260909.md)。此检查点不表示资产已入库。

`walk/` 包含 Walk 专用四权重 GLB、实际运行时四向 GIF 和报告；不是其他动作的通用权重批准。详细说明见 [走路验证](../../docs/ACTOR_WALK_VALIDATION_20260909.md)。
