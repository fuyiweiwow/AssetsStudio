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
- StyleProfile revision 3 已去掉与 Actor Core 冲突的 `boot-like feet`，明确要求小而圆、从小腿连续过渡的脚；靴口、鞋底、鞋跟块和脚尖块均为禁止项。
- 两枚已批准风格种子已作为可移植包发布；换机克隆后由 Studio 自动引入本地种子库。
- 一枚短发男性技术种子 `80b51207eb24482f8c96fbb93f1e9de0` 已由本机 FLUX.2 Klein distilled FP8（1536×768、4 steps、CFG 1、seed 20260830）生成并通过自动/人工三视图检查；它只在本地资产库，带 `ba` 消费标签，不是项目级硬约束，也没有调用托管生图。
- 旧 Actor `0ef398ca94d445f18226a8bf2a991c79` 只保留为 AccuRIG、动作映射和生命周期技术基线，不再是风格/形体权威。
- rule-based 素体、Klein/Qwen 零样本素体均已判定不能作为训练 Target 或资产。
- Qwen Q3/Q4 对照表明量化不是梨形躯干问题的主因；继续堆提示词的路线已停止。
- Klein distilled 限额预筛选可在约 11.7GB 增量显存生成 1536×768 三视图，但零样本仍保留部件，因此必须依靠任务 LoRA。
- Studio 的 Actor Core 路由现强制选择已批准 StyleSeed，将种子真实像素作为 reference latent，并加载搜索到的 `strip_to_actor_core` LoRA；零样本 Actor Core 入口已移除。界面只允许按 2.0/2.5/3.0 阶梯选择强度，并记录到任务合同。
- Actor Core 自动 Gate 现直接测量前视下躯干宽度与侧视脚/小腿投影：躯干比值必须 `<=0.54`，脚部检测比值必须 `>=0.80`，脚部投影比值必须 `<=1.20`。整幅 reference MAE 仅保留为诊断值，不再参与批准。
- 重新审计后三个旧 approved Target 全部失败，已移入本地 rejected，不再参加训练：两张躯干过宽，一张脚部投影过大。
- 两张新的教师 Target 已经确定性缩放/平移到 Source 的人物高度、中心和地面线，不做非均匀变形，并通过新自动 Gate 与人工 Gate：`teacher_actor_core_male_80b51207_20260827_v1`、`teacher_actor_core_bob_cowl_20260827_v2`。外部图像教师只提出 Target 候选，批准、训练和生产推理仍由本地流程决定。
- 两 Pair v4 使用正确的 gradient-checkpointing cache、589,824 pixels、rank 16、12 repeats、5 epochs，共 120 steps；2026-08-27 用时约 8 分 35 秒。epoch-4 SHA256 为 `15BB0CBC7BE0A0163D080E936FD8789CA96FFC81339A017F9C531D6EE715AE6E`，并已按相同哈希回载到 ComfyUI。
- v4 在旧长发保留集的 2.0/2.5/3.0 阶梯均未同时通过躯干与脚部 Gate；在男性训练来源上的同一阶梯也均失败。六个失败任务均已从 Studio 活跃候选删除并移入本地 rejected，不进入 3D 或资产库。
- Klein Base + v4 LoRA 的本地只读对照使用磁盘映射、FP8 暂存、BF16 计算，768×384/20 steps 用时 44.86 秒且没有下载。脚部 Gate 通过（0.8816），但躯干仍过宽（0.5577），并残留手指、胸腹和裆部解剖结构。因此当前主要阻塞是两 Pair/120 steps 尚未学会“连续无解剖细节壳”，不只是 Base→distilled 迁移或 LoRA strength。
- Base 仅为训练诊断，不是 RTX 3060 生产依赖；生产硬门槛仍是 distilled FP8 在真实 3060 12GB 离线通过。
- 当前动作库只有 `mixamo_standard_walk_v1`；自动映射与四方向预览已实现。

## 下一步

1. 用户先审阅 v4 distilled 最接近通过的保留集图与 Base 原生对照图；两张均为只读诊断，不在 Studio、不入库。
2. 补充至少 4–6 个通过新 Gate 的多样化 Pair，覆盖男女、长短发、披肩/盔甲/长靴等强遮挡 Source；Target 必须保持同一套窄收束、无解剖细节、连续圆脚权威。
3. 以固定训练源与固定保留集做 v5 小规模过拟合 Gate；先确认 Base 原生结果同时通过自动与人工 Gate，再做 distilled 2.0 → 2.5 → 3.0 阶梯。
4. 若 Base 在扩充数据后仍残留解剖细节，调整训练目标/步数而不是继续堆强度；若 Base 通过但 distilled 失败，才把问题归类为跨模型迁移并评估蒸馏原生训练或 SDXL 回退。
5. 图像 Gate 通过后，在真实 RTX 3060 12GB 完成冷启动、4-step 编辑、保存恢复和峰值显存 Gate。
6. 图像质量与 3060 硬件均通过后，才批准 Actor Core 并进入 Hunyuan3D。
