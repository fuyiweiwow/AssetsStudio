# Actor Core 人工 AccuRIG 回传工作流

## 边界

AccuRIG 标点与蒙皮是人工过程，并且结果与 Actor Core 一对一。Studio 不自动替代标点，也不把骨骼保存成可跨模型复用的独立资产。页面只负责把人工导出的 FBX 回传到所选 Actor 的本地工作区，执行确定性审计、运行副本转换和预览。

## 页面流程

1. 在 Studio 的“已批准 3D 来源”卡片下载该 Actor 的 `AccuRIG FBX`；
2. 在 AccuRIG 中为这一份模型人工确认中心线、头颈、肩肘腕、髋膝踝和足尖方向，完成蒙皮并导出 FBX；
3. 回到同一 Actor 卡片，点击“选择骨骼 FBX”；
4. Studio 立即把文件复制到该 Actor 专属目录，并显示上传、处理、成功或失败状态；
5. 成功后页面显示实际 Armature 与蒙皮身体的 `front/right/back/left` REST 预览，并开放蒙皮 GLB、四权重 Blend 和校验报告下载。

页面选择文件只接受 `.fbx`。新的回传创建新的 intake ID，不覆盖旧 intake；`current.json` 只指向当前一次。失败文件不会成为可用骨骼，也不会进入 Gallery、随机池或 AssetRegistry。

## 本地存储

所有内容位于 Git 忽略的本地工作区：

```text
workspace/actor_core/<3d-asset-id>/manual_accurig/
  current.json
  intakes/<intake-id>/
    intake.json
    source/accurig_export.fbx
    blender.stdout.log
    blender.stderr.log
    processed/
      validation.json
      <rig-asset-id>_accurig_raw.blend
      <rig-asset-id>_runtime_4weights.blend
      <rig-asset-id>_rigged_preview.glb
      preview/front.png
      preview/right.png
      preview/back.png
      preview/left.png
```

`source/accurig_export.fbx` 是人工结果原件；`accurig_raw.blend` 保留 AccuRIG 原始权重；`runtime_4weights.blend` 只保留每顶点最强四项权重并重新归一；GLB 与 PNG 只用于 Studio 预览。任何转换都不改写已入库高模、交接 FBX或人工上传原件。

## 一对一 Gate

后台使用环境搜索发现 Blender：显式 `BLENDER_PATH`、PATH、仓库同级便携版、Program Files，顺序匹配后使用；文档不要求固定盘符。

上传文件必须同时通过：

- 一个网格、一个 Armature、一个有效 Armature modifier；
- 23 个必需的 `CC_Base_*` 身体关节全部存在；
- 无未加权顶点，权重和误差不超过 1%，原始权重最多八项；
- 顶点数和面数与该 Actor 的 AccuRIG 交接清单完全一致；
- 三轴尺寸相对交接清单最大漂移不超过 1%；
- 模型落地、位于 `X=0` 中心面且 Z 为长轴。

因此把另一个 Actor 的骨骼 FBX 上传到当前卡片会失败，即使骨名相同也不能通过拓扑与尺寸 Gate。

## 处理与预览

入口脚本为 `tools/model_test/process_actor_core_accurig_rig.py`。它在 REST 状态清除导出文件中的动作，先保存原始权重 Blend，再生成四权重运行副本与带 Skin 的 GLB。四向 PNG 使用半透明身体和实际骨骼的彩色关节链；半透明只作用于审查渲染，不写回 Blend 或 GLB。

当前自动逻辑到 REST 预览为止。预览通过后仍需新增显式人工批准 Gate，随后才能执行 Walk/Run 重定向、肩肘髋膝变形、落脚、有限值和四向动作 QA，并最终生成 ActorProfile。没有人工批准时，`binding_performed` 不能自动改成完成。

## 已验证范围

- 用历史已验证 AccuRIG Actor 完成成功路径烟雾测试：101 根骨骼、无缺失必需骨、无未加权顶点；2,551 个超过四权重的顶点被裁剪并重新归一，运行副本最大四权重；四向实际骨架预览和蒙皮 GLB均成功生成。
- 用当前未绑定交接 FBX验证拒绝路径：后端正确报告 `armatures=0`、`rigged_meshes=0`，未产生可用骨骼状态。
- 当前 `0ef398ca...` 的真实人工 AccuRIG 文件尚未生成；最终视觉与变形结论必须等用户实际回传后确认。
