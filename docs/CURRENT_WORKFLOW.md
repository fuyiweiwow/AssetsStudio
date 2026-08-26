# 当前模块化美术资产工作流

## 目标

Studio 为多个游戏提供可复用美术资产。当前 `ba` 仅保留在 `consumer_tags`；生产对象不是完整角色，而是稳定 Actor Core 与可独立销毁/入库的 Slot 部件。

唯一生产顺序：

`StyleProfile → 风格种子 → 无部件 Actor Core 图像 → Hunyuan3D 形体 → 人工 AccuRIG → 动作库自动适配/变形 QA → 单个 Slot 部件 → Recipe/组合预览`

不得直接生成带头发、衣服和配件的完整 3D 角色。

## 阶段顺序

1. 定义 StyleProfile：比例、形状语言、材质响应、调色板和禁止项。
2. 生成多枚风格种子并做跨视图压力测试；前/侧/后必须是同一拓扑。
3. 从已批准种子生成模型无关的 `source/target/mask/caption/Gate` Pair。
4. 人工批准 Pair 后，使用 FLUX.2 Klein 4B Base 训练 `strip_to_actor_core` LoRA；训练可远程进行。
5. 在 FLUX.2 Klein 4B distilled FP8 上加载 LoRA，并在真实 RTX 3060 12GB 验证本地编辑。
6. 通过无部件、方向一致、头身比和轮廓 Gate 后，才能进入 Hunyuan3D-2MV。
7. 人工四方向审查单一封闭无纹理形体；候选只能销毁或加入本地 3D 资产库。
8. 对批准素体生成低风险绑定网格和落点预览，人工在 AccuRIG 标点并导出 FBX。
9. Studio 选择该 FBX，复制到 Actor 专属 intake，验证一对一来源并生成预览。
10. 从本地动作库选择动作，自动映射到当前 AccuRIG 骨骼并做四方向循环/关节变形检查。
11. 按 ActorSlotProfile 一次生成一个独立部件；候选只能销毁或进入本地资产库。
12. 通过 Slot 锚点、骨骼和 Recipe 组合，最终集成到 Studio 组合/导出界面。

## 模型与硬件决策

- 生产后端必须在 RTX 3060 12GB 离线推理；这是采用门槛，不是优化建议。
- 默认推理：Klein 4B distilled FP8；训练：Klein 4B Base LoRA。
- 远程教师或 Qwen 只可生成候选 Target，不是 Studio 必需依赖，也不能自动批准数据。
- 原始 Pair 是模型无关数据；DiffSynth/FLUX、Musubi/Qwen 或 SDXL 都只是导出适配器。
- 若 Klein LoRA 无法通过真实 3060 Gate，停止采用并回退 SDXL，不围绕更大显卡继续设计生产链。

详见 `docs/ACTOR_CORE_TRAINING.md` 与 `docs/ENVIRONMENT.md`。

## 当前检查点

- 当前 StyleProfile：`qstyle_anime_western_fantasy_no_face_v1`。
- 两枚已批准风格种子已作为可移植包发布；换机克隆后由 Studio 自动引入本地种子库。
- 旧 Actor `0ef398ca94d445f18226a8bf2a991c79` 只保留为 AccuRIG、动作映射和生命周期技术基线，不再是风格/形体权威。
- rule-based 素体、Klein/Qwen 零样本素体均已判定不能作为训练 Target 或资产。
- Qwen Q3/Q4 对照表明量化不是梨形躯干问题的主因；继续堆提示词的路线已停止。
- Klein distilled 限额预筛选可在约 11.7GB 增量显存生成 1536×768 三视图，但零样本仍保留部件，因此必须依靠任务 LoRA。
- 两组教师 Pair `teacher_actor_core_d70bce_20260826_v2` 与 `teacher_actor_core_74e7acc_20260826_v2` 已批准并导出为 DiffSynth 图像编辑数据；第二组使用双参考教师方法统一长发种子的布局与首枚 Target 的无耳几何规范。
- 第二轮 Klein Base rank-16/120-step LoRA 已从头训练并成功回载。Base 诊断证明任务已学会；distilled 4-step 在训练来源需 strength 2.0、未训练 BA 保留集需 strength 3.0 才去除可见耳朵。
- BA 保留集在 strength 3.0 仍有右侧脚部双轮廓，且真实 3060 尚未验证；因此 v2 只作为 Studio 本地评审候选，不是生产默认，也不能进入 3D 或资产库。
- 当前动作库只有 `mixamo_standard_walk_v1`；自动映射与四方向预览已实现。

## 下一步

1. 用户在 Studio/Tailscale 评审 v2 的两张训练来源 strength 2.0 结果与一张 BA 保留集 strength 3.0 结果，重点检查脚、手、轮廓和三视图一致性；
2. 增加至少两组不同外形来源与一个完全未参与训练的固定保留集，仍使用同一无耳 Target 规范，优先修复高 strength 下的脚部双轮廓；
3. 训练 v3 后执行固定 strength 阶梯 2.0 → 2.5 → 3.0，只允许人工选择通过六项 Gate 的最低强度；在泛化稳定前不做自动强度选择；
4. 在真实 RTX 3060 12GB 完成冷启动、4-step 编辑、保存恢复和峰值显存 Gate；若失败则启动 SDXL 回退，不提高硬件要求；
5. 图像质量与 3060 硬件均通过后，才将 LoRA/强度配置设为 Studio 默认并生成新的 Actor Core 候选，人工批准后进入 3D。
