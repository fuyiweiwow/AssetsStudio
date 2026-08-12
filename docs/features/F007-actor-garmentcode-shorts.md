# F007 Actor 专用 GarmentCode 短裤

- 状态：in_progress
- 实验分支：`pants_workflow_test`
- 本地候选：`workspace/garmentcode_pants_actor_v1/candidate_width_1p05/`

## 目标

复用 F006 短袖的 Actor 原生工作流：只用当前 Actor REST 网格和骨架测量驱动 GarmentCode Pants，在 Actor 下半身闭合碰撞体上仿真，并把仿真网格直接转移到 Actor 骨架。Blender 不缩放、Shrinkwrap、外推或补改生成后的服装。

## 首轮结果

`pants_length=0.30`、`pants_width=1.05`、`pants_flare=1.0`、`pants_rise=1.0` 的候选生成了 4 个标准 Pants 衣片、16 条缝线和 8695 顶点的仿真网格。修正碰撞代理面序后，180 帧静态仿真得到身体碰撞 0、自相交 0，所有顶点在结束帧静止；上游仍因达到帧上限把静态平衡标记为失败，因此候选不能晋级。

四向动画显示完整裤腰、左右裤腿和裆部，但自动 Actor fit 报告仍在走路帧检测到大量身体/裤脚穿透与间隙。当前瓶颈已经从版型/静态仿真转移到“仿真网格 → Actor 骨盆/左右大腿混合权重”的动作变形合同。

## 已确认的输入事实

- Actor 腰部中心截面约 `182.72 cm`，臀部中心截面约 `164.33 cm`，左右大腿约 `88.37 cm`。
- 该 Q 版体型违反 GarmentCode Pants 的“腰围小于臀围”假设；当前版型兼容策略把腰围限制为臀围的 98%，并在 provenance 中显式记录，不能伪称为原始 Actor 腰围。
- Blender 到 GarmentCode 的 `(x,y,z) → (x,z,-y)` 是行列式为正的旋转，面序必须保持。反转面序会让碰撞代理法线朝内，并把短裤错误地吸进身体。

## 下一门槛

1. 在不修改仿真几何的前提下，建立裤腰、裆部共享边、左裤腿、右裤腿四区权重合同。
2. 用面内重心权重或 Actor REST/pose 对应表替代当前单次最近表面映射。
3. 重新运行 8 帧 Actor fit；只有动态穿透显著下降且四向 GIF 人工通过，才允许讨论替换 `native_control_v0`。
4. 在固定 Git checkout 可用时重跑一键脚本，消除本轮本机源码快照缺少 Git 元数据的可复现性限制。

详细命令和边界见 [`../WORKFLOW_PANTS.md`](../WORKFLOW_PANTS.md)。
