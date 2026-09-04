# Actor Core 自动生成 V2

## 结论

旧的“先让二维编辑模型画完整素体三视图，再把生成网格直接当生产 Actor”路线停止。它反复出现头部拉长、四肢过长、体型肥胖、侧面体积不足、A-Pose 腋下粘连和随机拓扑问题；继续堆提示词、ControlNet 强度或旧网格比例修补，不再视为有效进展。

V2 采用“生成形体 + 独立骨架 + 语义 Slot”：

`风格/角色参考 → 透明背景形体证据 → TripoSG 高模 → 闭合动画网格 → 有限比例校正 → UniRig 独立骨架 → 蒙皮/动画 Gate → 骨骼与截面 Slot → Actor Core 候选`

TripoSG 的 83 万面原始网格不得直接入库；经过保持封闭性的减面、受限连续形变、独立骨架、蒙皮和动态 Gate 后，它的派生网格可以成为候选。每个 Actor 允许拥有自己的拓扑与一对一骨架；跨 Actor 稳定性由标准骨名、骨骼局部 Slot、截面测量和 Recipe 提供，而不是强行共享顶点编号。

这仍然是自动生成不同 Actor，不是为每个角色寻找现成模型。骨架签名可按形态家族复用，例如当前 `generated_chibi_biped_46_v1`；四足、史莱姆或机械等语义变化时才新增骨架家族。

## 成熟方案筛选

| 方案 | 官方显存要求 | 适合本项目的部分 | 决策 |
| --- | ---: | --- | --- |
| TripoSG | 至少 8GB | 1.5B、SDF、明确覆盖 cartoon/sketch；ModelScope 有官方权重 | V2 首选形体教师 |
| Stable Fast 3D | 约 6GB | 单图快速网格、UV 与材质，可作速度/轮廓对照 | 次级基线 |
| SPAR3D | 默认约 10.5GB，低显存约 7GB | 点云可改善不可见面 | 次级研究；权重获取不如 ModelScope 顺畅 |
| Hunyuan3D-2MV | 本机旧实验约 5.43GiB 峰值 | 已有环境、多视图对照 | 保留为比较器，不再承担最终拓扑 |
| AniGen | 至少 18GB、Linux | 形状、骨架、蒙皮一体化，方向最接近最终目标 | 当前 5070 Ti/3060 均不作为依赖，持续观察 |
| TRELLIS.2 | 至少 24GB、Linux | 高质量教师资产 | 排除出 3060 产线 |

首轮只比较 TripoSG 与已有 Hunyuan，避免同时安装多个近似后端。Stable Fast 3D 只在 TripoSG 无法满足速度或轮廓时加入。AniGen/TRELLIS.2 的硬件要求超过生产边界，不能因为教师机偶尔可运行就写进 Studio 依赖。

## 为什么成功率更高

此前把三个相互冲突的问题都交给了生成模型：二维风格转换、三维不可见面推断、可绑定生产拓扑。任意一步漂移都会污染下一步，而且“看起来像”无法保证腋下可分离、左右对称或权重可复用。

V2 把职责拆开：

1. 图像模型允许保留可识别五官，只用于稳定人物身份、比例和风格；无衣服、无头发、无配件仍是硬约束。
2. TripoSG 负责头颅饱满度、躯干厚度、四肢长度和腋下分离等三维体积证据。
3. Blender 闭合减面保留连通关系；比例校正仅允许参数化的连续顶点形变，禁止导入旧素体替换局部。
4. UniRig 对每个候选独立预测骨架；标准 46 骨签名通过后再生成蒙皮，不复用另一个模型的 AccuRIG 文件。
5. Slot 由标准骨名和当前 Actor 的实际截面建立，配件可以在不共享拓扑的 Actor 之间重新适配。

## 已否决的固定旧拓扑分支

曾尝试把旧 canonical mesh 通过 CPD 和语义 cage 拟合到 TripoSG 教师。CPD 发生头、躯干、四肢跨部位吸附；语义 cage 三轮后四向轮廓 IoU 约停在 `0.7335`，且无法同时保持 Q 版头身比与局部形状。继续加入规则会重新变成“旧模型规则生成”，因此该实现和候选已从当前路线删除。

V2 当前不承诺全局固定拓扑、固定 UV 或跨 Actor 顶点编号。纹理继续独立解决；配件定位不得存储裸顶点索引，而应存储父骨、骨骼局部变换、身体截面和必要的表面投影结果。

