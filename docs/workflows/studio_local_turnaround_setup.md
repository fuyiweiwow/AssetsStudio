# AssetsStudio 本地三视图环境与搭建

## 当前能力

Studio 的第一阶段入口支持：

`中文角色提示词 -> 固定生产合同 -> 本机 FLUX.2 Klein 4B -> 1536x768 正/右/背联合图 -> Studio 预览与生成记录`

它是提示词三视图候选生成器，不是自动验收器。页面输出必须人工确认视角、同一角色、服装结构、附件左右关系和多余肢体后，才能进入分栏注册与 Hunyuan3D。

参考图锁定、多视图重排和 Hunyuan3D 按钮属于下一阶段。已经验证可行的 ReferenceLatent 四向实验记录见 `docs/workflows/local_reference_turnaround_validation_2026-08-23.md`。

## 已验证硬件与软件

| 项目 | 当前验证值 |
| --- | --- |
| GPU | NVIDIA RTX 3060 12GB |
| 系统内存 | 24GB |
| 系统 | Windows，NVIDIA Driver 560.94 |
| ComfyUI | `E:\Env\ComfyUI`，版本 `0.28.0` |
| Python | `3.11.3` |
| PyTorch | `2.6.0+cu124` |
| Studio | Node 22+、Vite 8、React 19 |
| 本地桥接 | Python 标准库 HTTP server，`127.0.0.1:8765` |
| Studio | Vite，`127.0.0.1:4173` |
| ComfyUI | `127.0.0.1:8190` |

## 必需模型文件

```text
E:\Env\ComfyUI\models\
├── diffusion_models\
│   └── flux-2-klein-4b-fp8.safetensors  # 4,070,624,520 bytes
├── text_encoders\
│   └── qwen_3_4b.safetensors            # 8,044,982,048 bytes
└── vae\
    └── flux2-vae.safetensors             #   336,213,556 bytes
```

权威下载位置：

