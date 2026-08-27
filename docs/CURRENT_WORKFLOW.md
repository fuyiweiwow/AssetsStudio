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
4. 人工批准 Pair 后，先用 FLUX.2 Klein 4B Base 做任务可学习性诊断；最终 LoRA 必须针对生产所用的 Klein 4B distilled 权重族原生训练，训练可远程进行。
5. 在 FLUX.2 Klein 4B distilled FP8 上加载同权重族 LoRA，并在真实 RTX 3060 12GB 验证本地编辑。
6. 通过无部件、方向一致、头身比和轮廓 Gate 后，才能进入 Hunyuan3D-2MV。
7. 人工四方向审查单一封闭无纹理形体；候选只能销毁或加入本地 3D 资产库。
8. 对批准素体生成低风险绑定网格和落点预览，人工在 AccuRIG 标点并导出 FBX。
9. Studio 选择该 FBX，复制到 Actor 专属 intake，验证一对一来源并生成预览。
10. 从本地动作库选择动作，自动映射到当前 AccuRIG 骨骼并做四方向循环/关节变形检查。
11. 按 ActorSlotProfile 一次生成一个独立部件；候选只能销毁或进入本地资产库。
12. 通过 Slot 锚点、骨骼和 Recipe 组合，最终集成到 Studio 组合/导出界面。

## 模型与硬件决策

- 生产后端必须在 RTX 3060 12GB 离线推理；这是采用门槛，不是优化建议。
- 默认推理：Klein 4B distilled FP8；生产 LoRA：Klein 4B distilled-native。Base 只做训练诊断，不再把 Base LoRA 直接迁移到 distilled。
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
- 训练几何现只有一个权威：`actor_core_male_canonical_v1`，SHA256 `6c68f26074a1ecdda00b00e372901cf3538b1448349de6f72ed556177b57d5e5`。任何 Source 的 Target 只能对该图逐面板等比缩放与平移，禁止为不同角色重新发明素体形状。
- 当前四个 approved Pair 覆盖男性短发、短发兜帽、披肩盔甲和长发 Source，并共享上述几何权威：`canonical_actor_core_male_20260827_v1`、`canonical_actor_core_bob_cowl_20260827_v1`、`canonical_actor_core_scout_cape_20260827_v1`、`canonical_actor_core_longhair_d70b_20260827_v1`。审计结果全部通过且 authority ID/SHA256 一致。
- v5 Base 使用四 Pair、589,824 pixels、rank 16、6 repeats、5 epochs，共 120 steps；epoch-4 SHA256 为 `1672F079545A3BCFAB26F5D4A19B05918DDE0BD028D0D82314E91F8620CB1624`。在未参与训练的长发 `74e7...` Source 上，Base 768×384/20-step 对照同时通过躯干 `0.5369` 与侧脚 `1.1932`，证明 canonical 数据已具备任务可学习性。
- 同一 v5 Base LoRA 直接加载到 distilled 的 strength 2.0/2.5/3.0 阶梯全部失败；最高强度仅把侧脚收至 `1.2000`，躯干仍为 `0.5542`。因此已确认 Base→distilled 权重族迁移不是可采用的生产链。
- 本机已有 Comfy scaled-FP8 distilled Transformer 已通过可审计工具转换成 DiffSynth BF16 训练键：169/169 tensor、80 个带记录 scale 的 FP8 融合源完成确定性反量化、未复制 Base 数值、未下载模型。4-step smoke 正常后完成 distilled-native rank-16/120-step 训练，约 8 分 33 秒；epoch-4 SHA256 为 `EC414439CECC5E23BA8B9D4A5FCF65DCCDE0634B4AF1555B4FA89DCDD16FEEFD`。
- distilled-native held-out 对照中，96-step/strength 2.5 是当前视觉最佳：头发、服装、五官、耳朵和身份内容已清除，严格 front/right/back 成立；躯干通过 `0.5395`，侧脚仍失败 `1.3415`。120-step 开始更强地改写侧视，继续堆 steps/strength 已停止。
- 所有自动失败任务均已通过 Studio 生命周期从活跃候选目录删除；最佳图只存在于本地只读评审目录，不进入 Gallery、随机池、资产库、3D 或 Git。
- Base 仅为训练诊断，不是 RTX 3060 生产依赖；生产硬门槛仍是 distilled FP8 在真实 3060 12GB 离线通过。
- 当前动作库只有 `mixamo_standard_walk_v1`；自动映射与四方向预览已实现。

## 下一步

1. 用户审阅 v5 Base 通过图、唯一 canonical Target 与 distilled-native 视觉最佳图；后者仍明确标记为脚部 Gate 失败，不在 Studio 活跃候选、不入库。
2. 下一轮只处理“小腿到小脚的连续收束”：保持同一 canonical 几何，评估脚部区域加权损失或确定性下肢训练裁片；不得放宽 `1.20` Gate，也不得新增另一套素体形状。
3. 固定 held-out Source/seed，对新权重只跑 96-step 邻域和最小强度阶梯；同时检查严格右侧视，避免以脚部指标换取视角坍缩。
4. 图像自动与人工 Gate 同时通过后，在真实 RTX 3060 12GB 完成冷启动、4-step 编辑、保存恢复和峰值显存 Gate。
5. 图像质量与 3060 硬件均通过后，才批准 Actor Core 并进入 Hunyuan3D；否则执行既定 SDXL 回退实验。
