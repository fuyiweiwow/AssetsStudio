# 功能：发型参数化与标准发套

- 功能 ID：`F007`
- 状态：`in_progress`
- 分支：`hair_test`
- 建立时间：2026-08-13
- 关联里程碑：hair、body
- 关联功能：F004、F005

## 目标

在保留当前“Blender 权威生成、运行时使用已验收 bundle、人工四视图审查”边界的前提下，逐步建立适合 Q 版块状发束的参数化与随机化能力，并解决组件组合时的穿模和头皮暴露。

本功能不追求写实毛发模拟，也不把 Blender 作为游戏运行时依赖。第一阶段只建立可复现的 under-cap 合同和验证入口；后续再扩展组件根部锁定、轮廓区变形和发梢随机化。

## 结论与技术方向

### 类似 GarmentCode 的方案

目前没有一个成熟、开源且直接适合本项目 Q 版发束的“HairCode”。Blender Hair Curves/Geometry Nodes、Hair Tool 和 Medusa Nodes 可以作为曲线和程序化几何的底层工具，但最终仍应烘焙为项目自己的静态发型资产。

项目采用自建的“头部版型 + 发型语法”方向：标准头部表面作为发套基准，组件负责发束和轮廓，参数负责有限形变，生成结果经过 Blender 四视图和 Walk 审查后进入候选池。

### 组件参数化

现有组件变体生成器已支持宽度、深度、高度、taper、前后曲线、非对称和旋转。后续参数分为三个区域：

```text
root_zone       根部/发际线，锁定或只允许极小位移
silhouette_zone 外轮廓，可做体积、长度和方向变形
tip_zone        发梢，可做更明显的随机变化
```

推荐参数包括 `crown_height`、`hair_volume`、`side_length`、`back_length`、`bangs_sweep`、`part_offset`、`asymmetry`、`curl_amount` 和 `tip_spread`。随机化按完整发型 archetype 采样，而不是独立对所有参数做无约束随机。

默认策略继续采用约 80% 已验收完整发型、20% 受限组件变体。任何候选必须记录 seed、源对象、参数、Actor、生成器版本和审查状态。

## Under-cap 合同

每个完整发型 bundle 可包含一个与 Actor 头部同源的 `under_cap`。它不是网页遮罩，而是正式的 Blender 几何组件：

- 从当前 Actor 头部派生，不复制外部源文件头皮；
- 覆盖头顶、侧面和后脑的内部暴露区域；
- 发际线处按发型裁切，避免盖住额头和眼睛；
- 相对 Actor 表面保持一个很小的正向偏移；
- 使用深色发色或暗色头皮材质；
- 与发型一起绑定到 `CC_Base_Head`；
- 在四视图和 Walk 中作为正式几何体检查。

Under-cap 不能替代发片本身的正确贴合。它只负责组件层之间的小缝隙，不能用来掩盖大面积错位、后脑缺失或发片穿入头部。

## 穿模与暴露检测

后续验证器应至少报告：

- 头皮暴露采样数量和覆盖率；
- 发型进入头部碰撞包络的顶点比例；
- 发际线到 Actor 表面的最小距离；
- 耳朵、眼睛和后脑覆盖异常；
- 正、右、背、左四视图轮廓；
- Walk 中的漂浮或相对滑动。

根部修复优先使用局部法线推出或有限 shrinkwrap，不能对整个发型外轮廓做强制 shrinkwrap，以免压扁 Q 版体积。当前首套 `seed_04_bangs04_v2` 的中心缝仍采用局部真实网格修复，不引入未验证的补片。

## 阶段计划

### Phase 1：合同和可验证接口

- 固化本文档和 ADR/开发时间线记录；
- 定义 under-cap 的生成输入、输出 manifest 和绑定规则；
- 增加不影响 F004 默认路径的 under-cap 生成实验入口；
- 增加覆盖率、碰撞包络和四视图检查的报告字段。

### Phase 2：标准发套生成

