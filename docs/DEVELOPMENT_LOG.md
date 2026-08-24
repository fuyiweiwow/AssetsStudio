# AssetsStudio 开发时间线

本文件记录重要开发检查点。精确文件差异和提交时间以 Git 历史为准。

| 时间（Asia/Shanghai） | 类型 | 范围 | 事件 | 原因/结果 |
| --- | --- | --- | --- | --- |
| 2026-08-15 | decision/planning | clothing/workflows | 将服装开发从 DressCode/GarmentCode 单一路线改为三路线筛选：Seamly2D + Blender Cloth、Blender 原生版片缝合、免费基础网格拟合 | 当前 DressCode/GarmentCode 长袍候选未通过轮廓、Actor 穿着、碰撞和自碰撞门；先用统一斗篷目标验证可负担的离线主线，相关候选和验收记录写入 `docs/workflows/` |
| 2026-08-15 | decision/planning | F008/clothing | 将服装主路线从 GarmentCode 短袖扩展切换为本地 DressCode 参数化生成，首个目标为 Q 版日漫 JRPG 魔法师长袍与兜帽 | DressCode 负责版型/材质候选，AssetsStudio 负责 recipe、Actor 适配、四向动作审查和候选晋级；F006 保留为旧基线 |
| 2026-08-15 | implementation/validation | F008/clothing | 打通 DressCode canonical pattern → GarmentCode BoxMesh/Warp → Actor 蒙皮 → Blender 四向预览/GLB 的离线桥 | 证明格式、静态网格、定制 Warp、panel membership 和资产导出链路可运行；当前 Actor 烟雾仿真仍有 158 身体穿透与 1248 自交，候选保持 `review_required`，下一轮优先修正版型尺寸与空间布局 |
| 2026-08-09 | migration | repository | 从 AssetsLab 白名单迁移并建立 AssetsStudio | 只保留当前里程碑、必要模型、重建脚本、Gallery 和工作流 |
| 2026-08-09 | milestone | shoes | Cartoon sneaker v10 晋级为 `accepted` | 用户确认外观相当不错，可作为鞋里程碑 |
| 2026-08-09 | governance | development | 建立开发原则、功能文档/ADR 模板、删除审计和产品技术讨论稿 | 防止上下文丢失、重复实验和正式分支持续膨胀 |
| 2026-08-09 | cleanup | pants docs | 修复短裤人工审查文档中的迁移前失效链接 | 确保正式审查入口只引用仓库内当前文件 |
| 2026-08-09 | requirements | product/storage | 明确 Actor 页面预览、生成追溯、本地优先存储和 BomboAdventure 资产孵化器目标 | 将“即时预览”拆为交互预览与 Blender 生成预览，并提出 ADR-0002 供确认 |
| 2026-08-09 | decision | product/storage | 用户确认两级预览、本地优先同步、发布包隔离和人形优先插件化 | ADR-0002 晋级为 `accepted`，建立 F001 功能文档 |
| 2026-08-09 | art direction | product/visual | 确立 Q 版日漫 JRPG 美术方向，以《零之使魔》和《闪之轨迹》作为抽象风格坐标 | 统一后续 Actor、发型、五官、服饰和 3 渲 2 审查语言；不复制具体受版权保护设计 |
| 2026-08-09 | audit | body/face | 用当前 Actor、Walk 动画和内嵌 3D 眼睛/耳朵完成四方向 3 渲 2 复现测试 | 证明五官工作流不依赖旧 `milestones/face/` 2D 测试资产，可以安全收敛为 Actor Face 合同 |
| 2026-08-09 | cleanup | hair/face | 统一男女发型源文件命名，移动耳朵提取来源，删除旧五官渲染和失效脚本 | 正式分支只保留当前 Actor 3 渲 2 所需组成部分；删除项仍可从 Git/AssetsLab 恢复 |
| 2026-08-13 | milestone | tops | 将 Actor 专用 GarmentCode 0.90 短袖的输入、版型、仿真、转移 Blend、预览和审计纳入正式里程碑 | 其他机器克隆 main 后可校验完整哈希并从固定 Actor/GarmentCode/Warp 版本复现，不再依赖本机 workspace |
| 2026-08-09 | implementation | F001/studio | 建立 React + Three.js Studio 外壳、六类资产注册表、版本化 Schema 和可复现 Actor 组合 GLB 导出 | 首个页面已显示真实 Actor、Walk、短袖、短裤和鞋；发型因尚无已验证 Actor bundle 明确保持未装入状态 |
| 2026-08-09 | fix | F001/preview | 根据用户首轮审查修复 GLB 骨骼场景深拷贝、短裤近共面闪烁和离线启动误区 | 五官、衣物与鞋改为共享同一 GLTF 骨架；短裤增加仅限网页深度稳定；新增双击启动入口；用户决定将袖管模型缺陷延期到服装里程碑，F001 不做 workaround |
| 2026-08-09 | fix | face/F001 | 复查原项目眼睛历史并将误迁移的 `EyePackageV1` 替换为头部贴合 EyeAssembly 三态 | 保留身体/Walk v1，不覆盖基线；新增 Face v2 Blend、open/half/closed 纹理、重建/验证/四向眨眼脚本，Studio 恢复确定性眨眼 |
| 2026-08-09 | implementation | F002/workflow | 用模型→骨骼→动画→拼装→结果五步工作流替换无效左侧资产 Tab | 当前单模型/单骨骼/单动画如实显示；组件选择定位镜头；增加播放、暂停、停止、时间轴和直接拖动自由观察 |
| 2026-08-09 | implementation/fix | F003/workbench/preview | 将资产工作台与最终组合预览拆分，恢复发型目录与确定性配方入口，并把网页眼睛改为 Head Bone 蒙皮导出 | 八类工作流、单独/Actor 预览和正式组合控制台已建立；旧 GLB 眼睛无 Skin 的验证缺口已封堵，等待用户人工审查 |
| 2026-08-09 | fix | F001/launcher | 让双击启动器识别已运行的 AssetsStudio，并在无关程序占用端口时提前停止 | 修复重复双击导致 `Port 4173 is already in use`；避免失败前重复执行 Actor GLB 重建 |
| 2026-08-09 | implementation | F003/baseline/library | 新增 Actor 基准验收页、可放大 3D 工作区和本地静态缩略图资产仓库 | 把基本模型检查从参数工作流中分离；复用里程碑审查图让资产可快速辨认，并保持缓存可重建、不提交 Git |
| 2026-08-09 | implementation/fix | F004/hair | 按历史推荐 `seed_04_bangs04` 重建首套女性发型，绑定到 `CC_Base_Head` 并接入网页、缩略图和四方向 Walk GIF | 复用既有 Actor 贴合参数而不重新测量；修复 Bone Parent 导出造成发型落在脚边的问题，拒绝两个失败头皮补片；当前头顶中分小缝保留为人工审查项 |
| 2026-08-10 | quality/fix | F004/hair | 用前向表面覆盖检测定位并修复首套发型中心亮缝，生成 `seed_04_bangs04_v2` | v1 发片局部落到头皮后方而非左右断裂；v2 不加补片，仅平滑前移原网格，暴露采样从 105 降到 0，并改用 512px 浅色 Actor GIF 防止审查掩盖 |
| 2026-08-10 | implementation | F005/workbench | 资产仓库改为只显示当前左侧工作流类别，每个组件只缓存一张固定正面图；工作流预览可独立隐藏/显示 | 恢复左侧工作流选择的实际意义，避免四视图拼图和常驻 3D 画布挤占控制台空间 |
| 2026-08-13 | decision/planning | F007/hair | 在 `hair_test` 分支记录发型参数化、标准 under-cap 和分层随机化方案 | 现有组件变体已可复现，但仍缺少统一发套合同；先建立不破坏 F004 的阶段性开发入口，再扩展根部锁定和发型语法生成 |
| 2026-08-13 | implementation/validation | F007/hair | 完成 Phase 1 under-cap 生成器、Schema、验证器和四视图候选 | Actor 派生发套已生成并通过自动检查；候选未晋级，因前/侧发际线仍沿原面片边界呈锯齿状，Phase 2 需加入发际线 mask 与平滑裁切 |
| 2026-08-13 | implementation/preview | F007/Studio | 将 Phase 1 under-cap 候选导出为 Actor + Walk GLB，并在发型工作台增加正式 seed_04/under-cap 切换 | 每个阶段都必须能在 Studio 中由用户确认；候选独立于正式组合 GLB，保留 candidate 状态和已知锯齿发际线问题 |
| 2026-08-13 | fix/preview | F007/Studio | 修复候选 GLB 切换后旧发型残留、under-cap 显隐标签继承和默认展示模式 | 切换模型时强制重挂载 ActorPreview；沿祖先链识别 hair 组件；under-cap 默认使用单独展示，避免被 Actor 头部遮住 |
| 2026-08-13 | implementation/preview | F007/Studio | 建立发型/发套节点工作流试点并生成 seed_04 + under-cap 组合 GLB | 让“选择发型→选择发套→连接”成为真实可确认的 Studio 状态；两个 hair 节点共同绑定 Actor 头骨，组合候选仍保持 candidate，不自动进入随机池 |
| 2026-08-13 | quality/rejection | F007/hair | 检查 under-cap v2 的完整覆盖与自然度 | `rear_side_top` 会沿低模面片边界暴露缺口；连续椭球虽无锯齿，但在网页组合导出中未稳定承担补缝，故保留为失败证据，不晋级正式候选 |
| 2026-08-13 | implementation/validation | F007/hair | 建立 `seed04_scalp_base_v1` 专用 coverage layer 并接入 Studio 组合节点 | 专用 scalp base 已具备连续 Actor 表面、头骨绑定和组合预览；Studio 仍暴露前额大面积头部，明确说明外层 front_bangs 需要先修复，不能用 scalp base 掩盖大面积覆盖不足 |
| 2026-08-13 | implementation/preview | F007/hair | 将 seed_04 scalp base 拆为 Conservative / Coverage 两个可切换候选并接入 Studio | Conservative 前额回缩、优先保护刘海；Coverage 保留更宽覆盖用于对照；两套 Blender/GLB/manifest 和 Studio 组合均通过验证，下一步应修复外层 front_bangs 而不是继续扩大 scalp base |
| 2026-08-14 | diagnosis/implementation | F007/hair | 复核完整 Studio 取景后取消对 front_bangs 的错误修复，并将 scalp base 覆盖宽度/前缘回缩做成可逆 Studio 参数 | Blender 与完整 Studio 预览均确认刘海轮廓连续；参数 1.08 / 0.12 和重置流程已通过交互验证，外层发型不受影响，下一步可讨论哪些参数值得回写 Blender |
| 2026-08-14 | fix/preview | F007/hair | 修正 scalp base 前缘回缩的 Blender→Three.js 深度轴，并增加正面宽度/右侧回缩快捷检查 | 原实现把深度变化写到 Three.js 高度轴，状态变化但视觉不明显；修正为 -Z 后侧视可见，参数验收不再依赖错误的正面组合截图 |
| 2026-08-14 | validation/fix | F007/Studio | 将 scalp base 参数改为直接 position buffer 变形，增加命中网格、X/Z 跨度、Z 中心报告和单独检查高对比材质 | 复核确认宽度与回缩均作用于真实 GLB 网格；宽度 0.94→1.10 改变 X 跨度，回缩 0→0.16 改变 Z 中心，解决“数值变化但预览看不出”的验收歧义 |
| 2026-08-14 | metadata | repository | 将 `docs/ASSET_STATUS.json` 的来源快照更新为当前 AssetsStudio `main` 基线 | 修正迁移遗留的 AssetsLab `clothes_test` 来源，避免机器注册表误报资产来源 |
| 2026-08-24 | environment/validation | F009/F010 | 在远程机自动发现同级 ComfyUI，使用 ModelScope 逐文件重建 FLUX.2 Klein FP8、Qwen 3 4B 与 VAE，并完成真实三视图烟雾作业 | 移除活跃入口对旧机盘符和用户名的依赖；RTX 5070 Ti 上 1536×768 四步作业通过，下一阶段明确为 ReferenceLatent 风格稳定化 |
| 2026-08-24 | requirements/implementation | F010/F011 | 明确 AssetsStudio 是通用美术素材供给实验室，BA 只是近期消费者；建立带消费者标签的风格种子、素体/配件父子引用与候选入库/销毁合同 | 去除 Studio 全局 BA 风格绑定；本地库默认不上传，按 StyleProfile 隔离风格，压力测试后再决定是否训练 LoRA |
| 2026-08-24 | quality/correction | F011/style-seed | 用户复核发现旧种子正/侧长发、背面短发帽；撤销整条资产链批准并增加后端强制发型拓扑人工 Gate | 六组种子和两组下游素体复测后，只批准拓扑一致的短发/长发各一组；配件复测因混入人物和尺度漂移继续保持未批准 |
| 2026-08-24 | cleanup/validation | F011/3D intake | 从 Studio 本地库物理删除失效种子、素体和父链配件，并用批准短发素体完成首个 Hunyuan3D-2MV/Blender 四向 PoC | 库只剩 4 项 approved；本地 3D 候选为单连通 watertight 网格并保留 Q 版比例与短发拓扑，但仍是无纹理高模来源，未入库；Hunyuan 入口改为环境发现而非旧盘符默认值 |
| 2026-08-24 | implementation/decision | F011/Studio/texture | Studio 接入本地 3D 候选的真实 GLB 预览、四向图、强制人工 Gate、销毁/入库 API，并确定 12GB 显存纹理策略 | 3D 入库仍只代表 shape source；默认采用 Blender UV + 多视图颜色投影/烘焙，Hunyuan Paint low-vram 作为需单独验证的可选增强，避免把 16GB 级完整纹理链写成 3060 必需环境 |
| 2026-08-24 | quality/rejection | F011/texture | 两次隔离验证高模 AABB 四向顶点色直投，并在修正图片坐标原点后仍予以销毁 | 透明取样已大幅改善，但高模与 2D 无逐点对应，仍有前后串投、接缝和顶点膨胀；后续必须先重拓扑/UV，再做正交相机可见性烘焙与接缝修复 |
| 2026-08-24 | correction/validation | F011/Actor Core | 复核确认此前带头发、眼睛、训练服和鞋的“素体”实际是完整角色锚点；将其全部移出 Studio 活跃目录，并把 `base_actor` 收紧为 `canonical_actor_core` | StyleProfile 新增用途隔离的 `actor_core_contract`；完整角色风格图只记录谱系、不再作为 Actor ReferenceLatent。首个真正光头、无耳、无五官、无服装鞋饰品的 2D Actor `0ef398ca...` 已入本地库，其 Hunyuan 高模为 118,564 顶点、单连通、watertight，现作为 3D 候选等待远程人工审查，不进入 Gallery/随机池 |
| 2026-08-24 | validation/rig-prep | F011/Actor Core | 用户确认 `0ef398ca...` 四向形体并将高模 shape source 加入本地 3D 库；建立 Q 版归一化骨点 Profile、非破坏性 61,002 顶点绑定副本和 AccuRIG FBX 交接包，并接入 Studio 已批准资产卡片 | 绑定副本保持单连通/watertight/manifold，四向轮廓最差 IoU 0.999944，FBX 往返 Gate 全通过；它仍不是已绑定 Actor 或完整四边面重拓扑，下一步必须在 AccuRIG 人工确认落点并做基础动作变形 QA |
| 2026-08-24 | implementation/validation | F011/Studio/AccuRIG | 把人工 AccuRIG 回传实现为所选 Actor 卡片上的 FBX 上传、Actor 专属本地 intake、后台一对一审计、四权重运行副本与四向实际骨架预览 | 历史已绑定 Actor 成功通过完整处理烟雾测试，当前未绑定 FBX 被正确拒绝；Studio 不建立可跨 Actor 复用的骨骼库，真实 `0ef398ca...` 结果等待用户以后手工标定回传 |

## 记录规则

- 只记录产品、架构、正式里程碑、重大修复、方向变更和清理事件。
- 每条记录必须说明“为什么”，不能只有“做了什么”。
- 功能细节进入对应 `docs/features/*.md`；跨功能技术决定进入 ADR；删除进入 `docs/REMOVALS.md`。
