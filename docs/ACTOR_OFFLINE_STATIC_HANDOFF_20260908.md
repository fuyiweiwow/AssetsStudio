# 当前素体：未绑定轻量网格与静态配件

用户暂时不能手动绑定；沿用既有未绑定 T-Pose 支线，不启动自动 Rig 替代研究，不复用旧 Actor 骨骼。原始形体保持冻结。

## 已完成：50k 轻量副本

源：`workspace/local_generation/actor_offline_gate_20260908/run_v2/shape.glb`。

有效副本：`workspace/local_generation/actor_offline_gate_20260908/static_50k_v2/actor_offline_v2_50k_rig_mesh.glb`，SHA256 `e7e88465037df7ef3e5b018f19d36694e0d6c8ab081dced7fc17ace307a17068`。

- 270192 → 50000 三角面，25002 顶点；约减少 81.5% 的面数。
- 复用 `prepare_actor_core_rig_mesh.py` 的确定性 collapse 减面，增加源/输出哈希、坐标归一化平移记录、拒绝覆盖和共享平滑法线导出。
- 原件不修改。导出 GLB 重新载入后，单连通、封闭、Euler=2、面朝向一致、7 层脚部切片分离全部通过。
- 四向轮廓对比原始 3D 渲染，平均 IoU `0.999860`、最低 `0.999816`；包围盒最大尺寸漂移 `0.00569%`。这些只验证减面保形，不是源图风格得分，也不验证内部自交、关节布线或动画质量。
- 第一次 `static_50k` 因平面法线导出成拆分顶点，外部拓扑检查失败，不能用。只使用 `static_50k_v2`。

这仍是静态实验/绑定准备副本，不是已经完成动画拓扑的游戏成品。保留 50k 作为中间版本；是否进一步减面，应依据真实游戏呈现和变形测试，而不是现在追求最低面数。

## 已尝试：重新测量腰部与复用配件

新增 `measure_unbound_waist.py`：从当前 Y-up 网格的下身截面双环过渡、横向最大臂展区间推定躯干，再在该区间的 45% 位置给出待审核腰线。当前胯点约 `0.165H`、臂展行 `0.395H`、腰线 `0.2685H`。只输出腰部一个 Slot，不伪造其余 10 个位置，更不套用旧三头身的固定高度。

该检测依赖双腿分开、近似水平展开双臂，尚未通过多 Actor 测试；`waist_profile.json` 必须保持实验/待人工确认身份。位置经人体截面计算，但语义腰线仍是启发式，不能当自动标定。

复用已有本地 Hunyuan 生成的腰带腰包（不是新生成或规则建模），通过既有 `fit_tpose_accessory_blender.py --surface-conform` 试装。两次试装 `waist_fit_v1` 与 `waist_fit_v2` 都没有表面三角形相交，但均未通过槽位边界检查。

第二次宽/深系数 `0.9/0.9`，最大轴缩放比 `1.147732`；前侧最小深度 `-0.252133` 超过允许的 `-0.240410`，约超出 `0.0059H`。未扩大边界强行放行，也没有注册到 Studio 候选列表或资产库。表面零相交亦不能单独证明没有包裹式穿透。

下一步应区分「贴身腰带的接触面」与「腰包允许占据的前侧空间」，用当前 Actor 截面约束它们，先审核腰线和外观，再检验空间边界、双向包含和腿部静态间隙。骨骼、蒙皮、走路和动态间隙仍延后到人工标定完成。

## 复现

按 `ENVIRONMENT.md` 搜索 Blender 和现有 Hunyuan Python，激活 Python 专用环境。下面 `$Blender` 表示发现的可执行文件，不是固定安装路径。全部 Blender 命令使用后台模式；建议带 `--python-exit-code 1` 传播脚本错误。输出目录必须是新的，保留历史证据。

```powershell
$Root = 'workspace/local_generation/actor_offline_gate_20260908'
$Out = 'workspace/local_generation/actor_static_replay'
& $Blender --background --factory-startup --python-exit-code 1 --python tools/model_test/prepare_actor_core_rig_mesh.py -- --input "$Root/run_v2/shape.glb" --output-dir "$Out/body" --asset-id actor_offline_v2_50k --target-faces 50000
python tools/model_test/actor_core_offline.py audit --mesh "$Out/body/actor_offline_v2_50k_rig_mesh.glb" --report "$Out/body/audit.json"
python tools/model_test/measure_unbound_waist.py --actor "$Out/body/actor_offline_v2_50k_rig_mesh.glb" --output "$Out/body/waist_profile.json" --actor-id actor_offline_v2_50k
$Accessory = 'workspace/accessory_fit/chibi3_v9b/waist_accessory'
& $Blender --background --factory-startup --python-exit-code 1 --python tools/model_test/fit_tpose_accessory_blender.py -- --actor "$Out/body/actor_offline_v2_50k_rig_mesh.glb" --accessory "$Accessory/hunyuan/waist_accessory_seed20260831_accessory.glb" --profile "$Out/body/waist_profile.json" --slot-id waist_accessory --source-preparation "$Accessory/source_preparation.json" --shape-manifest "$Accessory/hunyuan/shape_manifest_accessory.json" --output-dir "$Out/fit" --asset-id actor_offline_v2_waist --surface-conform --width-factor 0.9 --depth-factor 0.9 --resolution 768
```

最后一步预期报告 `automatic_review_failed`，不是生产复现失败；它重现了待解决的边界问题。以报告为准，不因存在预览就放行。

轻量网格和试装均未进行 3060 实机测试；这轮不训练、不下载模型，也不触碰任何已有 AccuRIG 标定文件。