- 从 Actor 头部稳定派生 under-cap；
- 支持按发型发际线 mask 裁切；
- 在女性和男性源上各生成一组候选；
- 对比无发套、发套和局部修复三种结果。

### Phase 3：组件区域参数化

- 为组件建立 root/silhouette/tip 区域标记；
- 锁定根部，放宽外轮廓和发梢变形；
- 将参数和 seed 写入 variant manifest；
- 批量生成候选并进入人工审查。

### Phase 4：发型语法生成器

- 按 archetype 组合标准发套、后发、侧发、刘海和附件；
- 使用 Geometry Nodes 或 Python 生成 Q 版发束，而非写实发丝；
- 烘焙为可复现的 Blender/GLB 候选；
- 只有人工验收后才加入正式随机池。

## 非目标

- 不在运行时动态运行 Blender；
- 不把第三方插件作为正式资产生成的不可替代依赖；
- 不用材质染色或网页遮挡掩盖几何错误；
- 不让 under-cap 替代发型四视图和 Walk 审查；
- 不自动把候选提升为 `accepted`。

## 当前阶段验收

- [x] 已确认现有随机化属于组件组合和有限几何变体；
- [x] 已确认 under-cap 应从 Actor 头部派生；
- [x] 已确认整发 shrinkwrap 不是默认方案；
- [x] Phase 1 under-cap manifest/schema；
- [x] Phase 1 自动验证入口；
- [x] Phase 1 候选已导出 Actor + Walk GLB，并登记到 Studio registry；
- [x] Studio 发型工作台可在正式 seed_04 与 Phase 1 under-cap 之间切换；
- [ ] 女性/男性 under-cap 候选人工审查。

## Phase 1 实际结果（2026-08-13）

已在 `hair_test` 分支生成 `workspace/cache/hair/under_cap_v1/` 候选。`rear_side_top` 配置生成 791 个顶点、732 个面，绑定 `CC_Base_Head`，并通过正/右/背/左渲染和自动 manifest 验证。四视图确认没有盖住眼睛，但前/侧发际线沿 Actor 原始面片边界呈锯齿状；该候选仅证明生成合同和绑定链路可行，不能作为正式美术资产。Phase 2 需要增加发际线 mask、裁切平滑和与具体发型 bundle 的联合审查。

候选随后导出为 `studio/public/generated/hair-candidates/under-cap-v1/actor-under-cap-v1.glb`，并通过 Actor 预览合同验证。Studio 发型工作台的 `CANDIDATE REVIEW` 区域可切换正式 `seed_04` 和 `Phase 1 under-cap`，两者均支持四视角、显隐、放大和 Walk 时间轴。候选缓存属于本地生成输出，不进入 Git，也不会替换正式组合 GLB。

切换规则：选择正式 `seed_04` 默认进入“Actor 搭配”；选择 under-cap 默认进入“单独展示”。Under-cap 是头皮内层，直接放在白色 Actor 头部下方时本来就会被遮住；需要检查它的形状时使用单独展示，需要检查遮挡关系时再切回 Actor 搭配。

## 工作流试点：发型 / 发套节点连接

Phase 1 已增加 Studio 节点编辑试点。当前节点关系为：

`Hair Style（seed_04）` + `Under-cap（Phase 1）` → `Hair Assembly` → `Studio Preview`

Studio 支持三种可确认状态：只看发型、只看发套、预览连接结果。连接结果使用单独生成的组合 GLB，两个 hair 节点均绑定到 `CC_Base_Head`，并在 manifest 中保留组件清单。后续参数（偏移、贴合距离、缩放、发际线修复）将挂在输入节点或组合节点上；本阶段不伪装成实时 Blender 几何编辑。

验收要求：每次节点选择都必须有可加载的 GLB、manifest 和状态提示；组合候选不能自动晋级正式随机池。

### seed_04 专用 scalp base v1 结果

