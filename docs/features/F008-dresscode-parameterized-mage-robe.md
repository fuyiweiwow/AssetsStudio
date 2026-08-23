# F008 DressCode 参数化魔法师长袍与兜帽

- 状态：`in_progress`
- 生成器：本地 DressCode SewingGPT + PBR material generator
- 环境：`E:\Env\DressCode`
- 源码：`third_party/DressCode`
- 第一目标：符合 AssetsStudio Q 版日漫 JRPG 风格的魔法师长袍与兜帽

## 方向变更

服装生成主路线从“为当前 Actor 手工维护单套 GarmentCode 短袖”切换为 DressCode 驱动的版型生成、参数变体和服装工作流。现有 F006 短袖仍保留为已生成资产和视觉回归参考，但暂停继续围绕它扩展服装类别。

DressCode 负责从文本/结构提示生成可编辑的缝纫版型和材质候选；AssetsStudio 负责参数配方、候选追溯、Actor 适配、Blender 权威预览、四向动作审查和里程碑晋级。DressCode 输出不能直接视为当前 Actor 的最终服装。

## 第一目标边界

首个候选不是某个已有作品角色的复刻，而是抽象的轻幻想法师长袍：

- 长袍主体，清晰的前中线和下摆层次；
- 长袖或宽袖，袖口在 256px 审查图中可辨认；
- 独立兜帽，能从正面、侧面和背面读出轮廓；
- 少量学院/法术感滚边、扣合或腰部收束；
- 明快主色、深色辅色和小面积魔法强调色；
- 不复制受版权保护的具体角色、纹章或服装设计。

## 参数合同 v1

每次生成必须由一个可序列化 recipe 驱动，结构以 [`schemas/assetsstudio_dresscode_garment_recipe_v1.json`](../../schemas/assetsstudio_dresscode_garment_recipe_v1.json) 为准，至少包含：

```json
{
  "schema": "assetsstudio_dresscode_garment_recipe_v1",
  "generator": "DressCode",
  "seed": 1,
  "style": "chibi_anime_jrpg_fantasy_mage",
  "components": ["robe_body", "sleeves", "hood"],
  "shape": {
    "robe_length": 0.0,
    "ease": 0.0,
    "sleeve_length": 0.0,
    "sleeve_width": 0.0,
    "hood_height": 0.0,
    "hood_depth": 0.0,
    "collar_opening": 0.0,
    "front_closure": "center",
    "hem_slit": 0.0
  },
  "appearance": {
    "primary_color": "",
    "secondary_color": "",
    "trim_color": "",
    "material": "wool_cloth",
    "pattern_strength": 0.0
  }
}
```

数值范围在首个可接受版型通过后冻结；在此之前不能把未经审查的随机值暴露为正式随机池。

## 开发阶段

1. 用 DressCode 预训练 SewingGPT 生成 dress/jacket-hood 起始版型，记录文本提示、模型版本和输出。
2. 建立长袍主体、袖子、兜帽的 panel/stitch 结构检查，淘汰断片、非闭合或无法仿真的候选。
3. 为长度、松量、袖型、兜帽高度/深度、领口和滚边建立受限参数化变体。
4. 通过本地仿真或后续 Blender/布料适配作业检查当前 Actor 的贴合与动作表现。
5. 生成 GLB、正/侧/背/左四向静帧和 Walk GIF，完成三渲二人工审查。
6. 将通过的 recipe、版型、材质、输出哈希和审查状态登记为服装候选；通过后才进入 Studio 资产库和随机池。

## 当前执行记录

首个固定 seed `17081501` 已离线生成 9-panel/18-stitch sewing pattern，并通过 panel/stitch 完整性检查。基于该候选已完成 `robe_length_cm=-15/0/+15` 的 seam-coupled 参数变体；袖口宽度和兜帽深度的直接自由边变体已被 seam 误差回归拒绝，当前仍处于 `candidate`，因为袖长、袖宽、兜帽高度/深度、Actor 适配和仿真尚未完成。

当前已生成 canonical seam contract，记录 panel 角色、共享 seam 顶点和参数所有权；后续袖宽/兜帽参数必须基于耦合 edge group 或重新设计的 canonical template 实现。

已完成第一版 canonical template：新增独立袖口与兜帽扩展 panel 后，`robe_length_cm`、`sleeve_width_cm`、`hood_depth_cm` 代表性变体通过 seam 回归。该模板仍需经过 3D 仿真和当前 Actor 适配，才能从 `candidate` 晋级。

