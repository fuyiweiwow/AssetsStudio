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
- 一枚短发男性技术种子 `80b51207eb24482f8c96fbb93f1e9de0` 已由本机 FLUX.2 Klein distilled FP8（1536×768、4 steps、CFG 1、seed 20260830）生成并通过自动/人工三视图检查；它只在本地资产库，带 `ba` 消费标签，不是项目级硬约束，也没有调用托管生图。
- 旧 Actor `0ef398ca94d445f18226a8bf2a991c79` 只保留为 AccuRIG、动作映射和生命周期技术基线，不再是风格/形体权威。
- rule-based 素体、Klein/Qwen 零样本素体均已判定不能作为训练 Target 或资产。
- Qwen Q3/Q4 对照表明量化不是梨形躯干问题的主因；继续堆提示词的路线已停止。
- Klein distilled 限额预筛选可在约 11.7GB 增量显存生成 1536×768 三视图，但零样本仍保留部件，因此必须依靠任务 LoRA。
- 两组教师 Pair `teacher_actor_core_d70bce_20260826_v2` 与 `teacher_actor_core_74e7acc_20260826_v2` 已批准并导出为 DiffSynth 图像编辑数据；第二组使用双参考教师方法统一长发种子的布局与首枚 Target 的无耳几何规范。
- 第二轮 Klein Base rank-16/120-step LoRA 已从头训练并成功回载。Base 诊断证明任务已学会；distilled 4-step 在训练来源需 strength 2.0、未训练 BA 保留集需 strength 3.0 才去除可见耳朵。
- BA 保留集在 strength 3.0 仍有右侧脚部双轮廓，且真实 3060 尚未验证；因此 v2 只作为 Studio 本地评审候选，不是生产默认，也不能进入 3D 或资产库。
- 第三组短发/兜帽/披肩来源 Pair 已通过自动与人工 Gate；Source 仍是本地训练候选，不冒充已发布风格种子。Target 的面板偏移使用确定性整数平移工具对齐，没有重画或改变几何。
- Studio 的 Actor Core 路由现强制选择已批准 StyleSeed，将种子真实像素作为 reference latent，并加载搜索到的 `strip_to_actor_core` LoRA；零样本 Actor Core 入口已移除。界面只允许按 2.0/2.5/3.0 阶梯选择强度，并记录到任务合同。
- 新男性种子作为未参与训练保留集时，v2 在 2.0、2.5、3.0 均失败：2.0 残留耳朵，2.5/3.0 虽去耳但仍生成梨形躯干和靴口式脚踝；三张均已从 Studio 删除，仅留在本地 rejected 诊断目录。这说明当前两 Pair 泛化不足，不能进入 3D。
- 重启后确认异常根因不是 GPU/驱动：v3 数据缓存错误地内嵌了 `use_gradient_checkpointing=False`，训练命令无法覆盖，导致约 15.9GB 满占与极慢换页；历史 v2 cache 的同字段为 `True`，两步对照仅 8 秒。校正副本未改变任何 tensor、Source、Target 或文本条件，三步 Gate 约 12 秒完成。训练入口现会拒绝错误 cache。
- 三 Pair v3 已用校正后的 589,824-pixel cache、rank 16、180 steps 完成，约 12 分 45 秒；最终 SHA256 为 `A72C3B58163B046752A3A0E4F037C168F4244B51BDAACCCC75D56E97957BCC5C`。但新男性保留集的 2.0/2.5/3.0 仍未通过：2.0 有耳位凹痕，2.5/3.0 虽无耳但仍为圆腹和块状脚部，三张均已从 Studio 删除。
- 复核三张批准 Target 后确认 v3 正在忠实学习数据：其中两张 Target 本身就有圆腹/块状脚部，却被人工 Gate 错误标记为“窄收束、非梨形”。因此当前阻塞是 Target 与 Gate，不是继续增加 epoch 能解决的问题；v3 保留为诊断权重，不进入 3D。
- 当前动作库只有 `mixamo_standard_walk_v1`；自动映射与四方向预览已实现。

## 下一步

1. 用户先评审 v3 strength 2.5 的只读诊断图，确认我们对“圆腹和块状脚部仍不合格”的判断；它不在 Studio、不入库；
2. 把 Target Gate 改成可测量的躯干分区宽度/收束与脚踝连续性检查，并重新审计现有三 Pair；不合格 Pair 移入本地 rejected，不再参与 v4；
3. 以当前男性 StyleSeed 建立一组真正窄收束、无靴口的批准 Target；必要时教师只负责提出候选，仍由本地 Gate 和人工批准决定；
4. 用通过新 Gate 的 Pair 训练 v4，并在旧 BA 与男性种子两个固定保留集执行 2.0 → 2.5 → 3.0 阶梯；
5. 在真实 RTX 3060 12GB 完成冷启动、4-step 编辑、保存恢复和峰值显存 Gate；若失败则启动 SDXL 回退，不提高硬件要求；
6. 图像质量与 3060 硬件均通过后，才批准 Actor Core 并进入 Hunyuan3D。
