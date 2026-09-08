# 脚底薄片修复与标定交接（2026-09-09）

结论：修脚版可用于实验性人工 AccuRIG 标定，不代表最终美术或动作验收。旧 50k v2 和旧 FBX 留作对照，不再作为本轮标定输入。

唯一新输入：`workspace/local_generation/actor_foot_repair_20260908/local_v2/accurig_input/Actor_Offline_v2_FootRepair_AccuRIG.fbx`。

## 修复与验证

- 原脚底内侧两片薄面在底视和斜视明显可见，原模型虽封闭且 Euler=2，仍应被拒绝。输入 alpha 同位置包含粉灰投影，清理版只移除脚部 ROI 的 alpha，RGB 和区域外像素不变；它是源级诊断，不宣称已经重跑生成。
- 局部挤压 v1 有 23 个面相对原面法线翻转超过 90°，拒绝交接。
- v2 使用原脚在总高 1.5% 处的完整截面，仅重建其下方圆角脚底，回到原足底高度。不重新生成全身，不套椭圆脚或旧素体，不改变头身、手臂、躯干和上部足形。
- Blender 内 23899 个保护区顶点误差为 0；导出后另以双向最近点和 `1e-6H` 容差复核。新网格 26115 顶点、52226 面，单连通、封闭、绕序一致、Euler=2，7 层双脚截面分离。
- 新脚底薄边检查拒绝原件：相对原完整截面的最大低位外伸为 `0.01648H`，修复后所测截面为 0；门槛 `0.0015H` 未放宽。这是脚底专项筛查，不是通用风格或完整自交证明。
- 已检查正、侧、背、斜视、底视。脸部浅痕、手形仍是独立美术项；没有认证全身内部自交、关节面流、蒙皮或动画表现。
- FBX 往返保持顶点/面数及流形性，最大双向顶点误差 `3.2782554626464844e-07`，原 GLB 未改。

复盘方法来自质量复盘与参考验证技能：不以整体 IoU/封闭性替代局部外观，保留失败反例，补脚部特写与保护区检查。共享技能未修改。

## 标定

手指数量为 0，文件仅含素体，不含腰带。请保存标定工程，并另存包含网格与骨架的 FBX，不覆盖输入。先验证垂臂、抬臂、屈膝，再做走路及腰包动态间隙实验。

## 复现（无模型、无下载）

复用具备 NumPy/OpenCV/Pillow/SciPy/trimesh 的本地 Python 和 Blender 4.5。下面 `$Blender` 表示已发现的可执行文件，所有输出目录必须为新目录。

```powershell
python tools/model_test/verify_actor_foot_checkpoint.py
python -m unittest discover -s tools/model_test -p test_actor_foot_repair.py -v
& $Blender --background --factory-startup --python-exit-code 1 --python tools/model_test/rebuild_actor_sole_blender.py -- --input workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb --output workspace/local_generation/foot_replay_new
python tools/model_test/audit_actor_foot_repair.py --source workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb --candidate workspace/local_generation/foot_replay_new/foot_candidate.glb --output workspace/local_generation/foot_replay_new/audit.json
```

发布版 FBX 可直接使用。导出器 `export_actor_offline_calibration.py --foot-repaired` 只接受发布版 GLB 的精确哈希，不能用它给未知重跑结果自动授权；重跑生成的文件容器/顶点顺序可能不同，必须重新审查，不承诺跨版本逐字节一致。

检查证据：同目录的 `repair_report.json`、`structure_audit.json`、`final_audit_v2.json`、`foot_before_after.png` 和 `accurig_input/handoff.json`。完整资产哈希清单在 `milestones/actor_foot_repair_20260909/checkpoint.json`。