当前已用本地 Blender 4.5 导出平面 pattern `.blend/.glb` 检查资产；下一阶段是把 canonical panel 转入布料/Actor 适配，不把该平面导出误认为最终服装模型。

已完成下一阶段的技术链路接入：`tools/garmentcode/run_dresscode_pattern_bridge.py` 已将 canonical pattern 送入 GarmentCode `BoxMesh`，并使用 `E:\Env\NvidiaWarp-GarmentCode` 的官方定制 Warp 完成 Actor REST 碰撞体烟雾仿真。静态网格、panel membership、Blender 蒙皮转移、四向预览和 GLB 导出均已跑通。

本次 Actor 烟雾仿真在 2 cm 网格分辨率下第 11 帧达到静态，身体穿透为 `158`、布料自交为 `1248`；因此仍明确标记为 `review_required`。当前预览显示版型在 Actor 上过小且轮廓呈片状/交叉，下一轮工作重点是重新校准 DressCode canonical pattern 的尺寸、初始 panel 空间布局和袖/兜帽角色映射，而不是把该结果加入资产库。

已补充独立服装四向预览（不显示 Actor）：`milestones/robes/mage_suit_v1/garmentcode_bridge/canonical_template_v1_actor_frame80_smoke/render_garment_only/`。该预览确认当前版型自身更接近短袍/外套，兜帽轮廓不可辨识，因此下一轮应优先修复版片结构和兜帽连接。

复核后确认 v1 的 hood 角色判断不成立：原始 `panel_3/panel_5` 与身体/肩部接缝混合，不能仅靠外扩 panel 变成兜帽。已重新生成本地 `hooded jacket with attached hood` 候选，并用其同名 `panel_3/panel_5` 替换得到 `canonical_template_v2_hooded.json`；v2 的 2D panel 预览具备五边形 hood 和中心接缝。可是 v2 的 boxmesh 在 Actor 上仍被大量遮挡，说明当前主要阻塞已转为 DressCode 3D placement/深度坐标与 Actor body proxy 不匹配，而非单纯 Warp 动力学。

因此路线已调整为 Actor-first：新增 `tools/garmentcode/generate_actor_mage_robe_pattern.py`，
从 Actor REST 测量值生成确定性的主体、袖子和兜帽候选，DressCode 降级为结构/风格
候选器。Actor-first v4 已生成 8-panel、15236-face 的基础长袍，主体高度约
`0.08..2.10 m`，能覆盖当前 Actor 躯干；Warp 11 帧达到静态，身体交叉 238、自交
195。袖筒和兜帽仍需结构修复，当前状态仍为 `candidate/review_required`。

针对“兜帽没有考虑 Actor 真实头部大小”的反馈，已用 `CC_Base_Head` 顶点权重从当前
Actor 测得头部包围尺寸约为 `86.35 x 84.53 x 89.21 cm`（宽、深、高）。新增
`tools/blender/measure_actor_head.py` 和 Actor-scaled hood 运行时组件，将颈口接缝
宽度与头部容纳宽度分离。v5 的静态 BoxMesh 已通过，但 12 帧 Warp 尚未达到静态平衡，
统计为身体交叉 84、自交 440；因此仍保持 `review_required`，不能把兜帽视为已完成。

随后完成 v6 头部适配：兜帽高度仅按 Actor 头部包围尺寸加松量归一化，生成包围约
`100.53 x 105.21 cm`，尺寸门通过。12 帧 Warp 的非静态顶点由 v5 的 `13245/13967`
降至 `11720/12076`，但身体交叉 `85`、自交 `449`，动态门仍未通过。下一步应处理
兜帽初始深度/摆放和袖子自碰撞，不能继续仅放大或缩小头部尺寸。

v7 将 Actor-scaled hood 的初始锚点下移到校准后的颈部基线；静态桥接通过，但 12
步物理检查为身体交叉 `89`、自交 `472`，未通过动态门。v8 进一步把帽兜改为带脸部
开口的两片式拓扑，静态桥接通过（14 panels、18,524 faces），但短步检查仍为
`9078/9370` 个顶点未静止、身体交叉 `89`、自交 `493`，且校准后的 Actor 叠加预览
仍不是可接受的长袍轮廓。因此 v7/v8 均保留为诊断候选，不晋级为正式资产。

同时修正了预览诊断的坐标/单位错误：Actor 与 GarmentCode OBJ 均按 Y 轴竖直导出，
Actor OBJ 与厘米服装叠加时使用现有校准比例 `56.6540755631`。此前按 Z 轴或 100 倍
缩放生成的预览不能作为质量结论。

