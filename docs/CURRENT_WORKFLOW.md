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
- v3 正式训练与 3-step 烟雾训练在当前 GPU 会话触发异常慢路径且没有 checkpoint，均已停止；当前有效权重仍只有 v2，Studio 生成服务已恢复。
- Studio 的 Actor Core 路由现强制选择已批准 StyleSeed，将种子真实像素作为 reference latent，并加载搜索到的 `strip_to_actor_core` LoRA；零样本 Actor Core 入口已移除。界面只允许按 2.0/2.5/3.0 阶梯选择强度，并记录到任务合同。
- 新男性种子作为未参与训练保留集时，v2 在 2.0、2.5、3.0 均失败：2.0 残留耳朵，2.5/3.0 虽去耳但仍生成梨形躯干和靴口式脚踝；三张均已从 Studio 删除，仅留在本地 rejected 诊断目录。这说明当前两 Pair 泛化不足，不能进入 3D。
- 2026-08-27 再次运行三 Pair/393,216 pixels/3-step 烟雾 Gate，仍复现约 15.9GB、SM 100%、约 62W、135 秒停留在 0/3 且无 checkpoint；已停止进程并恢复 ComfyUI。正式 v3 不得在主机重启前启动。
- 当前动作库只有 `mixamo_standard_walk_v1`；自动映射与四方向预览已实现。

## 下一步

1. 在方便断开远程会话时重启当前主机；重启后只运行仓库训练入口的三 Pair/3-step 烟雾 Gate，必须看到 `epoch-0.safetensors` 落盘；
2. 烟雾 Gate 通过后再从头训练三 Pair v3，并在两组训练来源、旧 BA 保留集和新男性种子上执行固定 2.0 → 2.5 → 3.0 阶梯；只允许人工选择通过六项 Gate 的最低强度；
3. 将当前整幅前轮廓 MAE 拆成比例/身体分区指标，避免把必须删除的头发和衣服宽度误当成形体漂移；在新指标完成前，原 MAE 只可否决明显失败，不可单独批准候选；
4. 若 v3 仍不能在新男性保留集上生成窄收束、无靴口的 Actor Core，再补一组男性 Source/批准 Target，而不是继续堆提示词；
5. 在真实 RTX 3060 12GB 完成冷启动、4-step 编辑、保存恢复和峰值显存 Gate；若失败则启动 SDXL 回退，不提高硬件要求；
6. 图像质量与 3060 硬件均通过后，才批准 Actor Core 并进入 Hunyuan3D。
