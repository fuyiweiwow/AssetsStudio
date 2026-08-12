# ADR 0003：Actor 专用 GarmentCode 上衣契约

- 状态：accepted
- 日期：2026-08-12

## 决定

GarmentCode 上衣实验必须由当前 Actor 的 REST 测量、Actor body YAML 和 Actor 上半身碰撞体共同驱动。最终衣片、边界、缝合和静态几何必须由 GarmentCode 生成；Blender 只能做坐标转换、原生骨骼权重转移、渲染和只读审计。

禁止把官方 demo、mean/neutral body 或旧 sim OBJ 当作当前 Actor 的版型来源；禁止用 Shrinkwrap、全局缩放、表面外推、补洞或重叠袖管把诊断网格冒充最终 GarmentCode 几何。

## 原因

当前 Actor 不是标准人体比例。历史实验反复证明，demo 尺寸适配、表面硬壳和生成后修补会把袖窿、袖管、领口和躯干问题互相转移，无法证明流程对 Actor 本身有效。

## 验证

生成和仿真入口必须执行 Actor 输入 guard；GarmentCode 外部 checkout 必须通过固定提交和 Actor 字段补丁验证；候选必须依次通过静态平衡、碰撞、自相交、Actor 权重转移和四向运动人工审查。任一门槛未过时保持 `provisional`，不得进入 Gallery 或随机化。

完整命令和当前数据基线见 [`../WORKFLOW_TOPS.md`](../WORKFLOW_TOPS.md)。
