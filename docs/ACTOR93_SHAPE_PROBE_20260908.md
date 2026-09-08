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
2. 运行 `python tools/model_test/prepare_actor93_shape_probe.py`。
3. 用发现的 Hunyuan Python 运行 `tools/model_test/run_hunyuan3d_mv_shape.py`，传入输出目录的 `front.png/left.png/back.png`，参数 `--seed 20260908 --steps 20 --guidance-scale 5 --octree-resolution 256`。另设独立 output/manifest 文件将 steps 改为 40 作对照。退出码 1 在本记录中表示拓扑门未通过，图形已经导出。
4. 使用发现的 Blender 执行 `--background --python tools/model_test/validate_hunyuan_mv_blender.py -- --input <glb> --output-dir <render> --resolution 768 --target-height-ratio 0.87`。
5. `compare_hunyuan_source_silhouettes.py` 比较 RGBA 输入目录与 `<render>/silhouette`；`review_actor93_shape_probe.py --root <实验目录> --mesh <glb文件名> --render <render相对目录> --name <评审名>` 生成四向对照及连通体报告。

RTX 5070 Ti 上的 5.43 GiB CUDA 分配峰值不是整卡占用或真实 RTX 3060 验收。下一轮优先用相同源图比较已有 TripoSG，或单独验证源图阴影是否导致表面细节；保持形态权威，不回到旧网格替代。
