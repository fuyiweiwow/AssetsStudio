# 服装工作流筛选记录 v1

更新时间：2026-08-15

## 当前结论

暂不继续扩大 DressCode/GarmentCode 的复杂版片。先用同一个最小目标筛选三条离线路线：

> 三片式斗篷长袍 + 两片式兜帽 + 简单手臂开口

这不是最终魔法师套装，而是用来回答“版片能否围绕当前 Actor 成形、能否运动、能否导出”的技术门。

## 本机环境

| 组件 | 路径/状态 | 说明 |
|---|---|---|
| Blender | `E:\Env\Blender\blender.exe` | 已有，4.5.0；作为统一验证和导出端 |
| Actor | `milestones/body/chibi_actor_mixamo_walk_v1.blend` | 已有，含 Mixamo Walk |
| Seamly2D | `E:\Env\Seamly2D\seamly2d.exe` | 已下载并安装 v2026.8.10.212；尚未完成斗篷版片导入测试 |
| Elastic Clothing Fit | `E:\Env\Elastic-Clothing-Fit\src\Elastic-Clothing-Fit-main` | 已下载 GPL-3.0 源码；Blender 4.5 可导入包，尚未做实际拟合 |
| Modeling-Cloth | `E:\Env\Modeling-Cloth\src\Modeling-Cloth-master` | 已下载 MIT 源码；Blender 4.5 可导入模块，尚未做实际拟合 |
| GarmentCode + 自定义 Warp | 已有 | 仅保留为实验后端；之前的长袍结果未过质量门 |

## 筛选顺序

### A：Seamly2D + Blender Cloth Sewing

先确认 Seamly2D 能输出带尺寸变量的基础版片，再转换为 Blender 网格。缝合边使用 Blender Cloth 的 sewing springs；Blender 官方文档明确支持用额外的无面边连接斗篷需要拉拢的顶点。

### B：Blender 原生版片生成 + Cloth Sewing

如果 A 的安装或导入成本过高，就由项目脚本直接生成同一组 2D 版片、对应顶点和缝合边。这样不依赖外部版型 GUI，但保留真实的“版片→缝合→垂坠”链路。

### C：免费基础长袍网格 + 拟合/骨骼

最后再找授权明确的基础长袍网格，使用 Elastic Clothing Fit 或 Blender 辅助脚本拟合到 Actor，并做权重和行走测试。该路线用于快速得到可穿着结果，不把“现成模型能下载”当成“能穿到 Actor”。

## 统一验收门

每条路线都写入同一份结果记录，至少包括：

1. 前、侧、后服装单独预览，以及 Actor 穿着预览；
2. T-pose 或静态姿势无明显身体穿透；
3. 16 帧 Walk 无脱离、爆炸或大面积穿体；
4. 衣长、下摆宽度、兜帽深度三个参数至少各能修改一次；
5. 保存 Blender 源文件并导出 GLB/FBX；
6. 记录运行时间、失败原因和必须人工修正的步骤。

## 决策规则

- A 通过静态门和基础运动门：A 作为主路线，B 作为自动化加速层。
- A 的工具链导入成本过高，但 B 通过：B 作为主路线，保留 A 作为人工版型编辑入口。
- A/B 都无法在短时间内稳定穿着：C 先完成视觉里程碑，再逐步替换为参数版片。
- D（GarmentCode + Warp）和 E（DressCode + GarmentCode）不再阻塞项目主线，只记录可复用的参数和失败证据。

## 当前待测记录

| 路线 | 静态 | 16 帧 Walk | 参数 | 导出 | 状态 |
|---|---|---|---|---|---|
| A | — | — | — | — | 工具已安装；当前 CLI 导出被 `.locked` 状态阻塞，待 GUI/导入方案 |
| B | 技术通过；造型仍需修正 | 尚未单独验收 | 衣长/下摆/兜帽深度可调 | Blender/GLB 已导出 | 暂作为主实验路线 |
| C | 工具通过；视觉失败 | 尚未单独验收 | 由基础网格决定 | Blender/GLB 已导出 | 需要更好的基础长袍网格 |
| D | 失败证据已记录 | 未达标 | 部分可用 | 已有 | 实验后端 |
| E | 失败证据已记录 | 未达标 | 不稳定 | 部分可用 | 研究后端 |

## 路线 B 首轮结果

运行参数：基础版 `robe_length_factor=1.0`、`hem_width_factor=1.0`，改进版增加可调兜帽并运行 36 帧 Cloth。

