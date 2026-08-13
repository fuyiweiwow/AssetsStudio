# 西幻装备简报与参数化服装工作流

## 目标

把“一套西幻风格的矿工装备”拆成可编辑的 GUI 作业，而不是让一个模型直接输出一套不可追溯的成品。自然语言或离线语音转写只产生 `assetsstudio_equipment_brief_v1`；它必须经过资产目录、Actor 绑定和人工审查门槛。

当前已落地第一阶段：短袖上衣可以在 Studio 中切换材质配方、调整主色/粗糙度/程序纹样强度，并导出 Blender 渲染请求。材质配方不修改 GarmentCode 衣片、接缝、骨骼权重、碰撞体或尺寸。

## GUI 作业分层

| 作业 | 当前执行器 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 粗布/亚麻/羊毛/工会条纹 | Studio + Blender | ready | 复用当前 Actor 专用短袖几何 |
| 矿工头盔、护边、矿灯 | 离线程序化硬表面 | requires_asset | 需要头骨包络、挂点和独立验收，换材质不能替代 |
| 工具腰带、袋子、矿镐 | 离线程序化附件 | requires_asset | 需要骨骼挂点、碰撞层和装备组合合同 |
| 工作裤、矿工靴 | 参数化服装/附件 | requires_asset | 先复用材质 Schema，再建立各自几何资产 |
| 四向三渲二动画检查 | 人工审查 | gate | 所有自动生成结果都必须回到当前 Actor |

## 数据流

```text
语音转写/文本
  -> 本地简报编译器
  -> equipment-brief.json（风格标签、BOM、执行器、状态）
  -> GUI 逐项确认
  -> 材质配方即时预览 / 几何作业离线生成
  -> Blender 权威渲染
  -> Actor 四向动作、穿模、轮廓和三渲二验收
```

## 研究路线

- 语音：离线 Whisper 类模型只负责中文语音转写；转写文本进入简报编译器，不直接控制 Blender。
- 材质：Three.js 负责交互决策预览，Blender 节点负责权威渲染；两端共用 `materials/material_recipes.json`。
- 服装：GarmentCode 继续负责有接缝的衣片和 Actor 专用尺寸；版型参数改变后必须重新生成、静态仿真、转移和审查。
- 硬表面附件：先用 Blender Python/Geometry Nodes 的确定性参数生成头盔、腰带和工具，再接入 Actor 骨骼挂点；这些附件不应塞进 GarmentCode 短袖网格。
- 三渲二：最终材质需要另设轮廓宽度、色阶和高光规则；物理材质参数只服务于渲染输入，不能作为几何质量证明。

## 为什么可行

词表和规则先保证同一简报生成同一 BOM 和默认材质；离线语言模型以后只做标签补全或候选排序，不能直接写入几何。材质、几何、绑定和审查分开，也能避免把“新头盔”伪装成换色，或把 demo 身体参数重新带入 Actor 流程。

## 当前入口

- 材质库：`milestones/tops/garmentcode_short_sleeve_v1/materials/material_recipes.json`
- Studio 注册表：`python tools/build_studio_registry.py`
- Blender：`tools/blender/render_actor_clothing_eevee.py --material-library ... --material-recipe ...`
- 纯 Python 校验：`python tools/validate_garment_material_recipes.py --library ...`

## 资料依据

- [GarmentCode 官方实现](https://github.com/maria-korosteleva/GarmentCode)：参数化缝纫衣片和组件的主路线。
- [GarmentCode 论文](https://arxiv.org/abs/2306.03642)：支持以有意义的设计参数、身体测量和可互换组件构建设计空间。
- [GarmentCodeData](https://arxiv.org/abs/2405.17609)：可用于检查常见服装类别、测量和布料仿真的数据覆盖，不替代当前 Actor 的实测参数。
- [Blender Principled BSDF 文档](https://docs.blender.org/manual/en/3.1/render/shader_nodes/shader/principled.html)：材质节点参数的权威解释。
- [OpenAI Whisper](https://github.com/openai/whisper)：离线语音转写候选；只产生文本，不直接修改资产。

## 通过条件

材质切换可以进入 Studio 预览，但不会自动进入 Gallery 或随机化。新几何只有在当前 Actor 上完成静态、动作四向、碰撞/穿模和三渲二轮廓审查后，才可以改变资产状态。
