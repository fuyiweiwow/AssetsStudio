# 当前模块化美术资产工作流

## 目标

Studio 为多个游戏提供可复用美术资产。当前 `ba` 仅保留在 `consumer_tags` 中。生产对象不是完整角色，而是一个稳定 Actor Core 与可独立管理的 Slot 部件集合。

## 唯一顺序

1. 定义 StyleProfile：比例、形状语言、材质响应、调色板和禁止项。
2. 生成多枚风格种子并做跨视图压力测试；头发前/侧/后必须描述同一拓扑。
3. 从批准种子生成无身份 Actor Core 三视图。Actor 必须光头、无耳、无五官、无衣物、无鞋、无配件。
4. 使用 Hunyuan3D-2MV 生成单一、封闭、无纹理形体；人工四方向审查后才进入本地 3D 资产库。
5. 生成低风险绑定网格和标定预览，人工在 AccuRIG 中标点并导出 FBX。
6. 在 Studio 选择该 FBX。系统复制到 Actor 专属 intake、验证一对一来源并生成四方向预览。
7. 按 ActorSlotProfile 一次生成一个部件。候选只能销毁或进入本地资产库。
8. 通过 Slot 锚点、骨骼和配方组合；最终集成到 Studio 组合/导出界面。

## 当前检查点与下一步

- 当前 StyleProfile：`qstyle_anime_western_fantasy_no_face_v1`。
- 两枚已批准风格种子已发布为可移植包；换机克隆后由 Studio 自动引入本地种子库。
- 当前 Actor：`0ef398ca94d445f18226a8bf2a991c79`。
- 当前 ActorSlotProfile：`actor_core_0ef398ca_slots_v1`，所有锚点在 AccuRIG 人工确认前均为 `measured_provisional`。
- 当前可安全生成的首个独立 authority：`waist_accessory`。
- AccuRIG 导出已通过 Studio intake：101 bones、61,002 vertices、122,000 faces，运行时最多 4 influences；当前等待用户确认静态四方向预览。
- 用户确认后先做一组最小动作重定向与变形 QA，再开始 `head_hair` 的“在 Actor 上生成→隔离→四视图检查”工作流。

不要直接生成带头发、衣服和配件的完整 3D 角色。这会破坏 Slot 生命周期、独立销毁/入库和跨项目复用。
