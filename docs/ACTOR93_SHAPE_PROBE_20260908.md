# Actor93 多视图形体对照（2026-09-08）

从远端当前分支 `fa4ee98` 继续。本轮在用户要求继续实验后制作隔离三维对照；源图和网格均未晋升生产资产。

## 输入与检查修正

- 正面沿用 seed1002 无脸 B，右侧沿用用户确认的 seed1005 腹部修订 B。
- 背面平滑 v1 曾把腿间背景纳入编辑。v2 仅编辑侵蚀后的实际前景；相对原 seed1008，轮廓改变像素数为 0，编辑区外 RGB MAE 为 0。源文件为 `workspace/local_generation/actor_core_multiview_gate_20260907/back_b_seed1008_refined_v2.png`。
- 旧背面审计把 seed1009 抬起的拇指计入头部 bbox，误报头宽 406 px。隔离裁剪区最大头部连通体后，其头宽为 355 px，原“头宽增加 15%”结论撤回。当前沿用 seed1008 以保持实验输入一致；1009 仍未人工批准。
- 原审计的头底固定裁剪到 y=443，不能把头底差 0 当成实际下颌高度一致的证明。新量测明确记录 `head_bottom_is_crop_limited`。
- `prepare_actor93_shape_probe.py` 输出四张 RGBA 与源图 SHA256；只按肤色分离背景、填内部孔洞，保留画布/尺度。左侧为右侧镜像，光照也被镜像，属于形体诊断输入。

## 运行结果

使用自动发现的本地 Hunyuan3D-2mv 原版（非 Turbo），相同 seed=20260908、guidance=5、octree=256、num_chunks=20000。唯一对照变量为 steps=20/40。没有新增权重下载。

| 指标 | 20 步 | 40 步 |
| --- | --- | --- |
| 三角面 | 272232 | 272360 |
| 原始连通体数 | 12 | 4 |
| 原始整体封闭 | 否 | 是 |
| 原始 Euler | 13 | 4 |
| 最大主体封闭 | 是 | 是 |
| 四向平均轮廓 IoU | 0.934837 | 0.936148 |
| CUDA 分配峰值 | 5828215296 bytes | 5828215296 bytes |

两次原始网格均未通过素体拓扑门；40 步仍有 3 个微小碎片。形态总体保留短肢和大头，但表面凹凸、手端和头颈过渡仍需处理。当前不继续堆 steps，不绑定，不入库。原始 GLB 与渲染留在被忽略的实验目录；仓库只保存成功输入、脚本和诊断数值/结论。

Blender 预览器输出中的 `BLENDER_MV_PASS` 和 `validated` 文件名只表示导入/渲染/导出完成，不能覆盖 Hunyuan 的拓扑失败结论。轮廓 IoU 是全局诊断，不批准局部造型。

## 换机复现

先按 `ENVIRONMENT.md` 搜索 Hunyuan Python、源码、现有拆分权重及 Blender；Python 需有 torch、trimesh、Pillow、numpy、opencv，模型依赖按现有专用环境安装。无需 ComfyUI 重新生图即可从已保存输入继续。

1. 运行 `refine_actor_core_back_surface.py`，用 seed1008 原图生成上述 v2 文件（参数 `--source --output --mask-output --report`）。
2. 原来的外轮廓填充已废弃。运行 `python tools/model_test/prepare_actor93_shape_probe.py --output <新的输入目录>` 使用新的离线 profile；要重放本节旧对照，应使用已存档旧 RGBA，不覆盖它们。当前正确入口见 [离线流程](OFFLINE_ACTOR_CORE_REPAIR.md)。
3. 用发现的 Hunyuan Python 运行 `tools/model_test/run_hunyuan3d_mv_shape.py`，传入输出目录的 `front.png/left.png/back.png`，参数 `--seed 20260908 --steps 20 --guidance-scale 5 --octree-resolution 256`。另设独立 output/manifest 文件将 steps 改为 40 作对照。退出码 1 在本记录中表示拓扑门未通过，图形已经导出。
4. 使用发现的 Blender 执行 `--background --python tools/model_test/validate_hunyuan_mv_blender.py -- --input <glb> --output-dir <render> --resolution 768 --target-height-ratio 0.87`。
5. `compare_hunyuan_source_silhouettes.py` 比较 RGBA 输入目录与 `<render>/silhouette`；`review_actor93_shape_probe.py --root <实验目录> --mesh <glb文件名> --render <render相对目录> --name <评审名>` 生成四向对照及连通体报告。

