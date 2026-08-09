# 鞋子当前工作流

## 正式里程碑

`milestones/shoes/cartoon_sneaker_v10/` 已由用户确认可作为里程碑。

参数合同：

- `toe_extra = 0.160`
- `heel_extra = 0.060`
- `radial_width_scale = 1.80`
- `radial_height_scale = 1.80`
- `weight_mode = rigid_foot_toe`

源 FBX 位于 `references/shoes/cartoon_sneaker/source/Shoessneakers.fbx`。包内未附许可证，因此仓库保持私有，且公开发布前必须补充授权信息。

## 重建

```powershell
& E:\Env\Blender\blender.exe --background --python .\tools\blender\build_actor_cartoon_sneaker_fbx_v1.py -- `
  --actor-blend .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --reference-fbx .\references\shoes\cartoon_sneaker\source\Shoessneakers.fbx `
  --output .\workspace\shoes\cartoon_sneaker_v10 `
  --toe-extra 0.160 --heel-extra 0.060 `
  --radial-width-scale 1.80 --radial-height-scale 1.80 `
  --weight-mode rigid_foot_toe --resolution 256
```

## 审查

- 正面、侧面鞋头均覆盖脚掌。
- 鞋跟和鞋筒不被脚/小腿遮住。
- 左右鞋比例一致。
- Foot/ToeBase 运动无滑动或零件分离。
- 保留四向 GIF 和近景帧；人工审核优先于单帧包络统计。