已生成 `seed04_scalp_base_v1`：从 Actor 头部连续表面派生，使用 `CC_Base_Head` 单骨骼绑定，组合 GLB 和 Studio 节点均已验证。该层可以作为外层发束的暗色 coverage layer，但当前 Studio 组合仍暴露前额大面积 Actor 头部；这不是 scalp base 应该掩盖的问题，而是 seed_04 前发/发际线覆盖不足。下一步应修复外层 `front_bangs` 的形状和覆盖范围，再重新检查 scalp base 的小缝隙过渡。

### v2 回修结论（未通过）

本轮先尝试了 `full_upper_head` 连续发套，验证了 Actor 面片直接细分会产生网格状破面；随后建立 `seed04_scalp_base_v1`，改为从 Actor 连续表面派生的发型专用 coverage layer。组合测量显示其初始 `surface_offset=0.022` 仍太接近 Actor 头部，前视角会被白色头部遮住；因此下一轮将安全距离调至 `0.060`，保持在外层发束包络以内，再用组合状态下的四视图和 Walk 验收。

## 预览硬性规则

从 Phase 1 开始，每个 hair 开发阶段都必须同时提供：

1. Blender 候选 Blend、manifest 和自动验证；
2. Actor + Walk 的本地 GLB 预览；
3. Studio registry 中的候选记录；
4. Studio 发型工作台中的明确切换入口；
5. 候选状态、已知问题和人工确认边界。

没有 Studio 可确认的候选，不视为该阶段完成。

## 刘海与发套边界取舍：Conservative / Coverage

参考 Reallusion 的头皮 backdrop、Front/Bangs 分区和 Houdini 的 mask 思路，本阶段将同一套 seed_04 scalp base 生成成两个独立候选：

- Conservative：前额较低区域排除，优先保护刘海和脸部轮廓，作为默认 Studio 预览。
- Coverage：保留更宽的头顶/前侧区域，用于测量覆盖上限，不作为默认美术方案。

两者均使用 Actor 头部连续表面、CC_Base_Head 单骨骼绑定、四视图渲染和 Actor + Walk GLB。Studio 节点编辑器中的 variant 按钮会切换对应的独立 under-cap 与 assembly 资源。

本轮验收结论：Conservative 确实降低了前额覆盖，Coverage 明显压住前额；两者都暴露同一个外层 front_bangs 发际线锯齿问题。因此后续应修复刘海自身的根部形状/覆盖，而不是继续扩大 scalp base。优先级固定为：脸部可见性 > 刘海轮廓 > 发套覆盖率。

### 诊断修正与 Studio 参数化试点

随后用正式 first_bundle_v2 的 Blender 正面渲染和完整 Studio 放大预览复核，确认外层 seed_04 刘海轮廓本身是连续的；此前局部截图中的“额头大白块/锯齿”来自页面滚动导致的画布截断，以及单独查看 scalp base 时 Actor 头部仍可见。为避免错误修复源资产，本阶段不修改 front_bangs。

Studio 现已在 SCALP BASE 节点提供可逆参数：

- 覆盖宽度：只对 HairSeed04ScalpBase 做横向缩放；
- 前缘回缩：只沿头部 +Y 后移发套；
- 重置发套参数：恢复 1.00 / 0.04 默认值。

精确输入 1.08 / 0.12 已在 Studio 组合预览中验证，外层 HairBundle_Female_Seed04 不受影响。该参数化目前属于 Studio 预览试点，尚未回写 Blender 资产或进入正式随机池。

### 参数可见性诊断：坐标轴与观察视角

首次参数试点出现“数值变化但预览不明显”。复核后确认有两个原因：

1. Blender 的头部深度轴导出到 Three.js 后对应 Z，不是 Three.js 的 Y；前缘回缩已修正为沿 -Z 作用。
2. scalp base 是外层发型的内层，组合模式下本来会被外层发束遮挡；前缘回缩属于深度变化，正面不适合作为验收视角。

因此 Studio 增加了快捷检查入口：覆盖宽度自动进入“只看发套 + 正面”，前缘回缩自动进入“只看发套 + 右侧”。后续参数验收必须同时满足“参数状态变化”和“正确观察轴上的几何变化”，不能只看正面组合截图。