RTX 5070 Ti 上的 5.43 GiB CUDA 分配峰值不是整卡占用或真实 RTX 3060 验收。下一轮优先用相同源图比较已有 TripoSG，或单独验证源图阴影是否导致表面细节；保持形态权威，不回到旧网格替代。

## 无投射阴影评审

用户指出鼻下黑影无法比较。`render_actor93_shadowless.py` 加载相同 40 步预览 blend，使用明亮的法线着色（0.7 + 0.3 abs(normal dot view)），关闭投射阴影/AO 对外观的影响，输出四个正交方向和斜下方视角。编辑前后顶点及面索引哈希相同，没有平滑或修改几何。

结果：下颌与颈部原先的大块黑色主要来自照明；均匀着色下整体与源图更接近。斜下方仍可见面部浅凹和手端局部不平整，拓扑失败记录仍有效。该预览用于检查轮廓和表面，不代表最终材质效果。

复现：用 Blender `--background <40步预览blend> --python tools/model_test/render_actor93_shadowless.py -- --output <shadowless目录>`；拼图工具增加参数 `--render shadowless --beauty-subdir . --name review_shadowless`。预览与几何哈希报告保存在实验目录 `shadowless/`。

## 左脸毛刺清理

用户认可整体形态并指出正视图左脸毛刺。检查确认它连接在主网格上，另有 3 个悬浮碎片（合计 32 面）。`clean_actor93_cheek_spike.py` 锁定原始 40 步 GLB 哈希，去除碎片，对左脸限定区域做带衰减权重的邻域平滑；600 次小步迭代消除了毛刺和根部凸起。

本地结果 `workspace/local_generation/actor93_shape_probe_20260908/cheek_clean_v2.glb`；原始 GLB 保留，可完整恢复。主网格 136162 顶点中仅修改 654 个（约 0.48%），限定区域外顶点坐标和全部主网格面索引不变。四向无投射阴影预览为 `review_cheek_clean.png`，局部参数与校验见 `cheek_clean_v2.json`。没有重新生成模型或修改整体比例。

清理后为单一封闭连通体，但 Euler 仍为 -2，对应 genus 2；原有异常通道尚未修复，不能宣称通过绑定前的拓扑门。下一步定位这些通道并验证肩/手连接；继续沿当前形态处理。

## 后续：离线输入流程重建

以上左脸定位平滑只保留为历史 workaround，不纳入通用产线。后续发现双脚阴影触发外轮廓整体填充，导致腿间背景被错误保留为前景。新预处理 v1 打开腿缝后双脚已分离，但误删背面头部浅色高光，仍有拓扑失败；v1 不应复用。

`workspace/local_generation/actor_offline_gate_20260908/inputs_v2` 同时保留腿间负空间和小面积内部高光；RGB 不改。`run_v2/shape.glb` 由同一本地 Hunyuan3D-2mv、seed20260908、40步、CFG5、octree256 重新生成，未经任何手工网格修补：135098 顶点、270192 面、单连通、封闭、Euler=2、一致面朝向，脚部 7 层切片均为两个不跨中心的轮廓。结构门全通过，但不代表通过美术/绑定验收。

四向源图/无投射阴影预览为 `review_v2.png`，遮罩对照为 `input_comparison_v2.png`。脚缘仍有小凸边，手端和肩部仍待审核。本轮不继续随机重生或按固定坐标雕刻；先审核形态，再验证可复用的有限修复与绑定前网格流程。完整复现命令、测试和硬件边界见 [离线流程](OFFLINE_ACTOR_CORE_REPAIR.md)。