当前结论：Actor 头部测量合同本身有效，但 GarmentCode 原生两片式帽兜和当前主体
摆放仍不足以完成里程碑。下一步应保留 GarmentCode 主体/袖子实验，同时单独生成一个
基于 Actor 头部包络、带脸部开口的 Actor-conformed hood shell，再与领口连接。

已开始独立帽兜壳体路线：`tools/blender/generate_actor_conformed_hood_shell.py` 根据
头部包络生成可参数化的开脸壳体。当前 v1 使用 6 cm 余量、1.2 cm 壁厚和 120° 前脸
开口，输出包络约 `98.35 x 96.53 x 97.31 cm`。校准正面预览已通过“头部余量/脸部开口”
检查，但侧面仍是硬质半壳，未通过“下垂造型/领口过渡”检查，因此尚不合并到正式长袍。
下一步只调整后部曲线和领口连接，保持 Actor 测量与参数合同不变。

帽兜 v2 已将底环改为 Actor 颈口合同（`13 cm`）并增加 `14 cm` 后颈下垂；正面
开口和头部余量保持正确，侧面仍偏硬。将 v2 与 v8 主体/袖子组合后发现，现有
GarmentCode 主体在校准坐标下呈薄片/横向条带，不能直接作为最终长袍底座。当前决定
保留 GarmentCode 版片作为形状参考，下一步在同一 Y-up 厘米坐标合同下重建
Actor-conformed 主体/袖子，再连接 v2 帽兜。

另外用旧 v4 Actor-first 主体/袖子替换测试，组合结果仍出现边缘片/横向条带，说明
主体版片的导出或空间摆放需要独立修复，不能把失败继续归因于帽兜。当前里程碑仍为
`review_required`，暂不进入材质、随机池或正式 Studio 资产库。

本轮还厘清了坐标方向：源文件注释描述的是 Blender 内部转换后的方向，而导出的
Y-up OBJ 预览的相机 front/back 标签曾经反向。当前统一使用 Actor-first 合同
“Y-up 厘米 OBJ，front = +Z”，并从 Blender 负 Y 方向观察 Actor 正面；临时反向
预览不作为质量结论。

随后通过受控组合验证了主体问题：GarmentCode 主体/袖子 OBJ 在 Blender 导入后需要
额外翻转 Z 深度，才能与 Actor 导出 OBJ 对齐；帽兜不翻转。新增组装参数
`--flip-panels-depth` 后，主体恢复完整长袍轮廓。当前组合候选为
`actor_v4_torso_sleeves_plus_hood_v4_flipped.obj`，下一步检查领口连续性、袖子与手臂
间隙及穿插，尚未晋级正式资产。

新增 `tools/blender/audit_obj_pair_overlap.py` 对校准后的 Actor/服装 OBJ 做静态 BVH
审计，当前报告为 `1,194` 个三角形重叠对，其中帽兜 `308`、主体和袖子仍有局部重叠，
袖口为零。该结果仍保持 `review_required`；下一步处理局部松量、领口连接和袖子/手臂
间隙，不再修改全局坐标合同。

随后只对已翻转的主体/袖子版片施加 `1.55` 深度松量，帽兜保持原尺寸；静态 BVH
重叠由 `1,194` 降至 `995`，四向轮廓仍保持完整。当前候选为
`actor_v4_torso_sleeves_plus_hood_v4_depth155.obj`，下一步集中处理帽兜/领口和
袖子/手臂局部间隙。

随后对主体/袖子深度松量做了受控扫描：`1.55/1.70/1.90/2.10` 对应静态 BVH
重叠分别为 `995/696/518/531`。`1.90` 是本轮数值最低点，但三向预览仍显示衣身
是平板式斗篷/围裙，缺少可信的胸腹弧面、袖窿过渡和袖子体积；因此这个结果只能作为
碰撞诊断候选，不能以“重叠数下降”晋级。当前路线从继续外扩版片转为先构造贴合 Actor
的参数化 3D 衣身壳，再独立连接袖子和已测量头部的兜帽壳。该步骤完成前不进入布料
仿真、材质精修或正式资产库。

随后尝试直接使用 GarmentCode 原生 `Sleeve` 和 `Hood2Panels` 组件，虽然生成了
14-panel/28-stitch 候选，但 BoxMesh 在 `right_btorso` 产生退化三角形，未能进入
稳定仿真；该候选不作为当前基线。

