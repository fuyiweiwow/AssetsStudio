# 功能：Studio 本地提示词三视图

- 功能 ID：`F009`
- 状态：`provisional`
- 负责人：Codex 与用户共同审查
- 建立时间：2026-08-23
- 最近更新：2026-08-23
- 关联功能：F001、F002、Actor V2 image-first rebuild

## 需求证据

用户要求把本轮本地 FLUX.2 三/四视图实验接入 AssetsStudio 页面，第一阶段先实现“输入提示词并生成三视图”，同时记录完整实验、环境和搭建流程。

## 本轮范围

- Studio 顶部新增“本地三视图”工作区。
- 用户输入角色/服装/比例提示词，选择软 3D 或干净 2D 风格并设置 seed。
- 本地桥接编译严格的正面/右侧/背面联合画布合同，并异步提交 ComfyUI FLUX.2 Klein 4B。
- 页面显示 ComfyUI/模型健康状态、任务阶段、原始联合图、实际编译提示词和可下载生成记录。
- 作业记录写入 `workspace/local_generation/turnarounds/<job-id>/`。
- 所有结果固定标记为 `visual_review_required`，不得自动送入 Hunyuan。

## 非目标

- 本轮不在页面上传参考图；ReferenceLatent 身份锁定留到第二阶段。
- 本轮不自动判断面板真实方向，也不自动重排。
- 本轮不执行 RGBA、Hunyuan3D、Blender、AccuRIG 或 Git 提交。
- 页面关闭或桥接重启后，不恢复内存中的历史任务列表；磁盘记录仍保留。

## 技术边界

浏览器只调用 `127.0.0.1` 的受限 HTTP API，不能提交模型路径、ComfyUI 节点图或任意命令。桥接只接受：

- `subject`：8–1000 字符；
- `style`：`soft_3d` / `clean_2d`；
- `seed`：非负整数。

扩散模型、文本编码器、VAE、尺寸、步数、CFG、输出目录和节点图都由后端固定。这样可以避免 Studio 页面成为任意本地执行入口。

## 验收条件

- [x] Studio 出现独立“本地三视图”入口。
- [x] ComfyUI 或模型离线时，页面明确显示原因并锁定生成按钮。
- [x] 在线时可提交异步任务并轮询 `queued/submitting/generating/completed/failed`。
- [x] 完成后可显示 PNG 并下载 JSON 记录。
- [x] TypeScript 类型检查、Vitest 和生产构建通过。
- [x] `python tools/validate_studio_local_generation.py --check-models` 通过。
- [x] 从 Studio 页面实际生成一张新三视图，完成状态轮询、PNG 回显和 JSON 下载入口验证。
- [ ] 用户确认页面交互与本轮角色输出可以进入下一阶段。
- [ ] 第二阶段加入批准正面锚点/ReferenceLatent、视角分类和注册 Gate。

## 变更记录

| 日期 | 变化 | 原因 | 验证/审查结果 |
| --- | --- | --- | --- |
| 2026-08-23 | 新增 Studio 工作区、本地桥接、Vite 代理和安全启动脚本 | 将已验证的 FLUX.2 本地实验变成可操作工作流 | 自动测试完成；等待用户从页面生成并审查新资产 |
| 2026-08-23 | 从页面提交作业 `8e45a403` | 证明页面不是静态 UI | 1536×768 PNG 与 record.json 回显成功；自动构图 Gate 通过，仍保留人工审查状态 |
