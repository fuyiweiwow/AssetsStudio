# 架构决策记录（ADR）

ADR 用于记录影响多个功能、未来替换成本高或需要长期解释“为什么”的技术决定。功能内部的小选择留在功能文档中。

## 命名

使用 `NNNN-short-title.md`，编号只增不复用。新记录从 `docs/templates/ADR_TEMPLATE.md` 创建。

## 状态

- `proposed`：讨论中；
- `accepted`：当前生效；
- `superseded`：已被新 ADR 替代，必须链接新记录；
- `rejected`：讨论后未采用；
- `deprecated`：仍可能存在，但不应再新增使用。

## 当前记录

| ADR | 状态 | 决定 |
| --- | --- | --- |
| `0001-development-record-system.md` | `accepted` | 用功能文档、ADR、开发时间线、删除记录和 Git 共同构成追溯系统 |
| `0002-asset-lifecycle-sync-policy.md` | `accepted` | 生成资产默认本地，只有根源、里程碑和发布内容显式同步 |
| `0003-actor-native-garmentcode-authoring-contract.md` | `accepted` | 当前 Actor 参数和碰撞体驱动 GarmentCode，Blender 不替代最终几何 |