本轮新增 Actor-conformed 3D 基座生成器 `tools/blender/generate_actor_conformed_robe_shell.py`。
它读取当前 Actor 的实际包围盒，以参数生成开颈、肩部过渡、腰部收束、下摆外扩的衣身壳，
并生成两条独立锥形袖筒；随后用已按头部测量合同生成的独立兜帽壳组合。当前候选文件为
`milestones/robes/mage_suit_v1/actor_conformed_robe_shell_v1/actor_conformed_robe_with_hood_v1.obj`。

该候选三向预览已不再呈现 GarmentCode 平板版片的横向条带，能稳定显示袍体、袖子、下摆和
开脸兜帽；静态 BVH 重叠为 `493`，因此仍是 `review_required`。这不是最终服装，也没有通过
布料动力学；下一步先修兜帽下垂/领口过渡和袖窿间隙，再决定是否把这套 3D 壳作为新的
参数化工作流基座，DressCode/GarmentCode 退回到纸样与风格候选器。
分件复核显示衣身+袖子为 `185`、兜帽为 `308`；两部分相加与组合结果一致，说明当前最
值得优先处理的是兜帽壳体与头部包络的局部交叠，而不是再次调整全局衣身宽度。
已做一次局部兜帽修复候选：脸部开口 `120° -> 150°`、后颈下垂 `14 -> 22 cm`，头部余量
仍为 `6 cm`、颈口仍为 `13 cm`。组合静态重叠降至 `441`，当前预览与文件为
`actor_conformed_robe_with_hood_v6.obj` 及 `robe_with_hood_v6_front/three_quarter/side.png`；
该版本仍需人工确认领口连续性和后颈造型，未晋级。
进一步测试后垂 `36 cm`（v7）和同时增加头部余量至 `8 cm`（v8）分别得到 `503/505`
个组合重叠；虽然 v7 侧面后垂更明显，但数值和领口表现都变差。结论是当前单层环带壳
拓扑已到参数调节的收益边界，v6 暂作为基线，下一轮应改成分离的开脸面片+后颈 cowl
拓扑，而不是继续放大兜帽。
追加了一个带后向 cowl 偏移的 v9 实验（`cowl_back_cm=14`），组合重叠为 `477`，
侧面后颈斜度有所增加但仍没有形成真正的布料褶皱，因此不替换 v6 基线；它验证了后向
偏移方向可用，后续拓扑改造可继续沿用该参数作为起点。
随后生成 v10 的“左右开脸帽片 + 独立后颈 cowl”拓扑，组合静态重叠为 `475`，四向
预览可生成但外观改善有限；这证明拓扑拆分链路已经可用，但还需要独立领口环来连接
衣身和 cowl。v10 暂不晋级，v6 仍为当前对照基线。

复核后发现旧衣身生成器按 Actor 总高度比例放置颈线约在 `112 cm`，而头部测量合同的
头部下缘约为 `86 cm`，造成衣身侵入头部。新增 `--head-measurements` 颈线约束后生成
`actor_conformed_robe_shell_v2.obj`，衣身单独静态重叠降至 `60`，与 v6 兜帽组合降至
`316`；三向预览也显示肩线下移、头部完整露出。该 v2 成为新的基线候选。

尝试额外加参数化领口环后，组合重叠反升至 `530` 且视觉收益有限，因此领口环实验不
晋级。后续应直接改衣身上缘与 cowl 的交界，避免叠加未经贴合的连接件。

直接把兜帽 cowl 底部对齐到 v2 衣身颈线（`cowl_drop_cm=5`，头部余量/开脸/颈口不变）
生成 v11 后，组合静态 BVH 重叠降至 `202`。侧面衣身-兜帽断层明显缩小，正面肩线不再
侵入头部；v11 当前作为新的几何基线。它仍是参数化几何候选，不代表布料物理或材质质量
已经通过，下一步可进入局部领口人工审查和低成本动作/碰撞验证。

v11 已接入现有 Actor Armature 做低成本动作烟雾测试：通过最近 Actor 顶点复制 `63` 个
骨骼组、`2,954` 条权重分配，在 7 个关键帧中没有整体脱离或爆炸；局部穿体审计为
`127..130` 个顶点，且动作前后基本稳定。因此“共享身体 + 服装模板”的方向通过了可行性
烟雾门，但最近邻绑定只适合验证跟随能力，不能作为最终蒙皮。下一步应改为按衣身/袖子/
兜帽区域使用语义骨骼权重，再做动作验收。

随后完成语义绑定实验：识别出衣身、左右袖和兜帽 4 个连通组件，分别绑定到腰/脊柱、
锁骨/上臂/前臂和头/颈骨骼。7 个关键帧中衣身保持整体形状、袖子跟随手臂、兜帽跟随
头部，没有整体脱离；穿体审计为 `147..154` 个顶点，仍标记 `review_required`。这说明
共享身体模板的绑定机制可行，但还需要局部松量/权重修正才能进入生产验收。