- FLUX.2 Klein 4B：[ModelScope 模型页](https://modelscope.cn/models/black-forest-labs/FLUX.2-klein-4B)；[BFL 官方模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)。
- FP8 单文件：[BFL 官方 FP8 仓库](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8)。
- ComfyUI 编辑模板与其文本编码器/VAE链接：[官方 FLUX.2 Klein 教程](https://docs.comfy.org/tutorials/flux/flux-2-klein)。

ModelScope 的完整 `black-forest-labs/FLUX.2-klein-4B` 仓库约 23.74GB，不应为了 ComfyUI FP8 三文件布局盲目全量下载。网络受限时可用 ModelScope 下载需要的上游仓库到暂存目录，再把与 ComfyUI 模板相符的文件放入上述三个目录；必须核对文件名和字节数。

本轮另从 ModelScope 下载并验证过：

```text
modelscope download --model AI-ModelScope/mv-adapter \
  mvadapter_i2mv_sdxl.safetensors \
  --local_dir E:\env\models\mv-adapter
```

该 I2MV 权重下载成功但运行链被否决：当前 Windows/PyTorch 组合缺失 70 个 reference attention cache，不能作为 Studio 后端。不要把“下载成功”写成“模型通过”。

## ComfyUI 安全启动参数

RTX 3060 12GB 使用：

```powershell
python E:\Env\ComfyUI\main.py `
  --lowvram `
  --disable-async-offload `
  --disable-pinned-memory `
  --cache-none `
  --preview-method none `
  --reserve-vram 1.5 `
  --listen 127.0.0.1 `
  --port 8190
```

这组参数是针对之前蓝屏风险采取的保守合同。不要在当前 24GB RAM 主机上恢复 57GB Qwen-Image 全量 Windows offload 实验。

## 一键启动 Studio

最简单的方式是在项目根目录双击：

```text
start-local-generation-studio.bat
```

它会在首次运行时补齐 Studio 的 npm 依赖，随后启动 ComfyUI、本地桥接和 Studio；`4173` 端口就绪后自动用默认浏览器打开 `http://127.0.0.1:4173/`。启动窗口应保持打开，用完后在该窗口按 `Ctrl+C`，出现 `Terminate batch job (Y/N)?` 时输入 `Y`；脚本会回收本次由它启动的桥接与 ComfyUI 进程。

若只想启动服务、不自动打开浏览器：

```powershell
.\start-local-generation-studio.bat --no-open
```

PowerShell 等价入口为：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start_studio_local_generation.ps1
```

脚本会：

1. 检查三个模型文件；
2. 如果 8190 未运行，以安全参数隐藏启动 ComfyUI；
3. 启动受限本地桥接 `studio_local_generation_api.py`；
4. 前台运行现有 Studio Vite 服务；
5. Studio 结束时，仅停止本脚本启动的桥接/ComfyUI，不会关闭用户原先运行的 ComfyUI。

打开 `http://127.0.0.1:4173`，进入顶部“本地三视图”。

该启动脚本直接运行 Vite，不触发历史 `npm predev` 资产重建。原因是全局 registry 构建器仍引用已经按 `docs/REMOVALS.md` 删除的 GarmentCode 短袖和 native-control 短裤；在它迁移到 Actor V2 Slot 合同前，不应为了启动 F009 恢复旧资产。

如果项目或 Python 路径不同：

```powershell
.\tools\start_studio_local_generation.ps1 `
  -ComfyRoot 'E:\Env\ComfyUI' `
  -Python 'C:\Path\To\python.exe'
```

## 接口与文件合同

Vite 将 `/api/local-generation/*` 代理到本地桥接：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 检查 ComfyUI 与三个模型文件 |
| POST | `/api/turnarounds` | 创建提示词三视图任务 |
| GET | `/api/turnarounds/<id>` | 查询任务状态 |
| GET | `/api/turnarounds/<id>/image` | 读取生成 PNG |
| GET | `/api/turnarounds/<id>/record` | 下载可追溯 JSON |
| POST | `/api/accessories` | 创建绑定 StyleProfile/ActorSlotProfile 的独立配件三视图任务 |
| GET | `/api/accessories/<id>` | 查询配件任务状态 |
| GET | `/api/accessories/<id>/image` | 读取配件联合三视图 PNG |
| GET | `/api/accessories/<id>/record` | 下载含 Profile 快照的配件任务记录 |

项目记录写入：

```text
workspace/local_generation/turnarounds/<job-id>/
├── turnaround.png
└── record.json
```

独立配件写入：

```text
workspace/local_generation/accessories/<job-id>/
├── accessory_turnaround.png
└── record.json
```

ComfyUI 的原始 SaveImage 输出仍位于：

```text
E:\Env\ComfyUI\output\assetsstudio\turnarounds\<job-id>_*.png
```

## 固定生成参数

- 模型：FLUX.2 Klein 4B distilled FP8；
- 画布：`1536x768`；
- views：`front/right profile/back`；
- sampler：Euler；
- steps：`4`；
- CFG：`1.0`；
- 背景：统一浅灰；
- 视角：正交、同尺度、同落脚线、无动作；
- QA 状态：固定 `visual_review_required`。

浏览器不能修改模型名、模型路径、尺寸、Comfy 节点或输出目录，这是本地安全边界。

F009 独立校验：

```powershell
python .\tools\validate_studio_local_generation.py --check-models
```

项目全局 `tools/validate_studio.py` 目前仍会因为上述已删除的旧短袖/短裤里程碑失败；这是旧 registry/ASSET_STATUS 迁移事项，不是本地生成链失败。不要用恢复被淘汰资产的方式让旧校验器变绿。

## 本轮实验结论

| 路线 | 结果 | Studio 决策 |
| --- | --- | --- |
| FLUX.2 Klein 文生联合图 | 角色配色/主要造型稳定，适合第一阶段提示词三视图 | 已集成，`provisional` |
| FLUX.2 Klein ReferenceLatent | 三/四向风格、比例与身份最稳定 | 第二阶段接入 |
| SD1.5 IP-Adapter + ControlNet | 快且省显存，侧面/背面和比例漂移 | 仅概念草稿 |
| Animagine XL + MV-Adapter T2MV | 旧记录误判；重审有块状伪影 | 已撤销 |
| Animagine XL + MV-Adapter I2MV | 70 个 reference layer cache 缺失 | 否决 |
| Qwen-Image/Edit-2511 全量 | 资源占用过大且两次蓝屏 | 禁止在当前主机恢复 |
| Krea | 云端产品/API，不是本机运行时 | 可做云端对照，不进入离线依赖 |

## Studio 端到端验收记录

2026-08-23 使用页面默认女冒险者提示词完成首个真实 Studio 作业：

- Job：`8e45a40374434afc8a0f06d8b615d5f8`；
- Comfy prompt：`d6db7207-5ab7-4151-aec9-a79d9b788ae6`；
- Seed：`20260823`；
- 输出：`workspace/local_generation/turnarounds/8e45a40374434afc8a0f06d8b615d5f8/turnaround.png`；
- 记录：同目录 `record.json`；
- 量化：同目录 `turnaround.metrics.json`。
- Git 可保留的视觉证据：`docs/workflows/assets/studio_prompt_turnaround_e2e_20260823.png`；
- Git 可保留的量化证据：`docs/workflows/assets/studio_prompt_turnaround_e2e_20260823.metrics.json`。

页面依次显示 `submitting -> generating -> completed`，生成期间按钮锁定，完成后正确回显 `1536x768` PNG 并提供记录下载入口。

自动指标：

| 指标 | 结果 | Gate |
| --- | ---: | ---: |
| 人物高度 CV | `0.0025` | `<= 0.05` |
| 落脚线范围 | `0.0026` | `<= 0.03` |
| 分栏中心最大偏移 | `0.0205` | `<= 0.08` |
| 最低跨视图色彩相关性 | `0.9189` | `>= 0.55` |

自动 Gate 全部通过。人工检查确认本次为正面、右侧和背面，角色发型、蓝夹克、红围巾、短裤与棕靴保持一致；附件背面关系仍需在进入 Hunyuan 前单独确认。

## 下一阶段

1. 页面上传/选择已批准正面锚点；
2. 改用 FLUX.2 `ReferenceLatent` 三/四向生成；
3. 视觉识别真实面板方向，禁止信任提示词顺序；
4. 调用 `normalize_turnaround_panels.py` 和 `analyze_turnaround_sheet.py`；
5. 人工确认后生成 RGB/RGBA，并排队 Hunyuan3D-2MV；
6. 在 Studio 中显示 2D 源、3D 候选和 Blender QA 的晋级状态。

独立配件路线的实测结论见 `docs/workflows/accessory_style_slot_validation_2026-08-23.md`。FLUX.2 配件联合图必须先通过自动一致性 Gate；当前腰包实验未通过，下一步改为批准单图经 Hunyuan3D 建模后由同一网格渲染三视图。
