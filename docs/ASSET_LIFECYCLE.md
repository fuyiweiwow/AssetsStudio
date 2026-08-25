# 本地资产生命周期

所有生成内容默认位于被 Git 忽略的 `workspace/`。

- `candidate`：等待自动 QA 与人工 Gate。
- `accepted`：复制到本地资产库，可作为后续生成的父资产。
- `destroyed` / `failed`：立即从候选与 Studio 列表移除，不保留失效副本。
- `blocked_by_parent`：父风格种子或 Actor 失效，禁止继续消费。

当前保留的本地生产资产只有：两枚已批准风格种子、当前 Actor 三视图、当前 Hunyuan 3D Actor、Actor Core rig/AccuRIG handoff。资产库不上传远程仓库。
