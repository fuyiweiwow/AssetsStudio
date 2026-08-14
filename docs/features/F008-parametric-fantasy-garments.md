# F008：面向 2D 输出的参数化幻想服装

- 功能 ID：`F008`
- 状态：`proposed`
- 分支：`feature/parametric-fantasy-garments`
- 建立时间：2026-08-14
- 关联里程碑：body、tops、pants、shoes
- 关联 ADR：ADR-0002、ADR-0003、ADR-0005

## 目标

在不依赖付费服装软件和人工高水平建模的前提下，通过 Studio 配方、GarmentCode、Blender Python/Geometry Nodes 和当前 Actor 验收链，生成具有西方幻想辨识度、适合最终 2D/像素化输出的低层数服装候选。

第一目标不是建立真实服装工业软件，而是验证“可复现参数 → 当前 Actor → 四向 Walk → 2D 轮廓审查”的闭环。

## 范围

- 以当前非标准 Actor 的测量、碰撞体和骨骼合同为唯一身体输入。
- 使用 GarmentCode 生成主体布料衣片，优先支持短袍/长袍、袖子和简单帽兜。
- 使用 Blender Python 或 Geometry Nodes 对已有基础组件做参数化轮廓调整、装饰和骨骼绑定。
- 在 Studio 中定义版本化服装 Recipe、参数范围、候选状态和审查入口。
- 输出 Blender 审查 Blend、四向静态图、Walk GIF、预览 GLB 和验证报告。
- ComfyUI/Stable Diffusion 仅作为可选的概念、配色、纹样和低分辨率视觉参考工具。

## 非目标

- 不依赖 CLO、Marvelous Designer、Style3D 等付费软件完成正式生产。
- 不把自然语言直接转换成正式服装几何。
- 不要求真实服装工业中的多层内衬、复杂布料厚度或完整物理碰撞。
- 不让 ComfyUI 生成的图像或网格直接成为游戏资产、骨骼真相或正式里程碑。
- 不在第一阶段实现任意服装的自动建模、任意体型适配或节点编辑器。
- 不为了消除全部自动碰撞警告而牺牲 2D 轮廓和动作可读性。

## 产品工作流

```text
Studio 选择服装 archetype
  -> 调整有限范围的轮廓/袖型/长度参数
  -> 生成版本化 Recipe
  -> Blender 无头执行 GarmentCode/组件生成
  -> Actor 权重转移与动作检查
  -> GLB + 四向 GIF + 报告
  -> 人工审查后保留、拒绝或晋级
```

ComfyUI 是旁路：可以由 Studio 导出参考请求或调用本地 API，但不阻塞上述主链。

## 第一实验：主体长袍轮廓参数化

第一步只验证一个主体服装，不同时引入帽兜、披风、肩甲和复杂装饰。

建议 archetype：`mage_robe_body_v1`。

候选参数先限制为：

- `length_factor`：衣长；
- `body_width_factor`：躯干宽度；
- `hem_flare`：下摆展开；
- `side_split`：侧开衩；
- `sleeve_length_factor`：袖长；
- `cuff_width_factor`：袖口宽度；
- `main_color`、`trim_color`：材质颜色。

第一实验成功条件：

1. 使用当前 Actor 测量、body YAML、collision body 和固定 GarmentCode 版本；
2. Recipe 可以确定性重建同一候选；
3. 输出服装仍使用 Actor 原生骨骼/混合权重合同；
4. 正、右、背、左静态视图和 Walk 中主体轮廓完整；
5. 64px/128px 参考输出中仍能辨认长袍和袖型；
6. 失败候选留在 `workspace/`，不进入 Gallery、随机池或 `milestones/`。

第一实验暂不要求：

- 服装物理审计达到零自相交；
- 复杂装饰几何；
- Studio 中实时修改 Blender 网格；
- ComfyUI 自动生成可绑定模型。

## 参数化实现策略

优先复用当前已有输入和脚本，不复制 demo/neutral body：

1. GarmentCode：主体衣片、接缝、静态平衡和基础碰撞；
2. Blender Python：确定性装配、坐标映射、Actor 原生权重转移、渲染和报告；
3. Geometry Nodes：已有基础组件的宽度、长度、展开度、边饰和简单重复装饰；
4. Studio：Recipe 表单、参数范围、作业状态和候选审查；
5. ComfyUI：设计参考和材质/纹样候选，不写入几何合同。

## 许可证策略

正式管线优先使用 Blender、GarmentCode、项目自有脚本和许可证清晰的模型/纹理。任何 ComfyUI checkpoint、LoRA、ControlNet、Embedding、自定义节点和参考素材都必须登记来源、许可证、商业使用限制和是否允许重新分发；未确认前只能用于本地研究，不进入正式资产包。

## 当前已有基础

