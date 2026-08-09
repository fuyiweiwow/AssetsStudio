# AssetsStudio 开发时间线

本文件记录重要开发检查点。精确文件差异和提交时间以 Git 历史为准。

| 时间（Asia/Shanghai） | 类型 | 范围 | 事件 | 原因/结果 |
| --- | --- | --- | --- | --- |
| 2026-08-09 | migration | repository | 从 AssetsLab 白名单迁移并建立 AssetsStudio | 只保留当前里程碑、必要模型、重建脚本、Gallery 和工作流 |
| 2026-08-09 | milestone | shoes | Cartoon sneaker v10 晋级为 `accepted` | 用户确认外观相当不错，可作为鞋里程碑 |
| 2026-08-09 | governance | development | 建立开发原则、功能文档/ADR 模板、删除审计和产品技术讨论稿 | 防止上下文丢失、重复实验和正式分支持续膨胀 |
| 2026-08-09 | cleanup | pants docs | 修复短裤人工审查文档中的迁移前失效链接 | 确保正式审查入口只引用仓库内当前文件 |
| 2026-08-09 | requirements | product/storage | 明确 Actor 页面预览、生成追溯、本地优先存储和 BomboAdventure 资产孵化器目标 | 将“即时预览”拆为交互预览与 Blender 生成预览，并提出 ADR-0002 供确认 |
| 2026-08-09 | decision | product/storage | 用户确认两级预览、本地优先同步、发布包隔离和人形优先插件化 | ADR-0002 晋级为 `accepted`，建立 F001 功能文档 |
| 2026-08-09 | art direction | product/visual | 确立 Q 版日漫 JRPG 美术方向，以《零之使魔》和《闪之轨迹》作为抽象风格坐标 | 统一后续 Actor、发型、五官、服饰和 3 渲 2 审查语言；不复制具体受版权保护设计 |
| 2026-08-09 | audit | body/face | 用当前 Actor、Walk 动画和内嵌 3D 眼睛/耳朵完成四方向 3 渲 2 复现测试 | 证明五官工作流不依赖旧 `milestones/face/` 2D 测试资产，可以安全收敛为 Actor Face 合同 |
| 2026-08-09 | cleanup | hair/face | 统一男女发型源文件命名，移动耳朵提取来源，删除旧五官渲染和失效脚本 | 正式分支只保留当前 Actor 3 渲 2 所需组成部分；删除项仍可从 Git/AssetsLab 恢复 |
| 2026-08-09 | implementation | F001/studio | 建立 React + Three.js Studio 外壳、六类资产注册表、版本化 Schema 和可复现 Actor 组合 GLB 导出 | 首个页面已显示真实 Actor、Walk、短袖、短裤和鞋；发型因尚无已验证 Actor bundle 明确保持未装入状态 |
| 2026-08-09 | fix | F001/preview | 根据用户首轮审查修复 GLB 骨骼场景深拷贝、短裤近共面闪烁和离线启动误区 | 五官、衣物与鞋改为共享同一 GLTF 骨架；短裤增加仅限网页深度稳定；新增双击启动入口；用户决定将袖管模型缺陷延期到服装里程碑，F001 不做 workaround |
| 2026-08-09 | fix | face/F001 | 复查原项目眼睛历史并将误迁移的 `EyePackageV1` 替换为头部贴合 EyeAssembly 三态 | 保留身体/Walk v1，不覆盖基线；新增 Face v2 Blend、open/half/closed 纹理、重建/验证/四向眨眼脚本，Studio 恢复确定性眨眼 |
| 2026-08-09 | implementation | F002/workflow | 用模型→骨骼→动画→拼装→结果五步工作流替换无效左侧资产 Tab | 当前单模型/单骨骼/单动画如实显示；组件选择定位镜头；增加播放、暂停、停止、时间轴和直接拖动自由观察 |
| 2026-08-09 | implementation/fix | F003/workbench/preview | 将资产工作台与最终组合预览拆分，恢复发型目录与确定性配方入口，并把网页眼睛改为 Head Bone 蒙皮导出 | 八类工作流、单独/Actor 预览和正式组合控制台已建立；旧 GLB 眼睛无 Skin 的验证缺口已封堵，等待用户人工审查 |
| 2026-08-09 | fix | F001/launcher | 让双击启动器识别已运行的 AssetsStudio，并在无关程序占用端口时提前停止 | 修复重复双击导致 `Port 4173 is already in use`；避免失败前重复执行 Actor GLB 重建 |
| 2026-08-09 | implementation | F003/baseline/library | 新增 Actor 基准验收页、可放大 3D 工作区和本地静态缩略图资产仓库 | 把基本模型检查从参数工作流中分离；复用里程碑审查图让资产可快速辨认，并保持缓存可重建、不提交 Git |

## 记录规则

- 只记录产品、架构、正式里程碑、重大修复、方向变更和清理事件。
- 每条记录必须说明“为什么”，不能只有“做了什么”。
- 功能细节进入对应 `docs/features/*.md`；跨功能技术决定进入 ADR；删除进入 `docs/REMOVALS.md`。
