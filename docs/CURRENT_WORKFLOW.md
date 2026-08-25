# 当前模块化美术资产工作流

## 目标

Studio 为多个游戏提供可复用美术资产。当前 `ba` 仅保留在 `consumer_tags` 中。生产对象不是完整角色，而是一个稳定 Actor Core 与可独立管理的 Slot 部件集合。

## 唯一顺序

1. 定义 StyleProfile：比例、形状语言、材质响应、调色板和禁止项。
2. 生成多枚风格种子并做跨视图压力测试；头发前/侧/后必须描述同一拓扑。
3. 使用素体专用图像编辑模型，把批准种子转换为无身份 Actor Core。Actor 必须光头、无耳、无五官、无衣物、无鞋、无配件；优先使用配对编辑 LoRA，而不是仅靠通用模型提示词。
4. 使用同一编辑合同和结构控制生成 front/right/back 候选；通过去部件、方向一致性、头身比和轮廓 Gate 后，才允许进入 image-to-3D。
5. 使用 Hunyuan3D-2MV 生成单一、封闭、无纹理形体；人工四方向审查后才进入本地 3D 资产库。
6. 对批准素体生成低风险绑定网格和标定预览，人工在 AccuRIG 中标点并导出 FBX。
7. 在 Studio 选择该 FBX。系统复制到 Actor 专属 intake、验证一对一来源并生成四方向预览。
8. 从本地骨骼动画库选择动作，自动映射到当前 Actor 的 AccuRIG 骨骼，并通过四方向循环与关节变形检查。
9. 按 ActorSlotProfile 一次生成一个部件。候选只能销毁或进入本地资产库。
10. 通过 Slot 锚点、骨骼和配方组合；最终集成到 Studio 组合/导出界面。

## 当前检查点与下一步

- 当前 StyleProfile：`qstyle_anime_western_fantasy_no_face_v1`。
- 两枚已批准风格种子已发布为可移植包；换机克隆后由 Studio 自动引入本地种子库。
- 旧 Actor `0ef398ca94d445f18226a8bf2a991c79` 仅保留为 AccuRIG、动画映射和 Studio 生命周期的技术验证基线，不再作为风格或形体权威。
- 当前没有可批准的新标准 Actor。rule-based 参数化候选已判定失效并从 Studio 删除。
- 当前 ActorSlotProfile：`actor_core_0ef398ca_slots_v1`，所有锚点在 AccuRIG 人工确认前均为 `measured_provisional`。
- 当前可安全生成的首个独立 authority：`waist_accessory`。
- AccuRIG 导出已通过 Studio intake 和用户静态检查：101 bones、61,002 vertices、122,000 faces，运行时最多 4 influences。
- 当前动画库只有 `mixamo_standard_walk_v1`。自动映射覆盖 22 个核心骨，并检查骨骼覆盖、帧范围、四肢动作幅度、双手左右次序和背后交叉；当前 Gate 是用户检查修正后的四方向循环中的手腕、肘、肩、髋、膝、脚底与循环接缝。
- Qwen-Image-Edit-2511 Q3_K_M 的首轮固定基线已跑通。第一阶段稳定保留 front/right/back 和大头比例，并去掉头发、眼睛、鞋与腕带，但仍残留衣物和耳朵；第二阶段定向清理已得到无头发、无耳、无五官、无衣物的连续素体，但模型自动补出的躯干偏梨形/鼓肚，尚未通过 StyleProfile revision 2 的窄躯干轮廓 Gate，因此没有进入资产库。
- 第三阶段仅用提示词定向收窄躯干时，模型新增了胸部、肚脐、腹股沟线和臀沟，明确违反非性征连续素体合同；该候选同样不入库。这一失败已终止“继续堆叠提示词”的路线。
- 当前下一步是建立局部掩码和配对样本：以第二阶段的干净连续表面为基础，由无性征 Gate 约束躯干重建，并训练 `strip_to_actor_core` LoRA；前视归一化宽度曲线用于比较风格种子与输出。新素体批准后才创建全新的一对一 AccuRIG，随后再开始 `head_hair` 工作流。

不要直接生成带头发、衣服和配件的完整 3D 角色。这会破坏 Slot 生命周期、独立销毁/入库和跨项目复用。
