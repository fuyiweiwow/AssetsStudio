# Actor 专用 GarmentCode 短袖工作流

## 当前状态

当前唯一保留候选是 `milestones/tops/garmentcode_short_sleeve_v1/`。它由当前非标准 Actor 的 REST 测量、Actor 上半身碰撞代理和 GarmentCode 衣片生成；最终网格未做 Blender 缩放、Shrinkwrap、顶点外推或补洞。Blender 只负责坐标映射、Actor 原生骨骼权重转移和预览。

材质与几何分离：`materials/material_recipes.json` 只描述颜色、粗糙度、纹样和布料响应；它不能改变衣片、接缝、骨骼、碰撞或尺寸。Studio 的材质切换和 Blender 的 `--material-library/--material-recipe` 必须读取同一份 JSON。

人工四向动画审查已通过“外观可继续”门槛，但自动报告仍记录 1184 个 GarmentCode 自相交和 326 个碰撞弹簧，因此状态保持 `provisional`，不能进入 Gallery 或随机化。

## 已提交的唯一数据基线

| 用途 | 路径 | 约束 |
| --- | --- | --- |
| Actor | `milestones/body/chibi_actor_mixamo_walk_v1.blend` | 哈希必须与里程碑清单一致 |
| Actor 测量 | `milestones/tops/garmentcode_short_sleeve_v1/inputs/actor_measurements.json` | REST、厘米、完整 body/arms |
| GarmentCode body YAML | `milestones/tops/garmentcode_short_sleeve_v1/inputs/body_measurements.yaml` | 含 Actor 袖长、袖口周长和连接宽度 |
| 碰撞体 | `milestones/tops/garmentcode_short_sleeve_v1/inputs/collision_body.obj` | Actor REST 躯干和左右上臂 |
| 碰撞分区 | `milestones/tops/garmentcode_short_sleeve_v1/inputs/collision_segmentation.json` | 与碰撞体顶点顺序一致 |
| 设计参数 | `milestones/tops/garmentcode_short_sleeve_v1/pattern/design_params.yaml` | `shirt_length_factor=0.90`，seed 1 |
| GarmentCode 规格 | `milestones/tops/garmentcode_short_sleeve_v1/pattern/garment_specification.json` | 仿真的精确衣片和接缝输入 |
| 静态仿真 | `milestones/tops/garmentcode_short_sleeve_v1/simulation/garment_sim.obj` | 16340 顶点，附精确 panel membership |
| Actor 转移 | `milestones/tops/garmentcode_short_sleeve_v1/output/actor_transfer.blend` | 唯一正式预览 Blend |
| 固定动作审查候选 | `milestones/tops/garmentcode_short_sleeve_v1/output/actor_pose_corrective_v8_review.blend` | v8 宽泛落差诊断候选；保持 provisional，不进入 Gallery/随机化 |
| 审计和预览 | `milestones/tops/garmentcode_short_sleeve_v1/audit/`、`review/` | 保留最小可核验报告、四向 GIF 和接触表 |

`workspace/` 只用于可重新生成的缓存和试验结果，不是权威输入。里程碑中的所有必要数据资产均由 `manifest.json` 记录大小和 SHA-256；32 张单帧 PNG、随机织物贴图和重复缓存不影响几何重现，故不提交。

## 基线完整性验证

```powershell
python .\tools\validate_garmentcode_milestone.py `
  --manifest .\milestones\tops\garmentcode_short_sleeve_v1\manifest.json
```

验证器会检查全部清单文件的大小和 SHA-256、目录覆盖范围以及 Actor 源文件哈希。任何缺失、额外或被修改的数据都立即失败。

## GarmentCode 依赖

固定官方 GarmentCode 提交：`d449629979028123a5c4dc9e732a2ec19b7fce31`；固定 NvidiaWarp-GarmentCode 提交：`63baf6855efdd89b2834b74640f84b3bb0d86b50`。

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
python .\tools\garmentcode\validate_garmentcode_actor_patch.py --garmentcode-root .\third_party\GarmentCode
```