## 有限比例校正规则

- 只允许作用于当前生成网格，不读取任何旧 Actor 网格；
- 必须保持 topology hash、封闭性和连通体；
- 单次躯干压缩不超过 15%，腹部前向收缩不超过 20%；
- 校正后必须重新运行 UniRig，不能沿用校正前骨架；
- 校正只修显式比例偏差，不承担角色生成或雕刻功能。

## 分阶段 Gate

### G0：输入证据

- 单个人物、透明背景、无头发/衣服/配件；
- 可以保留眼睛、耳朵和轻微嘴部弧度，不能让五官决定网格细节；
- A/T-Pose 手臂与躯干轮廓必须分离；
- 明确记录目标头身比与四肢长度区间。

### G1：教师网格

- 单一主要连通体；
- 前/侧轮廓与输入一致，尤其检查侧面后脑饱满度；
- 手臂、腋下和胯部不粘连；
- 不检查 UV、面流、骨骼或材质，不允许直接入库。

### G2：动画网格

- 高模减至目标面数后仍为单一主要连通体、watertight、无重复面；
- 头身比、头宽/头长、臂长、腿长、躯干长度通过数值 Gate；
- 腋下/裆部最小净空、左右对称和四向轮廓通过；
- 四向轮廓通过人工审查。

### G3：可动画性

- 为当前 Actor 独立预测骨架和权重，标准骨名映射必须匹配已批准签名；
- 肩、肘、髋、膝变形和 Slot 锚点通过；
- 只有 G3 通过的候选才能进入本地资产库，否则立即销毁或留在忽略的诊断区。

## 3060 与 5070 Ti 边界

- RTX 3060 12GB 是完整离线产线硬门槛：教师生成、拟合、Gate 和预览最终都必须在真实 3060 验证。
- RTX 5070 Ti 可批量生成教师、建立 landmark/轮廓数据和训练轻量适配器，但不得产生仅能在 16GB 运行的 Studio 依赖。
- TripoSG 官方最低 8GB，理论上落在 3060 范围内；仍需记录真实峰值、时间和冷启动结果才可批准。
- UniRig 官方推理边界为至少 8GB；当前只下载 1.44GB skeleton checkpoint，不引入 14GB 显存级 SkinTokens。RTX 3060 仍需真机复验。
- AniGen 与 TRELLIS.2 明确不进入当前生产链。
- 纹理继续与形体分离：素体只使用语义色块/共享材质，配件阶段再生成或烘焙纹理。

## 环境与权重规则

- 源码使用官方 GitHub 提交 `fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c` 的小型压缩包；模型权重只从 ModelScope 获取。
- 本地模型、第三方源码、虚拟环境、教师网格和拟合中间件全部位于忽略的 `workspace/`，不得提交 Git。
- 入口按“显式参数 → 专用环境变量 → 仓库工作区 → 相邻目录 → 用户缓存”搜索，不写死盘符。
- 推理必须 local-only；输入已有 alpha 时跳过 TripoSG 的背景移除模型，避免无意义的额外下载和轮廓扰动。
- TripoSG 准备入口：`tools/setup_actor_core_v2_research.ps1`。
- UniRig skeleton-only 准备入口：`tools/setup_unirig_skeleton_research.ps1`。它使用 Python 3.11、ModelScope 的 skeleton checkpoint 和可审计的离线补丁，不安装 `flash_attn`、`spconv`、`torch_cluster` 或 `open3d`。
- 两个入口默认只补齐缺失项；`-CheckOnly` 只审计不改环境，`-SkipWeights` 可只准备源码和虚拟环境。

## 实验顺序与停止条件

1. 用一张明确标注为“诊断输入、非几何权威”的现有 RGBA 素体图跑 TripoSG smoke。
2. 输出教师网格的四向轮廓、连通体、watertight、自交和显存报告；与 Hunyuan 同输入比较。
3. 将教师减为封闭动画网格；只有明确比例偏差时执行一次有限校正。
4. 为校正后的网格重新运行 UniRig skeleton，完成骨名映射、最多四权重蒙皮和关节变形检查。
5. 从骨骼和当前身体截面生成 Slot；复用独立配件并执行静态、动态相交 Gate。
6. 用至少三个明显不同的比例目标验证同一骨架签名，而不是只对一个角色过拟合。
7. 三个目标中至少两个通过 G2/G3 且不需要 Blender 手修，才进入 Studio 集成。

