# 本地资产生命周期

所有生成内容默认位于被 Git 忽略的 `workspace/`。

- `candidate`：等待自动 QA 与人工 Gate。
- `accepted`：复制到本地资产库，可作为后续生成的父资产。
- `destroyed` / `failed`：立即从候选与 Studio 列表移除，不保留失效副本。
- `blocked_by_parent`：父风格种子或 Actor 失效，禁止继续消费。

当前保留的本地生产资产只有：两枚已批准风格种子、当前 Actor 三视图、当前 Hunyuan 3D Actor、Actor Core rig/AccuRIG handoff。普通资产库不上传远程仓库。

两枚已批准风格种子是唯一例外：它们以小型可移植包发布在 `references/style_profiles/published_seeds/`，包含图片、数值 seed、生成合同、QA 指标和哈希。Studio API 启动时只会把本机缺失的发布种子复制到本地库，不覆盖已有本地资产。模型权重、普通候选、Actor、绑定结果和其他资产仍保持本地。
