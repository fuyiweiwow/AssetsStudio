# 从 AssetsLab 迁移到 AssetsStudio

## 来源

- 原仓库：`git@github.com:fuyiweiwow/AssetsLab.git`
- 整理时分支：`clothes_test`
- 整理时提交：`1745bcf`
- 整理日期：2026-08-09

AssetsLab 工作树在整理时包含大量未提交实验。迁移采取“只复制白名单”的方式，没有删除、移动、reset 或覆盖原仓库文件。

## 正式分支保留原则

只保留以下四种内容：

1. 用户明确认可的里程碑；
2. 当前最好但仍有明确缺陷的唯一候选；
3. 能从权威输入重建候选的最小脚本；
4. GIF、contact sheet、manifest、自动报告和人工审查记录。

模型文件不是外部占位符：当前流程使用的 Actor、动作、耳朵、发型、短袖、短裤、鞋以及鞋源 FBX 均迁入正式仓库。只有旧失败候选、未采用的外部衣服和第三方工具缓存被排除。

迁移后的第二轮清理进一步统一了源资产命名：男女发型进入 `milestones/hair/sources/<gender>/`，耳朵提取来源进入 `references/face/miku_chibi_source/`。当前眼睛和耳朵已经嵌入 Actor，不再维护一套平行的 `milestones/face/` 渲染资产；其可复现合同位于 `milestones/body/face_contract_v1.json`。

## 未迁入正式分支

- GarmentCode 裤子 v1-v47、短袖纸样/代理/袖窿参数扫掠；
- Actor-derived/source-topology/compact-sleeve 的重复失败版本；
- 鞋 v1-v9 与第一套不适配的高帮参考鞋；
- 已退休的眼窝、外部眼睛、下载耳朵候选；
- 已停止的 2D 五官帧、眼睛装配测试和重复里程碑渲染；
- 与当前 Actor 不一致的旧 ImageGen 男女风格/步行图（只将抽象方向转写到 `docs/ART_DIRECTION.md`）；
- `prototype/test_output` 中重复 32 帧 PNG 序列、第三方虚拟环境和模拟缓存。

这些内容仍可在本机 `E:\WorkProject\AssetsLab`、其 Git 分支/提交及原始实验记录中追溯。AssetsStudio 的正式分支不复制失败产物，以免后续自动化再次误选。

## 晋级纪律

任何里程碑替换都必须同时更新：

- `docs/ASSET_STATUS.json`
- `docs/MILESTONES.md`
- 对应 `docs/WORKFLOW_*.md`
- `gallery/index.html`
- 候选目录中的 `manifest.json` 与 `HUMAN_REVIEW.md`