- 通过：3 片网格生成、60 条 sewing spring、Actor 碰撞、Blender 保存和 GLB 导出。
- 未通过：当前结果是箱状罩体，顶部/侧面轮廓不自然，尚无兜帽；不能作为魔法师长袍候选。
- 预览：[route_b_cloth_sewing_body.png](../../milestones/robes/workflow_screening/route_b_smoke_v1/route_b_cloth_sewing_body.png)
- 源文件：[route_b_cloth_sewing_body.blend](../../milestones/robes/workflow_screening/route_b_smoke_v1/route_b_cloth_sewing_body.blend)
- 脚本：[build_cloth_sewing_smoke_test.py](../../tools/blender/build_cloth_sewing_smoke_test.py)

这个结果说明路线 B 值得继续做“版片质量和缝线拓扑”改进，但不能把 Blender Cloth 本身当作自动设计师；轮廓必须先由参数化版片定义。

改进版已将身体版片改为“肩部窄、下摆宽”的梯形版型，并加入左右两片兜帽；`robe_length_factor`、`hem_width_factor`、`hood_depth_factor` 三个参数均可重新生成。当前最新预览仍有肩部开口、兜帽像硬壳、袖子缺失等问题，因此只算 workflow smoke test，不算服装候选。

- 改进版预览：[route_b_smoke_v3/route_b_cloth_sewing_body.png](../../milestones/robes/workflow_screening/route_b_smoke_v3/route_b_cloth_sewing_body.png)
- 改进版源文件：[route_b_smoke_v3/route_b_cloth_sewing_body.blend](../../milestones/robes/workflow_screening/route_b_smoke_v3/route_b_cloth_sewing_body.blend)

## 路线 B 尺寸修正与路线 C 拟合结果

发现前几轮的袍体高度使用了错误的 Actor 坐标范围；v4 已按当前骨骼的肩部约 `z=1.4`、手腕约 `z=0.8` 修正比例，并加入 4 个袖片。结果表明主体长度落在正确高度，但袖片在 Cloth 松弛后塌入肩部，兜帽仍未形成可用开口。

随后用 Elastic Clothing Fit 对 v4 原型做了完整 Fit → Apply：工具链成功完成，但坏版片被拟合成分裂的平面罩体，说明 ECF 能做几何贴合，不能替代正确的长袍版型。

- v4 预览：[route_b_smoke_v4/route_b_cloth_sewing_body.png](../../milestones/robes/workflow_screening/route_b_smoke_v4/route_b_cloth_sewing_body.png)
- 路线 C 预览：[route_c_ecf_smoke_v1/route_c_ecf_fit.png](../../milestones/robes/workflow_screening/route_c_ecf_smoke_v1/route_c_ecf_fit.png)
- 路线 C 源文件：[route_c_ecf_smoke_v1/route_c_ecf_fit.blend](../../milestones/robes/workflow_screening/route_c_ecf_smoke_v1/route_c_ecf_fit.blend)
- 路线 C 脚本：[run_ecf_fit_smoke_test.py](../../tools/blender/run_ecf_fit_smoke_test.py)

## 路线 A/C 工具准备结果

- Seamly2D `v2026.8.10.212` 已安装到 `E:\Env\Seamly2D`，命令行版本检查通过；其官方仓库说明支持 Windows、Linux 和 macOS，并采用 GPLv3+。
- Seamly2D 的批量导出测试能启动并读取测量文件，但当前进程会留下 `.sm2d.locked`，随后停止在 `Pattern file ... was locked`；因此路线 A 目前只能记为“工具可启动、导出未通过”，不把它列为已验证链路。
- Elastic Clothing Fit 源码导入 Blender 4.5 通过，声明兼容 Blender 3.2+；它适合把“已有长袍网格”拟合到 Actor，但不能替代基础网格本身。
- Modeling-Cloth 源码导入 Blender 4.5 通过；它暂作为辅助脚本，不作为核心依赖。
- 已找到两个可继续核验的免费候选：BlendSwap 的 `Long Robe` 页面标注 CC-0，但下载需要登录；Meshy 的 `Mystic Patchwork Cloak` 页面标注 CC0，但当前页面没有暴露可直接归档的下载文件。两者都暂不作为本地输入，避免把网页展示当成已取得资产。
- 下一轮优先取得一个授权和文件都可追溯的基础披风/长袍；如果仍找不到，路线 C 只能作为工具保留，主线转向“预制 Actor-native 长袍模板 + 参数化变形”。
