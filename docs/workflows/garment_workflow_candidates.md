# 离线服装生成工作流候选

更新时间：2026-08-15

本文件是候选路线总览；实际本机安装状态、每轮筛选结果和晋级规则见
[`garment_workflow_screening_v1.md`](garment_workflow_screening_v1.md)。

## 目标

为 `chibi_actor_mixamo_walk_v1.blend` 建立一套离线、可参数化、可导出并能通过简单行走验证的服装流程。

首个统一测试对象不是完整复杂法师套装，而是：

> 三片式斗篷长袍 + 两片式兜帽 + 简单手臂开口。

这个对象能验证长袍轮廓、版片缝合、Actor 拟合、骨骼绑定和动画稳定性。

## 候选路线

| 编号 | 路线 | 主要职责 | 成本 | 参数化 | 长袍适配 | 当前判断 |
|---|---|---|---|---|---|---|
| A | Seamly2D + Blender Cloth | 2D 版片、缝合、垂坠、导出 | 免费/开源 | 强 | 强 | 首选验证路线 |
| B | Blender Cloth + 开源缝合脚本 | 直接在 Blender 中制作版片并缝合 | 免费/开源 | 中 | 中高 | A 的轻量替代 |
| C | 基础长袍网格 + Elastic Clothing Fit + Armature | 现成网格拟合、权重、动画 | 免费/开源组件 | 中 | 取决于基础网格 | 最快的保底路线 |
| D | GarmentCode + Warp | 参数版片、盒网格、布料模拟 | 免费/开源 | 强 | 中低 | 保留为实验后端 |
| E | DressCode + GarmentCode | AI 版片预测、程序化转换 | 研究代码 | 不稳定 | 低 | 暂不作为生产路线 |

## 路线 A：Seamly2D + Blender Cloth

Seamly2D 用于制作带尺寸参数的二维版片；Blender 原生 Cloth 使用缝合弹簧、固定点和碰撞体完成三维缝合与垂坠；最后在 Blender 中进行骨骼绑定和动画验证。

- Seamly2D：<https://github.com/FashionFreedom/Seamly2D>
- Blender Cloth Sewing：<https://docs.blender.org/manual/en/latest/physics/cloth/settings/shape.html>
- 适合：斗篷、长袍、披风、宽松服装。
- 风险：版片导入和缝合边顶点数需要自动化处理。

## 路线 B：Blender Cloth + 开源缝合脚本

直接在 Blender 中生成或导入平面版片，使用缝合边和 Cloth 完成缝合。可参考 `blender_clothing_tools`，但它项目较旧，因此只作为脚本参考。

- 项目：<https://github.com/whyoh/blender_clothing_tools>
- 适合：快速验证一件斗篷是否能围绕 Actor 成形。
- 风险：参数化能力弱，部分边缘匹配需要我们自己自动生成。

## 路线 C：基础网格拟合

先获取一个结构正确的免费斗篷/长袍基础网格，再使用拟合工具将其调整到 Actor，随后转移骨骼权重。

- Elastic Clothing Fit：<https://github.com/VRC-Staples/Elastic-Clothing-Fit>
- Modeling-Cloth：<https://github.com/the3dadvantage/Modeling-Cloth>
- 适合：尽快得到可穿着的视觉结果。
- 风险：基础网格的授权、拓扑和兜帽/袖口质量不可控。

## 路线 D：GarmentCode + Warp

保留当前已完成的环境和脚本，但只用于比较版片生成结果，不再把它视为唯一服装生产后端。

当前已知问题：

- 镜像版片会产生退化三角形；
- 复杂长袍需要额外修补版片；
- Actor 身体碰撞和自碰撞仍未稳定解决；
- 模拟环境对 Warp 版本敏感。

## 统一筛选标准

每条路线都必须输出以下内容：

1. 斗篷前、侧、后预览；
2. Actor 静态姿势下的碰撞检查；
3. 至少 16 帧简单行走测试；
4. 衣长、下摆宽度、兜帽深度三个参数可修改；
5. Blender 文件和 GLB/FBX 导出；
6. 记录生成时间、失败原因和人工修正量。

## 初步决策规则

- 如果路线 A 能完成基础斗篷缝合和静态拟合，采用 A 作为主路线。
- 如果路线 A 的版片导入成本过高，采用路线 B，并由项目脚本自动生成版片和缝合边。
- 如果两者都无法快速稳定，采用路线 C 先完成视觉里程碑，再逐步替换为参数版片。
- 路线 D/E 只作为研究后端，不阻塞主流程。

## 当前方向变更

DressCode/GarmentCode 已证明可以跑通部分格式转换和离线桥接，但当前长袍候选在版型轮廓、Actor 穿着、身体碰撞和自碰撞上均未达到里程碑门槛。因此它们不再是生产主线；下一轮优先验证真实版片缝合路线 A/B，再以路线 C 作为可负担的视觉保底。
