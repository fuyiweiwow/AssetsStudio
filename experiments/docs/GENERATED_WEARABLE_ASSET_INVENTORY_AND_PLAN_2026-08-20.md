# 生成式 Actor / 穿戴资产清点与计划（2026-08-20，精简封存版）

## 当前决定

当前不接入 AssetsStudio。优先目标是让另一台 Windows 机器通过 Git + Git LFS 取得当前 V3 进度、验证同一场景与故障指标，并继续替换或重编译 Slot。

目标方向仍是：

`本地图像 AI 素体多视图 -> Hunyuan 素体 -> Actor 校准视图 -> 本地图像 AI 分 Slot 设计 -> Hunyuan3D-2MV 来源网格 -> ActorProfile / Slot Compiler -> 动作与四向 QA`

纹理、UV、最终材质与 Studio 接入继续延期。

## 1. 已完成的精简封存

Stage 10 权威目录：`experiments/generated_wearables/stage10_adventurer_set_v1/`。

- `REPRODUCIBLE_PACKAGE_V1.json` 封存 133 个必需文件；规范化文本与精确二进制合计 188,446,271 bytes（约 179.7 MiB）。
- 精简前正式包约 291.2 MiB；当前减少约 111.5 MiB，降幅约 38.3%。
- 当前只保留一个 Blend：`milestone/adventurer_set_workflow_v3.blend`。
- 七个活动 Slot 的 RGB、RGBA、Hunyuan GLB、脚本、ActorProfile、当前报告和预览均已进入正式包。
- 发型额外保留 Actor 头部校准图和穿戴后视图，保证 Actor-fit 图像链可追溯。
- Hunyuan 源码、Python 环境和 2MV 权重仍是外部依赖，不进入 Git。

已从当前工作树删除：

- V1、V2 两个历史 Blend；
- 未启用的 `head_hair_accessory` 头巾 GLB、输入图和参考图；
- 未被 V3 使用的 `feet_outer_workflow_v2` 候选链；
- V1/V2 预览、重复 turnaround 和被 V3 取代的审计快照；
- 可重建的临时帧缓存不进入正式包。

这些删除内容仍可从 Git 历史恢复，不再增加当前 checkout/LFS hydrate 的负担。

## 2. 当前权威资产

### Actor 与动画

- ActorClass：`ChibiActorV1`。
- Actor：`ChibiBaseMesh_AccuRIG_InputMesh`，16,296 顶点。
- 骨骼：`Armature`，ActorProfile 已解析 20 个动画语义骨骼。
- 动作：`Mixamo_Armature.001|mixamo.com|Layer0_on_Armature`，覆盖 1-71 帧。
- 审查帧：1、11、21、31、41、51、61、71。
- 审查方向：front、right、back、left。

### 七个活动 Hunyuan Slot

| Slot | 来源 GLB | V3 编译状态 |
| --- | --- | --- |
| `head_hair` | `adventurer_head_hair_actorfit_2mv_v2.glb` | Actor-fit 发型，刚性 Head 绑定 |
| `torso_outer` | `adventurer_torso_outer_2mv_v1.glb` | 上衣/短袖；袖管自相交 blocker |
| `waist_accessory` | `adventurer_waist_accessory_2mv_v1.glb` | 刚性 Waist 绑定，驱动可逆束腰 shape key |
| `legs_outer` | `adventurer_legs_outer_2mv_v1.glb` | 受控 pelvis/spine/thigh 权重 |
| `feet_outer` | `adventurer_feet_outer_2mv_v1.glb` | V3 实际来源；整鞋 Foot 刚性绑定 blocker |
| `wrist_accessory` | `adventurer_wrist_accessory_2mv_v1.glb` | 左右前臂绑定，手保持可见 |
| `back_accessory` | `adventurer_back_accessory_2mv_v1.glb` | Spine02 刚性绑定，按上衣背面锚定 |

V3 鞋源已通过场景报告核查：编译前为 263,900 顶点。后续 workflow-v2 鞋源为 262,966 顶点，未用于 V3，已排除。

## 3. 另一台机器现在能复现什么

安装 Git LFS 和 Blender 4.5.10 LTS 后运行：

`powershell -ExecutionPolicy Bypass -File experiments/generated_wearables/stage10_adventurer_set_v1/verify_reproducible_package_v1.ps1 -RebuildWaistSmoke`

