# 本机模型环境与本地图片模型评估（2026-08-20）

## 历史基线与当前发现规则

本节原先记录的是 2026-08-20 那台机器的盘符快照，不再作为运行合同。切换机器后必须重新查询 GPU、磁盘和 Python 环境，不能复用旧绝对路径。

当前入口按以下顺序发现环境：命令行显式参数；`HUNYUAN3D_SOURCE` / `HUNYUAN3D_MODEL_ROOT`；仓库相邻的 `Hunyuan3D_Experiment`；ModelScope/Hugging Face 本地缓存。找不到时停止并列出已检查位置。模型缺失时优先通过 ModelScope 下载到本机模型目录。

```powershell
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
Get-PSDrive -PSProvider FileSystem
Get-ChildItem .. -Directory | Where-Object Name -Match 'Hunyuan|Comfy|Blender'
& <发现到的Python> tools/model_test/run_hunyuan3d_mv_shape.py --help
```

## Hunyuan3D 结果

### Hunyuan3D-2.1

历史验证使用约 7.47GB 的 2.1 Shape/Shape-VAE 权重，没有下载完整 PBR Paint 权重。当前机器的实际位置必须通过上述发现规则确认。

已尝试：

1. 原始单文件加载；
2. 用 `mmap` 拆分为 `model.pt`、`conditioner.pt`、`vae.pt`；
3. 组件级 CPU-offload；
4. 纯 GPU、3 步、128 八叉树的最低配置。

2.1 在本机均未完成首个稳定推理：原始加载和组件加载路径分别出现 Windows 原生访问冲突。官方仓库给出的 2.1 形状生成建议约 10GB VRAM，完整形状+纹理约 29GB；因此本机不把 2.1 作为稳定路线，尤其不下载完整 PBR Paint 包来消耗空间和带宽。

### Hunyuan3D-2mv Turbo

从 ModelScope 的 `Tencent-Hunyuan/Hunyuan3D-2mv` 下载了仅形状 Turbo 所需文件：

实际文件由入口搜索 `<模型根>/hunyuan3d-dit-v2-mv*/model.fp16.ckpt`，不固定盘符；当前机器可用标准、fast 或 turbo 子目录中的一个。

约 4.93GB，未下载标准/fast 的重复权重，也未下载纹理模型。

通过 `tools/model_test/split_hunyuan_checkpoint.py` 拆分后，使用：

```powershell
& <发现到的Python> `
  tools\model_test\run_hunyuan3d_mv_shape.py `
  --front <注册后的front.png> `
  --left <注册后的left.png> `
  --back <注册后的back.png> `
  --output <候选输出目录>\shape.glb
