# MV-Adapter 动漫多视图验证（2026-08-21）

> **状态：已于 2026-08-23 撤销。** 重新目视检查 768 输出后，发现明显块状伪影和跨视图角色不一致；脚本完成不等于视觉通过。I2MV SDXL 的 ModelScope 权重也在官方版本组合下复现 70 个 reference layer cache 缺失。当前本地候选已改为 `FLUX.2 Klein ReferenceLatent`，详见 `local_reference_turnaround_validation_2026-08-23.md`。

## 历史结论（已撤销）

`MV-Adapter + Animagine XL 3.1` 已在当前 RTX 3060 12GB Windows 主机上完成稳定的 768×768、50 步文生四视图测试。结果具备统一的 Q 版日漫倾向、服装主色、披风、腰带和人物比例在 front/right/back/left 之间基本对应；没有 OOM、蓝屏或 CUDA 崩溃。

这条路线比“SDXL 独立生成三张图”更适合作为本地多视图候选生成器，但仍不是几何真相，必须经过轮廓、部件、颜色和 Hunyuan 来源网格 QA。

## 本地模型与脚本

- Anime base：`E:\env\models\animagine-xl-3.1`。
- MV-Adapter T2MV：`E:\env\models\mv-adapter\mvadapter_t2mv_sdxl.safetensors`。
- 官方代码：`E:\env\repos\MV-Adapter-main`。
- 测试输出：`E:\env\outputs\mvadapter_anime_adventurer_20260821\animagine_mvadapter_4view_768.png`。
- 单视图输出：同目录下的 `animagine_mvadapter_4view_768_0.png` 至 `_3.png`。

## 测试矩阵

| 配置 | 结果 |
| --- | --- |
| SDXL base + MV-Adapter，512×512，20 步，4 视图 | 可生成，画面偏低多边形，但视图对应关系成立 |
| Animagine XL 3.1 + MV-Adapter，512×512，20 步，4 视图 | 严重块状伪影，不采用 |
| Animagine XL 3.1 + MV-Adapter，768×768，50 步，4 视图 | 通过；Q版日漫风格和服装跨视图基本稳定 |
| Animagine XL 3.1 + MV-Adapter，768×768，50 步，直接 3 视图 | 伪影；当前 T2MV 权重不采用直接 3 视角配置 |

## 视图策略

当前项目口头称“三视图”，但标准件合同实际是 `front/right/back/left` 四向。当前最稳妥的方式是始终联合生成四视图，再将 `front/right/back` 作为三视图交付，保留 `left` 用于检查非对称发型、披风、腰包和裙摆错误。不要让当前 T2MV 权重直接以 `num_views=3` 运行。

## 角色与画风判断

本轮提示词为 Q 版日漫、西方幻想 RPG 女冒险者、青绿色服装、奶油色领口、棕色短披风和皮革腰带。生成结果已经能保持整体设计语言，但面部细节、眼睛形状、披风背面结构和服装小部件仍需人工修正。

若要固定一个长期复用的女冒险者，下一步应在 MV-Adapter 之上增加项目自有的风格 LoRA/角色 LoRA；IP-Adapter 或 InstantStyle 可作为参考图风格/身份辅助，但不能替代 MV-Adapter 的多视图条件。

## 原决策（已撤销）

1. 本地多视图实验后端：`MV-Adapter + Animagine XL 3.1`。
2. 默认生成：四视图联合生成，取前三视图交付，left 保留 QA。
3. 生产标准件：仍需通过 RGBA 分离、Hunyuan3D-2MV、ActorProfile/Slot Compiler 和动作 QA 后，才考虑替代 GPT ImageGen。
4. Qwen 原始 57GB Windows 分片路径继续停用。

## 官方资料

- [MV-Adapter 官方实现](https://github.com/huanngzh/MV-Adapter)
- [ComfyUI-MVAdapter 官方节点](https://github.com/huanngzh/ComfyUI-MVAdapter)
- [Animagine XL 3.1](https://huggingface.co/cagliostrolab/animagine-xl-3.1)
- [IP-Adapter 官方实现](https://github.com/tencent-ailab/IP-Adapter)