补丁只让 GarmentCode 原生衣片读取 `actor_sleeve_connecting_width`、`actor_sleeve_cuff_circumference` 和 `actor_sleeve_length`；它不复制 demo 网格，也不修改生成后的衣服。

## 版型重新生成

必须使用 GarmentCode 自带 `.venv`，并同时传入已提交的 Actor 测量 JSON 和 Actor body YAML：

```powershell
& .\third_party\GarmentCode\.venv\Scripts\python.exe .\tools\garmentcode\generate_actor_specific_garmentcode_pattern.py `
  --garmentcode-root .\third_party\GarmentCode `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --measurements .\milestones\tops\garmentcode_short_sleeve_v1\inputs\actor_measurements.json `
  --body .\milestones\tops\garmentcode_short_sleeve_v1\inputs\body_measurements.yaml `
  --design-template .\third_party\GarmentCode\assets\design_params\t-shirt.yaml `
  --output .\workspace\garmentcode_reproduction_v1 `
  --name garmentcode_reproduction_v1 --seed 1 `
  --shirt-width-ease 1.05 --shirt-length-factor 0.90
```

生成前后都必须看到 `ACTOR_NATIVE_GARMENTCODE_INPUTS_PASS`。任何官方 mean/demo body、neutral SMPL 或旧 sim OBJ 进入 manifest 都是立即失败。

## 静态仿真

先用 `--validate-only` 核对已提交输入契约；通过后移除该参数运行完整静态仿真：

```powershell
& .\third_party\GarmentCode\.venv\Scripts\python.exe .\tools\garmentcode\run_actor_specific_garmentcode_sim.py `
  --garmentcode-root .\third_party\GarmentCode `
  --pattern-spec .\milestones\tops\garmentcode_short_sleeve_v1\pattern\garment_specification.json `
  --actor .\milestones\body\chibi_actor_mixamo_walk_v1.blend `
  --actor-measurements .\milestones\tops\garmentcode_short_sleeve_v1\inputs\actor_measurements.json `
  --body-measurements .\milestones\tops\garmentcode_short_sleeve_v1\inputs\body_measurements.yaml `
  --manifest .\milestones\tops\garmentcode_short_sleeve_v1\pattern\candidate_manifest.json `
  --body-obj .\milestones\tops\garmentcode_short_sleeve_v1\inputs\collision_body.obj `
  --body-segmentation .\milestones\tops\garmentcode_short_sleeve_v1\inputs\collision_segmentation.json `
  --output .\workspace\garmentcode_reproduction_v1\simulation `
  --max-sim-steps 100 --max-sim-time 240 --disable-frame-timeout `
  --validate-only
```

## Actor 转移与审查

先用 `export_garmentcode_panel_membership.py` 从同一规格和 sim OBJ 导出精确衣片成员关系，再运行 `transfer_garmentcode_sim_to_actor.py --panel-membership ...`。袖子必须保留 Actor 原生的躯干/锁骨/同侧手臂混合权重；不得仅按空间位置选择上臂并丢弃其他权重。

审查顺序：静态正侧背四向、8 个走路采样帧的 Actor 穿透、GarmentCode 自相交、身体碰撞、最后完整四向 GIF。当前正式转移运动穿透计数为 `35,49,68,32,48,53,42,35`（均值 45.25，阈值为向 Actor 内 1cm）。v8 固定动作审查候选另记录普通视图 32、相机视图 75、衣料穿入峰值 179；它用于三渲二外观复核，不替换正式 GarmentCode 基线。

## 已排除路线

- `shirt_length_factor=0.86` 的自相交为 1257，高于 0.90 的 1184；下摆不是当前肩袖自相交主因。
- 整件衣服和碰撞体都没有穿反；仅袖口等局部折叠出现法线翻转。
- 纯空间分区权重转移会丢掉锁骨/脊柱混合，走路穿透均值约 961；精确 panel membership 和 Actor 原生混合权重把它降到 45.25。
- Actor 表面硬壳、重叠补袖、Shrinkwrap 和生成后网格修补不属于 GarmentCode 正式路线。
- 旧 v7、Route2、0.86、0.88、v18-v32 和 `actor_native_tshirt_v5` 不再是当前工作流；需要回看时只使用 Git 历史和实验记录。