- 当前 Actor V1、AccuRIG 骨骼和 Mixamo Walk；
- Actor 专用 GarmentCode 短袖的测量、body YAML、collision body、panel membership、静态仿真和权重转移链；
- Blender 无头渲染、四向 GIF、GLB 导出和验证脚本；
- Studio React/Three.js 预览、资产注册表、组件显隐和人工审查入口；
- 版本化 Schema、Recipe 占位和 `workspace/` 候选隔离规则；
- 当前材质 Recipe 可供主体服装颜色和粗糙度复用。

## 当前缺口

- 服装专用 `garment_recipe.v1` Schema 尚未建立；
- Studio 尚无服装生成作业桥和参数提交界面；
- 当前只有短袖 GarmentCode 模板，没有经过验证的长袍/宽袖 archetype；
- Blender 尚无可复用的服装轮廓组件库；
- 服装候选的自动 manifest、参数回放和 2D 尺寸审查尚未形成统一入口；
- ComfyUI 本地 API、模型许可证和输入输出合同尚未登记。

因此目前具备“开始第一实验”的基础，但还不具备“直接生产完整法师套装”的全部基础。

## 验收门槛

- 自动：Recipe Schema、输入来源、固定生成器版本、输出 manifest、Actor 绑定和文件完整性；
- 几何：静态平衡、碰撞、自相交和权重转移报告；
- 动作：正/右/背/左 Walk GIF；
- 视觉：当前 Actor 上的 3D 预览、低分辨率轮廓、颜色层次和风格一致性；
- 生命周期：候选默认只在 `workspace/`，人工通过后才允许进入正式目录。

## 实现状态

当前为设计记录和基础盘点，尚未生成法师服装候选。下一检查点应先建立 Recipe/Schema 和一个最小长袍 archetype，再决定是否值得增加 Studio 表单或 Geometry Nodes 组件。

## 变更记录

| 日期 | 变化 | 原因 |
| --- | --- | --- |
| 2026-08-14 | 建立 F008 设计 | 将“免费工具、2D 轮廓优先、参数化生产、ComfyUI 旁路”固化为可执行边界 |
## First experiment implementation update (2026-08-14)

The first executable recipe is now `mage_robe_body_v1_seed01`. It is driven by
`schemas/garment-recipe.v1.schema.json`, `recipes/mage_robe_body_v1.json`, and
`tools/garmentcode/generate_actor_specific_mage_robe.py`.

The tested construction is a GarmentCode `Shirt + SkirtCircle` composition. It
reads the current Actor measurements, derives only explicit style multipliers,
and emits a candidate manifest. This remains one visual robe for the 2D
pipeline, while avoiding the unstable overlong single-torso panel.

The paper-pattern stage, Actor-source guard, dependency pin guard, panel
topology guard, and BoxMesh generation pass. The full-resolution static probe
reaches cloth simulation and emits front/back renders and a simulation OBJ,
but the current CPU run crashes at frame 62. The low-resolution probe instead
reproduces a BoxMesh degenerate-triangle failure. Both results remain in
`workspace/` as diagnostic evidence; no candidate is promoted to Gallery,
randomization, or milestones.

The current Actor collision proxy has no lower-body vertex partition. The
generator therefore records an explicit temporary policy that labels skirt
panels against the available `body` collider. A dedicated lower-body proxy is
required before this policy can be considered production quality.
## Second experiment implementation update (2026-08-14)

`mage_robe_body_v2` now introduces the project-side `RobeBody` prototype. It
uses six low-flare lower panels, closes the ordinary 5 cm separate-garment gap,
and defines sleeve length as a fraction of the current Actor shoulder-to-wrist
measurement. Pattern generation and Actor/dependency guards pass. A ten-frame
simulation probe reaches cloth stepping and renders a longer-sleeve silhouette,
but it is only a visual probe and is not a static-equilibrium acceptance.
## Static simulation gate update (2026-08-14)

The v2 full-resolution probe passes BoxMesh creation, collision-part
initialization, and cloth stepping, but reaches only frame 47 before the
240-second CPU simulation limit. Its result is recorded as
`simulation_timeout`, not as a static-equilibrium pass. A 0.75 resolution
probe returns the known `right_btorso` degenerate-triangle error. The v2
candidate therefore remains outside Actor transfer, four-direction review,
Gallery, randomization, and milestones.
The extended 600-second probe reaches frame 99, but fails the physical gates
with 1,946 self-collisions and 72 body collisions. The next isolated variant
reduces lower-panel flare and introduces a small connection clearance; this is
intended to reduce physical overlap without changing the 2D robe silhouette.
The two-panel v3 probe reduces self-collisions to 1,545 and body collisions to
36, but still fails the 300/35 physical thresholds. This closes the first
GarmentCode-only tuning loop. For the project's 2D target, the next step is a
Blender-bound silhouette/render layer driven by the accepted recipe parameters;
it must remain clearly marked as a 2D prototype and cannot promote the
non-equilibrated simulation OBJ into a formal garment asset.
