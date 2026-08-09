# AssetsStudio 开发时间线

本文件记录重要开发检查点。精确文件差异和提交时间以 Git 历史为准。

| 时间（Asia/Shanghai） | 类型 | 范围 | 事件 | 原因/结果 |
| --- | --- | --- | --- | --- |
| 2026-08-09 | migration | repository | 从 AssetsLab 白名单迁移并建立 AssetsStudio | 只保留当前里程碑、必要模型、重建脚本、Gallery 和工作流 |
| 2026-08-09 | milestone | shoes | Cartoon sneaker v10 晋级为 `accepted` | 用户确认外观相当不错，可作为鞋里程碑 |
| 2026-08-09 | governance | development | 建立开发原则、功能文档/ADR 模板、删除审计和产品技术讨论稿 | 防止上下文丢失、重复实验和正式分支持续膨胀 |
| 2026-08-09 | cleanup | pants docs | 修复短裤人工审查文档中的迁移前失效链接 | 确保正式审查入口只引用仓库内当前文件 |

## 记录规则

- 只记录产品、架构、正式里程碑、重大修复、方向变更和清理事件。
- 每条记录必须说明“为什么”，不能只有“做了什么”。
- 功能细节进入对应 `docs/features/*.md`；跨功能技术决定进入 ADR；删除进入 `docs/REMOVALS.md`。
