# Actor 专用 GarmentCode 短袖工作流

## 当前状态

当前唯一保留的候选是本地 `workspace/garmentcode_restart_actor_length_0p90_repro_v1/`。它由当前非标准 Actor 的 REST 测量、Actor 上半身碰撞代理和 GarmentCode 衣片生成；最终网格未做 Blender 缩放、Shrinkwrap、顶点外推或补洞。Blender 只负责坐标映射、Actor 原生骨骼权重转移和预览。

人工四向动画审查已通过“外观可继续”的门槛，但自动报告仍有 1184 个 GarmentCode 自相交和 326 个碰撞弹簧，因此状态保持 `provisional`，不能进入 Gallery 或随机化。

## 唯一数据基线

| 用途 | 路径 | 约束 |
| --- | --- | --- |
| Actor | `milestones/body/chibi_actor_mixamo_walk_v1.blend` | 必须是测量报告中的 `source_actor` |
| Actor 测量 | `workspace/garmentcode_actor_native_measurements_v2/actor_v1_garmentcodedata_centered_measurements.json` | REST、厘米、完整 body/arms |
| GarmentCode body YAML | `workspace/garmentcode_actor_native_measurements_v2/neck_boundary_body_13p0.yaml` | 含 Actor 袖长、袖口周长和连接宽度 |
| 碰撞体 | `workspace/garmentcode_actor_native_measurements_v2/actor_torso_upperarm_surface_rest_partial_boundary_filled_v1.obj` | Actor REST 躯干和左右上臂 |
| 碰撞分区 | `workspace/garmentcode_actor_native_measurements_v2/actor_torso_upperarm_surface_rest_source_v1_segmentation.json` | 与碰撞体顶点顺序一致 |
| 版型 | `workspace/garmentcode_restart_actor_length_0p90_repro_v1/garmentcode_restart_actor_length_0p90_repro_v1_seed_1/` | `shirt_length_factor=0.90`，seed 1 |
| 静态仿真 | `workspace/garmentcode_restart_actor_length_0p90_repro_v1/simulation_100f_actor_locked/` | 16340 顶点，保留精确 panel membership |
| Actor 转移 | `workspace/garmentcode_restart_actor_length_0p90_repro_v1/actor_transfer_native_weight_mix_v3/` | 唯一正式预览和 Blend |
| 审计 | `workspace/garmentcode_restart_actor_length_0p90_repro_v1/audit/` | 精简 JSON；不保留重复诊断网格 |

`workspace/` 按仓库策略不提交云端；代码、依赖补丁和本页流程提交。需要归档本地数据时应单独打包，不得把实验缓存加入 Git。

## GarmentCode 依赖

固定官方 GarmentCode 提交：`d449629979028123a5c4dc9e732a2ec19b7fce31`。在干净 checkout 上应用 Actor 字段补丁并验证：

```powershell
git clone https://github.com/maria-korosteleva/GarmentCode.git .\third_party\GarmentCode
git -C .\third_party\GarmentCode checkout d449629979028123a5c4dc9e732a2ec19b7fce31
python .\tools\garmentcode\apply_garmentcode_actor_patch.py --garmentcode-root .\third_party\GarmentCode
git clone https://github.com/maria-korosteleva/NvidiaWarp-GarmentCode.git .\third_party\NvidiaWarp-GarmentCode
git -C .\third_party\NvidiaWarp-GarmentCode checkout 63baf6855efdd89b2834b74640f84b3bb0d86b50
uv venv --python 3.9 .\third_party\GarmentCode\.venv
& .\third_party\GarmentCode\.venv\Scripts\python.exe .\third_party\NvidiaWarp-GarmentCode\build_lib.py
uv pip install --python .\third_party\GarmentCode\.venv\Scripts\python.exe -r .\tools\garmentcode\actor_sim_requirements.txt -e .\third_party\NvidiaWarp-GarmentCode
Copy-Item .\third_party\GarmentCode\system.template.json .\third_party\GarmentCode\system.json
python .\tools\garmentcode\validate_garmentcode_actor_patch.py --garmentcode-root .\third_party\GarmentCode --require-sleeve-patch
```

补丁只让 GarmentCode 原生衣片读取 `actor_sleeve_connecting_width`、`actor_sleeve_cuff_circumference` 和 `actor_sleeve_length`；它不复制 demo 网格，也不修改生成后的衣服。

