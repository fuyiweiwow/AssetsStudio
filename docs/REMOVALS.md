# AssetsStudio 删除与退休记录

本文件记录正式分支中被删除、未迁移或退休的内容。Git 历史仍是恢复文件的权威入口。

| 日期 | 对象 | 动作 | 原因 | 替代项 | 恢复位置 |
| --- | --- | --- | --- | --- | --- |
| 2026-08-09 | GarmentCode 裤子 v1-v47、短袖纸样及参数扫掠 | 未迁入 AssetsStudio | 未形成可接受 Actor 基线，且大量失败候选会误导后续流程 | Blender-native 短裤；Actor-native 短袖 | `AssetsLab` 的 `clothes_test` 分支及历史 |
| 2026-08-09 | Actor-derived/source-topology/compact-sleeve 等旧短袖候选 | 未迁入 AssetsStudio | 已被当前 v5 候选替代，继续保留会造成版本混淆 | `milestones/tops/actor_native_tshirt_v5/` | `AssetsLab` 工作树与历史 |
| 2026-08-09 | 鞋 v1-v9 与第一套高帮参考鞋 | 未迁入 AssetsStudio | v10 已得到人工认可，旧版本存在尺寸与穿模问题 | `milestones/shoes/cartoon_sneaker_v10/` | `AssetsLab` 工作树与历史 |
| 2026-08-09 | 重复 PNG 帧、第三方虚拟环境、模拟缓存 | 未迁入 AssetsStudio | 可再生成、体积大、与正式里程碑无关 | 当前工具脚本与 `workspace/` | `AssetsLab` 本地工作树；必要时重新生成 |
| 2026-08-09 | 短裤 `HUMAN_REVIEW.md` 中指向 `../clothes_native_control_v0_actor_eevee/` 的旧链接 | 删除过时引用 | 迁移后审查文件已与模型放在同一里程碑目录，旧路径全部失效 | 指向 `milestones/pants/native_control_v0/` 内现有 GIF、contact sheet 和报告 | Git 提交 `36721d0`；文件本体仍在当前里程碑目录 |

## 新记录要求

删除或退休内容时，新增一行并写明日期、精确对象、删除原因、替代项和恢复位置；同时更新相关功能文档、索引与验证脚本。
