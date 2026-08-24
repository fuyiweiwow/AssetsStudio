# 功能：风格种子、素体/配件生成与本地资产生命周期

## 目标

把 AssetsStudio 建成项目无关的本地美术素材供给实验室，并先用带 `bombadvanture/ba` 消费者标签的无嘴鼻 Q 版日漫西幻 Profile 验证完整链路：

`StyleProfile + 权威参考 -> 风格种子候选 -> 人工入库 -> 无部件标准 Actor 候选 -> 人工入库 -> 分 Slot 部件候选 -> 人工入库/销毁 -> Recipe 脚本装配`

素体通过 2D Gate 后继续进入：

`注册 RGBA -> Hunyuan3D Actor 形状候选 -> Blender 四向/拓扑 Gate -> 本地 3D 入库或销毁 -> 重拓扑/UV/材质/骨骼 -> ActorProfile`

BA 是首个消费者标签，不是 Studio 的全局风格。新增消费者应登记独立 StyleProfile、权威图、不可变特征和 QA，不修改通用生成器。

## 顺序与原因

1. **风格契约与种子**：先分离形状/脸部/渲染语法和具体角色身份；否则素体与配件无法判断是在复用风格还是复制角色。
2. **标准 Actor Core**：引用已入库风格种子的版本谱系，但只继承 `actor_core_contract` 中的头身比、轮廓与材质语法。完整角色种子图不能直接作为 Actor 的 ReferenceLatent，否则会复制头发、五官和服装。产物必须光头、无耳、无所有五官、无服装、鞋和饰品；它是唯一身体核心，不是完整人物。
3. **分 Slot 部件**：引用已入库 Actor 作为尺寸父资产并绑定 ActorSlotProfile，使用槽位尺寸/包络和无人物 `isolated_slot_authority` 作为图像参考。头发、眼睛/眉毛、耳朵、上装、下装、鞋与配件分别生成和重建，禁止先生成完整人物再拆连通块。
4. **Recipe 装配**：脚本按 Recipe JSON 选择一个 Actor 与多个已批准 Slot，完成放置、身体遮罩、骨骼白名单、权重和碰撞，再进入四向与动作 QA。
5. **LoRA 决策**：ReferenceLatent 压力测试通过则不训练；只有在多主题/多 Seed 持续漂移时才建立按风格 Profile 隔离的 LoRA，不能给整个 Studio 加单一 LoRA。

这里的“风格种子”不是一个随机数。它由版本化 StyleProfile、消费者标签、权威参考、生成参数、被人工批准的种子图和压力测试记录共同组成。

## 数据与存储合同

- 候选：`workspace/local_generation/{style_seeds|base_actors|accessories}/<job-id>/`；
- 本地资产库：`workspace/local_asset_library/{style_seeds|base_actors|accessories}/<asset-id>/`；
- 两者都位于被 Git 忽略的 `workspace/`，默认不上传；
- “加入资产库”复制候选及生成记录并写入 `asset_manifest.json`；
- `asset_role` 固定区分 `style_calibration_anchor`、`canonical_actor_core` 和 `isolated_slot_source`；稳定 API 字段仍使用 `style_seed|base_actor|accessory`，避免后续与原 Studio 整合时再次迁移；
- “立即销毁”只允许删除已完成/失败且尚未入库的精确候选目录；
- 已入库资产不能用候选销毁接口删除，防止破坏素体/配件的父子引用。
- 3D 候选：`workspace/local_3d_generation/base_actors/<candidate-id>/`；
- 本地 3D 库：`workspace/local_3d_asset_library/base_actors/<asset-id>/`；
- 3D 入库只表示通过形状来源 Gate；manifest 必须继续声明 `untextured source mesh, not game-ready`，不得伪装成已绑定成品。

## Studio 与 API

Studio “本地三视图”提供三个通用模式：风格种子、标准 Actor、独立 Slot 部件。Actor 可选择已入库 `style_seed_asset_id`；部件可选择已入库 `base_actor_asset_id`。`base_actor` 在接口层明确等价于 `canonical_actor_core`，不能保存完整着装人物。

后续整合原 Studio 时，本地候选库不直接进入 Gallery/随机池。只有通过 Actor/Slot 编译、四向、动作和碰撞 QA 的 3D 资产，才由注册脚本写入现有 AssetRegistry；Recipe 只引用稳定资产 ID，不复制原始候选文件。

桥接 API v4：

- `POST /api/style-seeds`、`POST /api/base-actors`、`POST /api/accessories`；
- `POST /api/<kind>/<job-id>/accept`；
- `DELETE /api/<kind>/<job-id>`；
- `GET /api/library?kind=style_seed|base_actor|accessory`。
- `GET /api/3d-assets`、`GET /api/3d-candidates/<id>/model|preview/<view>`；
- `POST /api/3d-candidates/<id>/accept`、`DELETE /api/3d-candidates/<id>`；
- `GET /api/3d-library/<id>/model|preview/<view>`。

Studio 3D 工作台使用真实 GLB 交互预览和 Blender 四向审查图。只有四项人工 Gate 全部确认后才能复制到本地 3D 库；候选销毁接口只删除精确候选目录。

## RTX 3060 12GB 纹理策略

Hunyuan 官方把 shape 和 paint 设计为两个阶段，并标称 shape 约需 6GB、shape+texture 合计约需 16GB；官方入口提供 `--low_vram_mode`。因此 12GB 机器的生产默认不强依赖完整 Hunyuan Paint：

