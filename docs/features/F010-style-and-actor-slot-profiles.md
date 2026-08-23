# 功能：可复用风格与 Actor 槽位资产

## 目标

把风格和人物装配信息从提示词/散落报告提升为可版本化、可校验、可被 Studio 与本地生成后端共同消费的资产。

## 第一阶段：数据合同

已新增：

- `assetsstudio_style_profile_v1`：保存权威参考图及 SHA-256、头身比、造型语言、渲染语言、语义色板、正负提示词和 QA 规则；
- `assetsstudio_actor_slot_profile_v1`：保存 Actor 坐标系、测量值、骨骼/表面锚点、适配包络、推荐生成模式、碰撞策略和证据状态；
- 首个风格实例 `western_fantasy_qstyle_soft3d_v1`；
- 首个 Actor 实例 `default_adventurer_v2_slots_v1`，共 11 个槽位；
- 独立校验器 `tools/validate_style_slot_profiles.py`。

当前实例只固化已经存在的实验事实：

- Actor 高度 `1.990555m`，头部高度 `0.931863m`，实测 `2.136102` 头身；
- 坐标合同为 `+Z` 向上、`-Y` 朝前、`+X` 为角色左侧；
- `EarPair` 使用实测双表面锚点并标记 `reuse_only`；
- `waist_accessory` 使用已通过 Walk 的 `0.59 x 0.41 x 0.22m` 装配包络；
- 只有已有静态/动作证据的槽位标为 `validated`，其余保持 `measured_provisional`。

## 生产规则

1. 风格 Profile 的 required 权威图哈希变化时校验必须失败，禁止静默换图；
2. 配件任务只能引用一个明确的 StyleProfile 和 ActorSlotProfile；
3. 文生提示词只能补充主题，不能覆盖 Profile 的 immutable traits；
4. 槽位的生成方式必须遵守 `preferred_mode`：如耳朵复用、软服装参数化、腰包独立生成；
5. 所有结果保持人工审核 Gate，不能因为 Schema 通过而自动晋级 3D。
6. 独立配件不能直接使用人物身份图作 ReferenceLatent；槽位必须提供无人物的 `isolated_slot_authority`，否则后端拒绝任务。

## 后续阶段

- [x] Studio 通过独立生成注册表加载并展示 StyleProfile/ActorSlotProfile；
- [x] 配件生成表单强制选择风格、Actor 和可生成槽位；
- [x] 本地桥接把 Profile 编译到 FLUX.2 ReferenceLatent 提示词与任务记录；
- [x] 生成首个同风格腰包候选并接入自动一致性 Gate；失败结果禁止进入 Hunyuan3D。
- [ ] 改走“批准单图 → Hunyuan3D 单图建模 → 同一网格渲染三视图 → 槽位装配”验证。

## 校验

```powershell
python .\tools\validate_style_slot_profiles.py
```
