# 家庭机器继续实验：2026-09-08 阶段检查点

分支：`research/actor-core-generation-v2`。本入口是阶段成果与换机操作的索引；不要从旧三头身代理、旧固定槽位或曾失败的同名实验目录继续。

## 成果清单

| 阶段 | 有效结果 | 已验证 | 尚未完成 |
| --- | --- | --- | --- |
| 二维输入 | `inputs_v2` 的正/左/背 RGBA，右侧及源图也保存 | 腿间负空间、内部高光、文件哈希 | 多种真实 Actor 的泛化；左侧仍由右侧镜像 |
| 原始素体 | `run_v2/shape.glb`，270192 面 | 单连通、封闭、Euler=2、双脚截面分离 | 完整自交和绑定验收 |
| 轻量副本 | `static_50k_v2/actor_offline_v2_50k_rig_mesh.glb`，50000 面 | 导出后结构通过；四向轮廓平均 IoU 0.999860 | 动画关节布线与变形质量 |
| 静态腰带腰包 | `waist_contact_v5/actor_offline_v2_waist_contact.glb` | 接触/外凸约束、零表面相交、双向各 1024 点包含抽样、导出拓扑审计 | 人工外观审核、配件轻量化、动画 |
| Studio | 现有工作流保留；新增离线 CLI/JSON | 可单独重放 | 新实验尚未接入页面或入库 |

上表路径均相对 `workspace/local_generation/actor_offline_gate_20260908/`。腰带 GLB 是独立配件，不能单独打开后误认为少了素体；组合预览由重放脚本生成。原始人体和轻量副本不被试装脚本覆盖，已有 AccuRIG 标定文件未改动。

有效文件、所需源图、配件原件和运行脚本均在 Git；公共模型权重、Python 虚拟环境、Blender 安装包不重复上传。检查点清单为 `milestones/actor_offline_20260908/checkpoint.json`，用仓库相对路径和 SHA256 校验；文本统一 LF 校验以兼容 Windows 的 Git 换行转换。报告里的旧绝对路径只记录来源，不作为换机定位依据。

另提供只包含当前检查点文件与说明的 ZIP，解压后进入 `AssetsStudio-checkpoint` 即可执行路线 A 的环境准备、verify 和 replay；ZIP 没有 `.git`，因此不要在其中执行拉取命令。长期开发仍建议克隆上述分支。ZIP 不含任何私人标定内容或公共大模型权重。

## 路线 A：先继续静态实验，不加载任何 AI 模型

这条路线只需要 Python 与 Blender，**不需要 FLUX、Qwen、Hunyuan 权重、AccuRIG 或训练环境**。它适合先确认家中机器能重放当前成果；并不证明 RTX3060 已能跑完整生成产线。

1. 拉取此分支。已有目录若有未提交实验，先保留它们，不使用 `reset --hard`：

```powershell
git fetch origin research/actor-core-generation-v2
git switch research/actor-core-generation-v2
git merge --ff-only FETCH_HEAD
```

新机器没有该分支时可以直接克隆：

```powershell
git clone --branch research/actor-core-generation-v2 https://github.com/fuyiweiwow/AssetsStudio.git
cd AssetsStudio
```

2. 优先复用已有 Python 3.10 环境。若没有合适环境，创建独立静态环境再安装依赖；不会安装 torch 或模型：

```powershell
py -3.10 -m venv .venv-actor-static
.\.venv-actor-static\Scripts\python.exe -m pip install -r requirements-actor-static.txt
```

3. 搜索已有 Blender：支持 PATH、Program Files 下 Blender Foundation、仓库相邻 `blender-*` 便携目录。发现失败才显式指定 `BLENDER_PATH` 或命令的 `--blender <实际找到的exe>`。本轮验证使用 Blender 4.5.10 LTS；其他版本允许尝试，但结果需重新检查。

4. 在仓库根目录执行（也可以用已激活且具备依赖的 `python` 替换下方解释器）：

```powershell
.\.venv-actor-static\Scripts\python.exe tools/model_test/actor_checkpoint.py verify
.\.venv-actor-static\Scripts\python.exe tools/model_test/actor_checkpoint.py replay --output workspace/local_generation/home_static_01
```

预期最后输出 `STATIC_REPLAY_PASS`。脚本会校验冻结文件、复查素体、跑 5 项 Blender 测试、后台静态适配、检查报告并审计导出。任何失败即停止；输出目录必须是新的。四向图片在 `home_static_01/fit/preview/`；组合 GLB 在 `home_static_01/fit/`，文件名带 `_on_actor_offline_v2_50k`。

`verify` 拒绝改过的冻结脚本/资产。开始新实验前先完成重放，再复制参数到新实验目录、使用低层 CLI；不要用 `build` 将未知差异重新标成通过。`build` 仅用于维护者发布新检查点。

## 路线 B：RTX3060 上重跑三维生成（独立硬件验证）

先走通路线 A，再按 [环境发现](ENVIRONMENT.md) 找到 Hunyuan 专用环境、源码和现有拆分权重。固定使用 **Hunyuan3D-2mv 常规模型 `hunyuan3d-dit-v2-mv`，不是 turbo/fast**。离线生成入口已经固定这个子目录，避免换机自动选成另一种模型。

缺少公共权重时优先使用 ModelScope 的 `Tencent-Hunyuan/Hunyuan3D-2mv`；依 `split_hunyuan_checkpoint.py --help` 将相应 checkpoint 拆分为 `split_components/model.pt`、`vae.pt`、`conditioner.pt`，并保留同目录 `config.yaml`。源码和模型由 `HUNYUAN3D_SOURCE` / `HUNYUAN3D_MODEL_ROOT` 或现有环境搜索定位。不要安装 Qwen-Image-Edit 来重放这一步。

本轮教师环境实测记录（不是家庭机器强制精确版本）：Python 3.10.20、torch 2.7.1+cu128、accelerate 1.1.1、diffusers 0.30.0、transformers 4.46.0。模型专用完整依赖仍按已有 Hunyuan 源码环境配置，不要只装静态 requirements 就直接推理。

在 Hunyuan 专用 Python 环境执行：

```powershell
python tools/model_test/actor_core_offline.py generate --inputs workspace/local_generation/actor_offline_gate_20260908/inputs_v2 --output workspace/local_generation/home_shape_01 --seed 20260908 --steps 40 --cpu-offload
```

需要记录真实 3060 的总显存、耗时、是否 OOM、结构报告与四向视觉结果。5070 Ti 的约 5.43 GiB CUDA 分配峰值不能代替这些记录。默认不运行纹理扩散；静态适配可完全不经过本路线。

## 在家继续的优先顺序

1. 运行路线 A，打开四向预览，确认腰带宽度、腰包位置与源素体形态。
2. 不急于换素体；接着做配件轻量副本与外观保真验证，再把有效候选接入 Studio 的本地审核流程。
3. 有空再对 50k 副本做 AccuRIG 标定；导入后用已有走路动画验证肩/髋/膝和腰包动态间隙。
4. 有余力时单独跑路线 B，验证 3060 生产约束；失败也不影响现有静态实验继续。

详细方法：[离线输入](OFFLINE_ACTOR_CORE_REPAIR.md)、[轻量与腰线测量](ACTOR_OFFLINE_STATIC_HANDOFF_20260908.md)、[接触适配](WAIST_CONTACT_FIT_20260908.md)。