```

通常不需要传 `--model`、`--code-root` 或 `--subfolder`；只有自动发现失败或需要覆盖选择时才显式提供。

已通过 5 步、256 八叉树、20,000 chunks 的三视图形状生成，输出约 139,828 顶点、279,660 面。结论：2MV Turbo 可以在本机部署，适合作为当前多视图形状候选生成器；纹理仍应使用 Blender/现有材质流程，不把 2.1 PBR Paint 强行塞进 12GB 显存。

## 本地图片模型候选

### 先对齐当前标准件流程

AssetsLab 最新封存的标准件流程是按 Slot 生成独立物件，而不是把整套穿戴 Actor 直接交给模型：

`Actor 校准图 -> Slot 的多视图设计 -> RGB/RGBA 分离 -> Hunyuan3D-2MV 来源网格 -> ActorProfile/Slot Compiler -> 四视图与动作 QA`

当前实际合同是 `front/right/back/left` 四向（用户口头说“三视图”时仍建议保留 left 作为非对称错误检查），白底孤立物件、同一设计跨视图对应、RGBA 前景可分离。图像模型只负责设计与参考，不负责骨骼、服装拟合、纹理、UV 或最终验收。

### 同时要求“文生图 + 多视图”的候选

| 候选 | 能否同时覆盖两项 | 与本项目的匹配度 | 结论 |
| --- | --- | --- | --- |
| WaLa-MVDream-RGB4 | 官方提供 text-to-multi-view，输出 4 视图；WaLa 另有 RGB4 multi-view-to-3D | 功能上最接近，但视角是固定相机索引而非本项目的正交 front/right/back/left，输出 256 级别，且 Autodesk 模型/输出许可仅限非商业使用 | 只适合做研究对照，不直接替换生产 ImageGen |
| MVDream | 官方 text-to-image 直接生成 4 视图 | 4×256、视角合同不同、较老的 SD2.1 系路线，不能读取 Actor 校准图做受控 Slot 编辑 | 可做低成本多视图基线 |
| Qwen-Image + Qwen-Image-Edit-2511 | Base 负责文生图，Edit 负责多图输入、编辑与一致性 | 更适合“同一 Actor 校准图上生成指定 Slot”，但这是两个模型/两个阶段；官方没有承诺一次调用直接产出严格正交四视图 | 最值得做本机质量验证，但不是单模型替代 |
| Z-Image-Turbo | 文生图 | 当前公开路线不提供生产级 Actor 多参考图/多视图合同 | 仅作快速提示词草图 |
| SDXL-Turbo / FLUX.1-schnell | 文生图 | 生态成熟，但要额外搭配多视图/编辑模型，不能单独保证跨视图一致 | 备用基线，不作为主线 |

严格按“一个本机模型同时文生图且三/四视图一致”筛选，没有一个能直接满足当前标准件生产合同。WaLa-MVDream-RGB4 是功能上最像的研究候选，但它的固定相机、低分辨率和非商业许可使其不适合作为正式默认模型；Qwen 路线更贴近现有 Actor 校准和 Slot 编辑流程，但应视为“Qwen-Image 文生图 + Qwen-Image-Edit 多图编辑”的组合。

当前项目文档已经明确：图像生成只产生概念/参考资产，不能替代 Actor、正交模板和几何验收。按 RTX 3060 12GB 的现实约束，建议分层：

| 候选 | 本机判断 | 适合职责 | 主要问题 |
| --- | --- | --- | --- |
| Qwen-Image + Edit-2511 | 最值得验证 | Actor 校准图上的 Slot 多图编辑、文生图和中文提示 | 20B 原模型不适合 12GB；需要 DiffSynth/FP8/CPU offload，耗时和系统内存需实测 |
| SDXL-Turbo | 最容易落地 | 快速概念图、服装/发型提示词草图、批量候选 | 512px 优先，细节和文字能力有限；需遵守 Stability 许可 |
| FLUX.1-schnell | 可作为质量实验 | 更强提示词跟随和风格参考 | 12B，需 CPU offload/量化，速度和内存压力明显；Apache-2.0 |
| SD3.5 Medium | 可做第二阶段实验 | 复杂提示词、文字和构图 | 权重访问需接受条款，推荐 NF4/CPU-offload，许可需审查 |
| WaLa-MVDream-RGB4 | 研究对照 | 一次 text-to-4-view 的功能验证 | Autodesk 非商业许可、固定非正交视角、256 输出，不进入正式生产 |
| HunyuanImage-3.0 | 排除 | 高端图像生成/编辑 | 83B 级别、多 GPU 方向，不适合本机 |

最终建议：暂时继续使用 GPT ImageGen 作为标准件参考图的默认生成器；它更适合当前已经验证过的“同一设计的四张独立 Slot 视图 + 后续人工检查”链。并行把 Qwen-Image/Edit-2511 作为第一本机替代验证对象，把 WaLa-MVDream-RGB4 作为多视图学术基线，不在没有通过四视图、RGBA、Hunyuan 来源网格和动作 QA 之前切换默认模型。任何本地模型都不能未经人工检查进入几何真相链。

## 相关官方资料

- [Hunyuan3D-2.1 官方仓库](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Hunyuan3D-2/2mv 官方仓库](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [ModelScope 下载文档](https://modelscope.cn/docs/models/download)
- [WaLa 官方仓库（text-to-multi-view / multi-view-to-3D）](https://github.com/AutodeskAILab/WaLa)
- [WaLa 模型/许可说明](https://github.com/AutodeskAILab/WaLa/blob/main/LICENSE.md)
- [MVDream 官方仓库](https://github.com/bytedance/MVDream)
- [Qwen-Image 官方仓库（Image / Edit-2511）](https://github.com/QwenLM/Qwen-Image)
- [Hunyuan3D-2.1 ModelScope 页面](https://modelscope.cn/models/Tencent-Hunyuan/Hunyuan3D-2.1)
- [FLUX.1-schnell 模型卡](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
- [SDXL-Turbo 模型卡](https://huggingface.co/stabilityai/sdxl-turbo)
- [SD3.5 Medium 模型卡](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium)
- [Qwen-Image 模型卡](https://huggingface.co/Qwen/Qwen-Image)
