# 环境发现与模型资产

## 发现规则

所有入口按以下顺序解析环境：

1. 显式命令行参数；
2. 专用环境变量；
3. AssetsStudio 相邻目录；
4. 用户目录中的常见安装位置或模型缓存。

找不到时应列出已检查位置并停止，不在文档中写死盘符。

### ComfyUI / FLUX.2

- `ASSETSSTUDIO_COMFY_ROOT`：可选 ComfyUI 根目录。
- `ASSETSSTUDIO_PYTHON`：可选 Python 可执行文件或命令。
- 启动器也会搜索相邻 `ComfyUI`、其 `.venv`/`venv`/嵌入式 Python、当前虚拟环境和 PATH。

需要：

- `flux-2-klein-4b-fp8.safetensors`
- `qwen_3_4b.safetensors`
- `flux2-vae.safetensors`

### Hunyuan3D

- `HUNYUAN3D_SOURCE`：可选官方源码根目录。
- `HUNYUAN3D_MODEL_ROOT`：可选 `Hunyuan3D-2mv` 模型根目录。
- 默认还搜索相邻 `Hunyuan3D_Experiment` 与 ModelScope/Hugging Face 缓存。

优先用 ModelScope 获取官方 `Tencent-Hunyuan/Hunyuan3D-2mv`。只保留形状模型的 `config.yaml` 与拆分后的 `model.pt`、`vae.pt`、`conditioner.pt`；拆分成功后完整 checkpoint 是可删除的重复运行资产。

## RTX 3060 12 GiB

- FLUX 使用 FP8、`--lowvram`、关闭 pinned memory/异步 offload、无预览缓存。
- Hunyuan 使用拆分权重、CPU offload、较低 octree resolution，再由 Blender 做拓扑与预览。
- 纹理不在 Hunyuan 形体阶段解决。优先采用低分辨率语义色块、共享材质、2K 或更小图集、烘焙 AO/法线和按需局部重绘；不要在 12 GiB 显存上把高分辨率多视图纹理扩散绑进形体生成。

验证当前机器：

```powershell
python .\tools\validate_studio_local_generation.py --check-models
```