1. 当前 2MV 只负责形状来源；
2. Blender 对批准形状或重拓扑网格做 UV；
3. 从批准的 front/right/back/left 参考图投影颜色，烘焙为 1K/2K Base Color；
4. 对 BA/Q 版风格执行色块聚类、接缝修复、AO 烘焙和少量手工/图像模型修补；roughness/metallic 使用受控语义材质，不从写实模型盲猜；
5. Hunyuan Paint Turbo/2.1 Paint 仅作为低显存可选实验。先用 ModelScope 下载必要权重并在 `low_vram`、低分辨率、单任务下测峰值；通过前不成为 Studio 必需环境。

该顺序更适合无皮肤微纹理、低频干净色块的项目风格，也便于未来其他项目替换材质语法。

已对首个高模做过两次“按全局包围盒直接投影四向顶点色”的隔离探针。修正 Blender 图片原点后，透明区 fallback 从 164,255 降到 2,358，但仍出现前后颜色串投、白底污染和明显接缝；原因是 Hunyuan 高模表面与 2D 图不存在可靠逐点对应，且 CORNER 顶点色会把导出顶点从 126,388 膨胀到 756,961。该探针已销毁，禁止接入 Studio。

因此这里的“多视图颜色投影/烘焙”必须发生在重拓扑和 UV 之后，使用与审查图匹配的正交相机、逐视角可见性/法线 mask、重叠区融合和 UV 接缝修复；不能退化为全局 AABB 映射。

## 稳定化 Gate

每个 BA 风格候选至少检查：

1. 正面与侧面均无嘴、嘴线、嘴唇、鼻、鼻梁和鼻孔；
2. 头身比保持 2.1–2.5H，大圆头、短而厚实的肢体；
3. 改变人物性别表达、发型、服装类别与主色后仍保持同一造型/材质语法；
4. 配件不复制人物，并保持厚实、低频、游戏镜头可读的结构；
5. 自动分栏一致性通过后仍需人工确认，自动 QA 不替代美术批准。

分栏中心偏移容差为 `<= 0.09`。该值允许厚发型背视图产生少量视觉重心偏移，同时仍会拒绝历史 `0.0928` 及更大的偏移；头身、落脚线、色彩与人工方向检查保持独立 Gate。

## 阶段状态

- [x] 通用 StyleProfile 支持消费者标签；
- [x] BA 首个无嘴鼻风格 Profile；
- [x] Studio 三模式与候选入库/销毁交互；
- [x] 后端 ReferenceLatent 父资产引用与本地资产库；
- [x] 生成短发/长发 BA 风格种子对照并通过增强后的发型拓扑人工 Gate；旧批准已撤销；
- [x] 用两项批准种子生成过带头发/训练服的完整角色锚点；后续复核确认其不是标准 Actor，已从 Studio 素体库移除；
- [x] 完整角色 Hunyuan3D PoC 验证了 2MV/Blender 链路；该网格已作为错误分类候选移除，不能进入 Actor 库；
- [x] Studio 接入 3D GLB 交互预览、四向图、人工 Gate、候选销毁与本地 3D 入库 API；
- [x] 生成并批准第一份光头、无耳、无五官、无服装/鞋/饰品的标准 Actor Core `0ef398ca...`；
- [x] Actor Core 进入 Hunyuan 并形成 3D shape source：118,564 顶点、237,124 面、单连通、watertight，峰值显存约 5.43 GiB；
- [x] 用户确认四向形体后，`0ef398ca...` 已进入本地 3D 库；它仍明确是无纹理 shape source，不进入 Gallery/随机池；
- [x] 为批准的 Actor Core 建立高度归一化的 Q 版骨点 Profile，并保留 AccuRIG 人工落点复核要求；
- [x] 非破坏性生成绑定候选：61,002 顶点、122,000 面、单连通/watertight/manifold；相对高模四向轮廓最差 IoU `0.999944`，FBX 往返 Gate 通过；
- [x] Studio 已批准 3D 来源卡片只读展示四向骨点图，并提供高模 GLB、绑定 GLB 与 AccuRIG FBX 下载；
- [x] Studio 支持在精确 Actor 卡片选择人工 AccuRIG FBX，按 Actor/intake ID 复制到本地工作区，并自动执行一对一拓扑、尺寸、骨名和权重 Gate直到四向实际骨架预览；
- [ ] 在 AccuRIG 中确认骨点、完成绑定与基础动作变形 QA，再决定是否需要完整四边面重拓扑并形成 ActorProfile；
- [ ] 以 `head_hair` 为首个独立 Slot 验证生成、编译、装配和销毁/入库；
- [ ] 建立 Recipe JSON 装配入口并对接原 Studio AssetRegistry；
- [ ] 在 RTX 3060 12GB 上按 Slot 验证重拓扑后 UV/烘焙默认路线，并单独测试 Hunyuan Paint low-vram 可选路线；
- [ ] 根据压力测试决定是否需要 LoRA；
- [x] 通过 Tailscale 发布 Tailnet-only 审查入口。

当前的 122,000 面绑定候选是经过量化审查的减面副本，不等同于已完成生产级四边面重拓扑。高模资产保持不变；只有绑定后的肩、肘、髋、膝变形 Gate 暴露问题时，才投入完整重拓扑，避免在尚未验证变形需求前制造第二套身体拓扑事实源。

人工回传与自动预览的完整目录、Gate 和失败语义见 [`actor_core_manual_accurig_intake.md`](../workflows/actor_core_manual_accurig_intake.md)。当前完成的是“回传后直到 REST 预览”；动作重定向和变形批准不会在文件上传后自动发生。