## 版型生成

必须使用 GarmentCode 自带 `.venv`，并同时传入 Actor 测量 JSON 和 Actor body YAML：

```powershell
& .\third_party\GarmentCode\.venv\Scripts\python.exe .\tools\garmentcode\generate_actor_specific_garmentcode_pattern.py `
  --garmentcode-root .\third_party\GarmentCode `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --measurements .\workspace\garmentcode_actor_native_measurements_v2\actor_v1_garmentcodedata_centered_measurements.json `
  --body .\workspace\garmentcode_actor_native_measurements_v2\neck_boundary_body_13p0.yaml `
  --design-template .\third_party\GarmentCode\assets\design_params\t-shirt.yaml `
  --output .\workspace\garmentcode_restart_actor_length_0p90_repro_v1 `
  --name garmentcode_restart_actor_length_0p90_repro_v1 --seed 1 `
  --shirt-width-ease 1.05 --shirt-length-factor 0.90
```

生成前后都必须看到 `ACTOR_NATIVE_GARMENTCODE_INPUTS_PASS`。任何官方 mean/demo body、neutral SMPL 或旧 sim OBJ 进入 manifest 都是立即失败，不允许“先看看效果”。

## 静态仿真

仿真入口把 Actor 测量 JSON 与 GarmentCode body YAML 分成两个参数，并在 BoxMesh 构建前核对 Actor、版型、body OBJ、body YAML、分区和 manifest 的绝对路径：

```powershell
& .\third_party\GarmentCode\.venv\Scripts\python.exe .\tools\garmentcode\run_actor_specific_garmentcode_sim.py `
  --garmentcode-root .\third_party\GarmentCode `
  --pattern-spec .\workspace\garmentcode_restart_actor_length_0p90_repro_v1\garmentcode_restart_actor_length_0p90_repro_v1_seed_1\garmentcode_restart_actor_length_0p90_repro_v1_seed_1_specification.json `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --actor-measurements .\workspace\garmentcode_actor_native_measurements_v2\actor_v1_garmentcodedata_centered_measurements.json `
  --body-measurements .\workspace\garmentcode_actor_native_measurements_v2\neck_boundary_body_13p0.yaml `
  --manifest .\workspace\garmentcode_restart_actor_length_0p90_repro_v1\garmentcode_restart_actor_length_0p90_repro_v1_seed_1\assetsstudio_candidate_manifest.json `
  --body-obj .\workspace\garmentcode_actor_native_measurements_v2\actor_torso_upperarm_surface_rest_partial_boundary_filled_v1.obj `
  --body-segmentation .\workspace\garmentcode_actor_native_measurements_v2\actor_torso_upperarm_surface_rest_source_v1_segmentation.json `
  --output .\workspace\garmentcode_restart_actor_length_0p90_repro_v1\simulation_100f_actor_locked `
  --max-sim-steps 100 --max-sim-time 240 --disable-frame-timeout
```

## Actor 转移与审查

先用 `export_garmentcode_panel_membership.py` 从同一版型和 sim OBJ 导出精确衣片成员关系，再运行 `transfer_garmentcode_sim_to_actor.py --panel-membership ...`。袖子必须保留 Actor 原生的躯干/锁骨/同侧手臂混合权重；不得仅按空间位置选择上臂并把其他权重丢弃。

审查顺序：静态正侧背四向、8 个走路采样帧的 Actor 穿透、GarmentCode 自相交、身体碰撞、最后完整四向 GIF。当前运动穿透计数为 `35,49,68,32,48,53,42,35`（均值 45.25，阈值为向 Actor 内 1cm）。

## 已排除路线

- `shirt_length_factor=0.86` 的自相交为 1257，高于 0.90 的 1184；下摆不是当前肩袖自相交主因。
- 整件衣服和碰撞体都没有穿反；仅袖口等局部折叠出现法线翻转。
- 纯空间分区权重转移会丢掉锁骨/脊柱混合，走路穿透均值约 961；精确 panel membership 和 Actor 原生混合权重把它降到 45.25。
- Actor 表面硬壳、重叠补袖、Shrinkwrap 和生成后网格修补不属于 GarmentCode 正式路线。
- 旧 v7、Route2、0.86、0.88 及 v18-v32 已永久从本地工作区清理；恢复只能依赖旧实验记录或重新生成。
