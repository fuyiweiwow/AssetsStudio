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