若 TripoSG 与 Hunyuan 都无法给出可用体积，但输入轮廓本身稳定，再研究多视图重建或专用角色生成器；不得恢复旧素体规则缩放或提示词堆叠分支。

## 2026-09-03 首轮本地验证

在 RTX 5070 Ti 上使用 ModelScope 官方 TripoSG 权重、透明背景诊断图和 portable hierarchical decoder 完成了两级 smoke：

| 配置 | 总耗时 | 峰值 CUDA allocated | 峰值 CUDA reserved | 原始连通体 | 主体结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| 10 steps，128→256 | 9.62s | 4.88GiB | 5.64GiB | 854 | 低精度薄片明显，仅验证链路 |
| 30 steps，256→512 | 23.42s | 5.22GiB | 6.14GiB | 8 | 最大主体占 99.9988%，watertight、Euler=2 |

30-step 四向结果证明模型重新推断出了大圆头、短四肢、饱满后脑与分离腋下，不是旧网格缩放。残留问题是输入角色自身偏圆腹、生成脸部略向前凸、网格约 83.8 万面；这些都应由 canonical 拟合时的二维轮廓权威、面部平滑区和固定生产拓扑解决，不继续增加生成 steps。

教师派生的 50,000 面网格保持 watertight；第一次受限校正将躯干压缩 `8%`、腹部前向收缩 `12%`，topology hash 不变。校正后重新运行 UniRig 得到 46 骨、单根、11 叶骨骼；Blender 自动蒙皮为零未加权顶点、每顶点最多 4 权重。

首个 `waist_accessory` 从 `CC_Base_Hip/CC_Base_Pelvis` 和当前身体截面测量，复用既有 Hunyuan 腰带网格。静态 v5 的轴向缩放比为 `1.1416`、表面相交为 `0`；挂到 `CC_Base_Pelvis` 后执行躯干弯曲、同侧手臂下摆和抬腿压力姿势，动态表面相交仍为 `0`。这些只证明单个候选链路可行，人工四向复核和 Mixamo walk 仍未完成，候选不得入库。

跨机器继续实验所需的最小模型、生成输入、四向预览、哈希和参数已固化在 [`milestones/actor_core/generated_actor_seed20260943_v1`](../milestones/actor_core/generated_actor_seed20260943_v1/README.md)。AI 权重、虚拟环境、TripoSG 高模和失败候选不进 Git，由环境脚本与 ModelScope 恢复。

## Studio 集成边界

当前研究分支不改 Studio 的生产按钮。只有完整通过 G0–G3 后才新增：

- 骨架签名与版本；
- teacher backend 选择（默认自动）；
- 生成、销毁、加入本地资产库；
- 几何、骨架、蒙皮、Slot 和动态 Gate 报告与四向预览；
- 进入既有 Rig、动画库和 Slot 配件流程。

任何原始教师网格、失败候选和诊断图都不得进入 Gallery 或随机资产池。

## 官方资料

- [TripoSG 官方源码](https://github.com/VAST-AI-Research/TripoSG)
- [TripoSG 官方 ModelScope 权重](https://www.modelscope.cn/models/VAST-AI-Research/TripoSG/summary)
- [UniRig 官方源码](https://github.com/VAST-AI-Research/UniRig)
- [UniRig 官方 ModelScope 权重](https://www.modelscope.cn/models/VAST-AI-Research/UniRig/summary)
- [SkinTokens 官方源码](https://github.com/VAST-AI-Research/SkinTokens)
- [Stable Fast 3D 官方源码](https://github.com/Stability-AI/stable-fast-3d)
- [SPAR3D 官方源码](https://github.com/Stability-AI/stable-point-aware-3d)
- [AniGen 官方源码](https://github.com/VAST-AI-Research/AniGen)
- [TRELLIS.2 官方源码](https://github.com/microsoft/TRELLIS.2)
- [PyTorch3D 固定源网格到目标网格形变教程](https://pytorch3d.org/tutorials/deform_source_mesh_to_target_mesh)
- [Open3D ARAP 网格形变教程](https://www.open3d.org/html/tutorial/Advanced/mesh_deformation.html)