随后引入外部 CC0 模板进行路线验证：下载的 `smoothrobebasemesh.blend` 只有一个长袍网格，
带 Mirror/Subsurf 修改器、约 1516 个基础顶点、无 UV、无骨骼。它作为真实服装拓扑母版
是有效的，但不是可直接穿到 Actor 上的成品。通过 Elastic Clothing Fit 完成两次贴合后，
`fit_actor_v1` 的肩线仍高于当前 Q 版 Actor，且动作检查出现明显悬空；提高贴合强度到
`fit_actor_v2` 后尺寸接近 Actor，但袖子/肩线仍与头部比例不匹配。该资产因此登记为
`reference_topology_only`，不替换 v11 几何基线，也不进入正式服装池。

本次验证确认：外部模板能够显著减少“从零建立服装拓扑”的工作，但不能消除针对共享
Actor 的肩线、袖窿、兜帽和动作适配工作。后续模板库应按“长袍母版 + 兜帽/袖子/衣摆
部件变体”组织，而不是每种风格重新寻找整套服装。

随后实现 Q 版分区适配器 `tools/blender/build_qstyle_partitioned_robe.py`。它以 Actor 的
上臂骨骼为袖子目标，把衣身、左右袖和领口登记为独立区域，并修正了当前骨骼命名与屏幕
左右方向相反的问题。`qstyle_partition_v2` 的肩线检查已通过，袖子不再停留在头部高度；
但衣身局部穿透、长袍松量审计和原模板缺少独立兜帽拓扑仍未通过，因此该候选仍为
`review_required`，不进入正式服装池。修复顺序见 `docs/quality/ALIGNMENT_REPAIR_QUEUE_QSTYLE_ROBE.json`。

继续尝试时，自动投影领口产生了开洞和帽体断裂，已保留为失败证据；随后改用独立兜帽壳
替换外部模板的上半部分，生成 `qstyle_independent_hood_v2`。该组合解决了结构上的
“衣身上缘直接穿入头部”问题，但兜帽轮廓仍偏平，衣身穿透与宽松量检查仍失败。当前
结论是：分区适配器可以作为工程基础，但要达到可用的法师长袍，还需要真正的 Q 版兜帽
参考或重新制作兜帽网格；继续调全局贴合参数没有足够收益。

随后下载并检查了 CC0 的 OverScore Proxy 1.5 模块化服装库。它提供带 UV 的 Q 版低模服装部件，
包括 `Winter Jacket with Hood`、`Winter Jacket without Hood`、`Assassin Hood` 和 `Long Skirt`。
适配器已修正 Mirror 先于蒙皮权重的顺序，双侧袖子绑定可以正确生成；但其内置兜帽在当前
Actor 头部包络下被遮挡，独立 `Assassin Hood` 放大后又变成横向面罩。v6 通过了袍摆无穿透，
但肩部定位、身体松量和视觉兜帽门槛仍失败，因此仅登记为失败的源资源适配实验，不进入正式服装池。
资源记录见 `third_party/clothing_sources/overscore_proxy_15.json`，候选与审计见
`E:/Env/Assets/clothing/opensource/overscore_proxy/mage_robe_v6/`。

## 晋级门槛

- SewingGPT 输出可重建，固定 seed 得到相同版型；
- 衣片、接缝和兜帽连接关系完整；
- 长袍轮廓符合 Q 版日漫 JRPG 方向，256px 下结构仍清楚；
- 放到当前 Actor 上没有明显穿体、断裂、漂浮或兜帽穿头；
- 四向和 Walk 动画审查通过；
- 生成记录能追溯到 DressCode commit、recipe、seed 和外部模型资源版本。

## 已知限制

DressCode 官方预训练模型覆盖的是既有服装类别，魔法师长袍与兜帽需要从相近类别初始化并做受限结构改造；第一阶段不承诺一次提示直接得到最终可用的完整长袍。当前已用 `Manojb/stable-diffusion-2-1-base` 镜像完成本地 SD 2.1 管线校验，但在正式里程碑前仍需复核镜像来源、授权和输出质量。GarmentCode/Warp 目前使用 CPU 构建的定制 Warp，虽然链路可运行，但正式批量仿真前仍需补齐 CUDA 构建和 trimesh 渲染兼容层。

详细作业流见 [`../WORKFLOW_DRESSCODE.md`](../WORKFLOW_DRESSCODE.md)。
