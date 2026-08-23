# 同风格独立配件与槽位工作流验证（2026-08-23）

## 目标

验证 `StyleProfile + ActorSlotProfile + FLUX.2 Klein ReferenceLatent` 是否能生成可直接进入 Hunyuan3D 的同风格独立腰包三视图。

固定合同：

- StyleProfile：`western_fantasy_qstyle_soft3d_v1`；
- ActorSlotProfile：`default_adventurer_v2_slots_v1`；
- slot：`waist_accessory`；
- 实测装配包络：`0.59 x 0.41 x 0.22m`；
- 画布：`1536x768`，front/right/back；
- FLUX.2 Klein 4B FP8，4 steps，CFG 1.0；
- RTX 3060 12GB 安全启动参数不变。

## 实验一：人物身份图作为 ReferenceLatent

Job：`845c73555200445588aac203de97010b`，seed `20260823`。

结果：风格、人物比例和材质高度接近权威角色，但模型复现了整个人物。正面腰包被放大到遮挡身体，侧面和背面仍包含 Actor，违反“配件单独输出”。该结果禁止进入 Hunyuan。

证据：`docs/workflows/assets/accessory_character_reference_failure_20260823.png`。

结论：人物身份图不能作为通用配件 ReferenceLatent。StyleProfile 必须区分“角色身份权威”和“无人物配件/材质权威”。

## 实验二：无人物单视图槽位参考

Job：`1d8eca8b7354469fa6d509a3b4316097`，seed `20260824`。

结果：成功去除人物，皮革、黄铜、圆润几何和软 3D 渲染语言一致；但右侧视图出现蓝色侧片与圆环，正/背结构不一致。自动 Gate：

- height CV `0.0842`，失败（要求 `<=0.05`）；
- ground range `0.0131`，通过；
- center max offset `0.0547`，通过；
- minimum color correlation `0.4875`，失败（要求 `>=0.55`）。

结论：单张无人物参考能锁风格，但无法给出可靠侧背结构。

## 实验三：无人物四视图槽位参考

Job：`e3b8ac5d01544db0b4a3e81198ce457e`，seed `20260825`。

结果：保持纯配件输出，正/右/背布局清晰；右侧和背面仍新增红、蓝、绿色结构，未保持同一物体。自动 Gate：

- height CV `0.0569`，失败；
- ground range `0.0052`，通过；
- center max offset `0.0488`，通过；
- minimum color correlation `0.3967`，失败；
- overall `automatic_pass=false`。

证据：

- `docs/workflows/assets/accessory_isolated_multiview_candidate_20260823.png`；
- `docs/workflows/assets/accessory_isolated_multiview_candidate_20260823.metrics.json`。

## 工作流决策

FLUX.2 已证明能够生成“同风格、无人物的独立配件概念图”，但单次联合三视图不能保证跨视角几何一致，暂时不能直接作为 Hunyuan3D-2MV 输入。

Studio 保留配件候选入口，同时新增以下硬 Gate：

1. 只有具备 `isolated_slot_authority` 的 `standalone` 槽位可提交；
2. 生成后自动计算三栏高度、落脚线、中心和色彩一致性；
3. 任一 Gate 失败即标记 `automatic_review_failed`，禁止晋级 3D；
4. `reuse_only` 的耳朵与 `parametric` 的服装不能走该入口。

下一条生产候选路线改为：

`StyleProfile -> 单张批准配件概念图 -> Hunyuan3D 单图形状 -> 从同一 3D 网格渲染 front/right/back -> ActorSlotProfile 自动缩放/挂点 -> Blender 动作 QA`

同一网格渲染出的多视图天然保持几何一致，能够绕开当前 2D 模型侧背漂移。它仍需验证 Hunyuan 单图生成的背面质量与槽位贴合，但风险边界比“直接生成伪三视图”清晰。
