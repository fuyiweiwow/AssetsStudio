# AssetsStudio 删除与退休记录

本文件记录正式分支中被删除、未迁移或退休的内容。Git 历史仍是恢复文件的权威入口。

| 日期 | 对象 | 动作 | 原因 | 替代项 | 恢复位置 |
| --- | --- | --- | --- | --- | --- |
| 2026-08-09 | GarmentCode 裤子 v1-v47、短袖纸样及参数扫掠 | 未迁入 AssetsStudio | 未形成可接受 Actor 基线，且大量失败候选会误导后续流程 | Blender-native 短裤；Actor-native 短袖 | `AssetsLab` 的 `clothes_test` 分支及历史 |
| 2026-08-09 | Actor-derived/source-topology/compact-sleeve 等旧短袖候选 | 未迁入 AssetsStudio | 已被当前 v5 候选替代，继续保留会造成版本混淆 | `milestones/tops/actor_native_tshirt_v5/` | `AssetsLab` 工作树与历史 |
| 2026-08-09 | 鞋 v1-v9 与第一套高帮参考鞋 | 未迁入 AssetsStudio | v10 已得到人工认可，旧版本存在尺寸与穿模问题 | `milestones/shoes/cartoon_sneaker_v10/` | `AssetsLab` 工作树与历史 |
| 2026-08-09 | 重复 PNG 帧、第三方虚拟环境、模拟缓存 | 未迁入 AssetsStudio | 可再生成、体积大、与正式里程碑无关 | 当前工具脚本与 `workspace/` | `AssetsLab` 本地工作树；必要时重新生成 |
| 2026-08-09 | 短裤 `HUMAN_REVIEW.md` 中指向 `../clothes_native_control_v0_actor_eevee/` 的旧链接 | 删除过时引用 | 迁移后审查文件已与模型放在同一里程碑目录，旧路径全部失效 | 指向 `milestones/pants/native_control_v0/` 内现有 GIF、contact sheet 和报告 | Git 提交 `36721d0`；文件本体仍在当前里程碑目录 |
| 2026-08-09 | `milestones/face/`（316 个旧 2D 帧、眼睛装配测试和里程碑渲染文件，约 2.85 MB） | 从正式分支删除 | 内容来自已停止的 2D 直生成和五官实验，不能代表当前 Actor；继续保留会让 Gallery 和自动流程误选旧结果 | `milestones/body/face_contract_v1.json`、Actor 内嵌 3D 眼睛/耳朵、按需生成的 `workspace/` 审查输出 | 本次清理前 Git 历史；`AssetsLab` 历史工作树 |
| 2026-08-09 | 旧五官随机化、眼睛装配脚本及 `build_actor_derived_tshirt.py` | 从正式分支删除 | 依赖已退休的候选或把通用渲染辅助函数藏在旧短袖实验中，不符合当前单一工作流 | `tools/blender/actor_asset_render_utils.py`、`render_accurig_chibi_walk_test.py`、`process_actor_3to2_pixels.py`、`validate_actor_3to2_pixels.py` | 本次清理前 Git 历史；`AssetsLab` 历史工作树 |
| 2026-08-09 | 旧 ImageGen 男女风格图/步行图 | 不迁入正式分支 | 图像结构已经偏离当前 Actor，不能再作为几何或验收模板 | `docs/ART_DIRECTION.md` 保存抽象美术意图；F001 后从当前 Actor 生成新规范图并人工确认 | `AssetsLab` 历史与本机旧文件 |
| 2026-08-12 | 本地短袖 Route2、v7、0.86、0.88、v18-v32、中间权重转移与重复诊断网格 | 永久清理本地工作区 | 已被 0.90/native_weight_mix_v3 替代，旧结果和脚本反复造成版本回退；关键失败数据已压缩为 audit JSON | `workspace/garmentcode_restart_actor_length_0p90_repro_v1/`、`docs/WORKFLOW_TOPS.md` 和保留工具链 | 本次清理前本地试验；可按 Git 中工具重新生成，未提交的二进制缓存不可直接恢复 |
| 2026-08-13 | `milestones/tops/actor_native_tshirt_v5/` Actor 表面硬壳短袖 | 从正式分支删除 | 已被 Actor 参数驱动的 GarmentCode 0.90 基线替代；旧硬壳仍有右肩/右袖问题且不是最终几何路线 | `milestones/tops/garmentcode_short_sleeve_v1/` | Git 历史中的 `dc7674f` 及更早提交 |
| 2026-08-09 | `face_contract_v1.json` 与旧 `EyePackageV1` 预览合同 | 被 v2 取代 | 用户审查发现旧眼框/镜片叠层悬浮、遮挡且遗漏已经验证的眨眼流程 | `face_contract_v2.json`、`chibi_actor_eye_assembly_v2.blend` 和可复现眼睛脚本 | Git 历史；AssetsLab `origin/eye_anime` 历史 |
| 2026-08-09 | `studio/src/components/AssetRail.tsx` | 删除 | 只切换资产详情文字，不能表达模型→骨骼→动画→拼装→结果的工作流 | `WorkflowRail.tsx` 与 F002 五步装配流程 | Git 提交 `a2a5688` 之前的 F001 历史 |

## 新记录要求

删除或退休内容时，新增一行并写明日期、精确对象、删除原因、替代项和恢复位置；同时更新相关功能文档、索引与验证脚本。