该验证会：

1. 校验正式包全部 133 个文件的大小和 SHA-256；
2. 无界面打开 V3 Blend；
3. 检查 Actor、骨骼、动作、七个 Slot 和活动 Actor-fit 发型合同；
4. 重跑袖管/躯干自相交与鞋底接地诊断；
5. 从保留的腰带 GLB 重编译腰带和束腰 shape key，再运行腰部接口审计；
6. 把临时产物写入系统临时目录并在结束后删除。

本机验证结果：

- 包完整性：PASS；
- 场景结构：PASS；
- 腰带重编译：PASS；
- 袖管 blocker：16/16 side-frame tests 出现非相邻面穿插，最高 1,192 对；
- 鞋底 blocker：P95-P05 最大高差约 0.19695。

后两项是被准确复现的当前失败，不是验收通过。

## 4. 当前能力边界

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 从云端取得并继续 V3 | 可用 | Git LFS + 哈希 + Blender 结构审计已建立 |
| 七槽位根源图像封存 | 可用 | RGB/RGBA 均已正式保存 |
| Hunyuan3D-2MV 分 Slot 生成 | 可用但依赖外部模型 | 正式包保存输入与权威 GLB，不上传约 5GB 模型权重 |
| 在 V3 上替换/重编译 Slot | 部分可用 | 腰带已做烟雾测试；其他编译器保留但未在精简包中逐个重跑 |
| 从裸 Actor 一键重建完整 V3 | 尚未完成 | 早期装配链依赖历史候选，当前权威方式是从 V3 checkpoint 继续 |
| 任意 Actor 自动迁移 | 尚未完成 | 新 Actor 要重新 Profile、校准、生成和绑定；自动绑骨未解决 |
| 本地图像 AI | 缺失 | RTX 3060 候选已调研，尚未部署权重 |
| 纹理/UV/材质 | 延期 | 当前不处理 |
| AssetsStudio 接入 | 延期 | 保持独立仓库原状 |

## 5. 当前外部环境

- Blender：4.5.10 LTS。
- Hunyuan：官方 Hunyuan3D-2 源码目录，本机使用 Python 3.10.20。
- 模型：本机保留 Hunyuan3D-2.1 与 Hunyuan3D-2mv；2MV 主权重约 4.93GB。
- Git LFS：当前验证版本 3.7.1。
- ComfyUI：只有 SAM2 tiny，尚无 Qwen、Z-Image、SD3.5 或 FLUX 图片生成权重。

外部源码目录当前不是 Git checkout，因此不能提供可靠 commit id。精简包把生成后的 GLB 作为字节级权威资产；不同 CUDA、PyTorch 或 Hunyuan 环境重新生成时不承诺 GLB 字节完全一致。

## 6. 下一步计划

### Phase 1：修复当前两个硬 blocker

1. 为 `torso_outer` 建立 Actor 专用、不可见的低模变形笼与明确袖窿环；可见风格仍由 Hunyuan 网格提供。
2. 把袖窿附近权重改为连续过渡，以非相邻面自相交为门禁。
3. 将靴子划分为鞋口、鞋面、前掌、鞋底语义区域，使用 Foot/ToeBase 或辅助骨骼，而不是整鞋 Foot 刚性绑定。
4. 站立阶段增加足底锁定/IK 或动作接触修正，重新输出四向 GIF。

### Phase 2：补齐 clean-room 编译能力

1. 从 V3 中导出一个不含穿戴 Slot 的 canonical Actor 基线。
2. 建立按依赖顺序执行七个 Slot 编译器的统一入口。
3. 在临时目录从 Actor 基线重建完整套装，并与 V3 的对象合同和审计结果比较。
4. clean-room 重建通过后，V3 checkpoint 才不再是唯一启动点。

### Phase 3：本地图像 AI 与第二 Actor

1. RTX 3060 只部署一个首选图片模型做 640/768 多视图测试。
2. 先替换在线 ImageGen 的分 Slot 生成，不同时引入纹理和 Studio。
3. 选择第二个 Actor，重新生成 ActorProfile 和校准图；贴身资产不做统一缩放迁移。

只有以上阶段稳定后，才评估纹理和 AssetsStudio 接入。
