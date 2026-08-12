# 短裤当前工作流

## 选择

当前保留 `milestones/pants/native_control_v0/`：直接从 Actor 下半身拓扑提取连续表面、保留原骨骼权重并做小幅法线净空。它是从零重建后用户视觉评价明显优于旧 GarmentCode 转移的版本。

旧 GarmentCode `solution2`、v31、连续代理和体型参数扫掠全部不进入正式仓库：它们分别出现裆部撕裂、侧面缺片、整体陷入身体或不自然变形。

## 生成

```powershell
New-Item -ItemType Directory -Force .\workspace\pants | Out-Null
& E:\Env\Blender\blender.exe --background --python .\tools\blender\build_native_shorts_control.py -- `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --output .\workspace\pants\native_control_shorts.blend `
  --lower-z 0.40 --upper-z 0.738 --max-abs-x 0.40 `
  --surface-offset 0.012 --solidify-thickness 0.006
```

然后使用 `tools/blender/render_actor_clothing_eevee.py` 渲染四方向 8 帧，并用 `tools/make_clothing_review_gifs.py` 打包 GIF。

## 审查重点

- 正面裆部连续，不撕裂。
- 侧面大腿外侧有完整垂直裤料。
- 背面裆部不裂开。
- 裤腰和裤脚允许低分辨率锯齿，但不能出现独立碎块。
- 动画中可接受极少量不显眼穿模，不以“绝对零穿模”逼迫几何变得不自然。

## Actor 专用 GarmentCode 实验路线

`pants_workflow_test` 新增了与短袖相同的数据边界：Actor REST 网格与骨架测量 → Actor 专用 Pants body YAML → Actor 下半身闭合碰撞代理 → GarmentCode Pants 仿真 → 精确衣片成员关系 → Actor 骨盆/左右大腿原生混合权重转移 → 四向动画审查。它不读取旧 demo 衣服，也不在仿真后缩放、Shrinkwrap、外推或补洞。

固定依赖安装完成后，可运行：

```powershell
.\tools\run_actor_specific_garmentcode_shorts.ps1 `
  -GarmentCodeRoot .\third_party\GarmentCode `
  -Output .\workspace\garmentcode_pants_actor_v1
```

一键入口会先验证 `docs/WORKFLOW_TOPS.md` 固定的 GarmentCode/Warp 提交，再生成测量、碰撞体、版型、仿真、Actor 转移、fit 报告和四向 GIF。fit 失败时脚本返回非零，以免把实验候选误当作可发布结果。

首个 `width=1.05` 候选在修正碰撞代理面序后达到身体碰撞 0、自相交 0，视觉上形成完整短裤；但走路 fit 仍失败，因此现有 `milestones/pants/native_control_v0/` 保持不变。后续只允许修正裤腰/裆部/左右裤腿的动作权重合同，不回到旧 v21-v45 的生成后几何补丁路线。实验数据和结论见 [`features/F007-actor-garmentcode-shorts.md`](features/F007-actor-garmentcode-shorts.md)。
