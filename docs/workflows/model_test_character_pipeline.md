# model_test：Hunyuan3D 角色基础单元工作流

## 当前目标

在 AssetsStudio 的默认风格下，先生成一个男性冒险者完整服装候选，再把它拆成可组合的 3D 演员基础单元：

- 不带鼻子、嘴和表情线的 Actor 身体基底；
- 独立发套头发；
- 独立夹克、衬衣/领口、腰带/腰包、裤装、手套、靴子和围巾。

参考结构是 `milestones/body/chibi_actor_mixamo_walk_v1.blend`，不是泛化的普通 Q 版角色。必须保持大圆头、紧凑短身、短四肢、圆手脚和低频大块造型。

## 已完成的候选链路

1. image_gen 生成男性冒险者正面全身图。
2. rembg 生成透明背景 RGBA 输入。
3. Hunyuan3D-2mini Turbo 生成完整人物形状 GLB。
4. ComfyUI 已安装 Hunyuan3DWrapper，已承接全部 8 个服装/发套遮罩分支。

当前拆分进度：发套、冒险者夹克和裤装已通过 ComfyUI 遮罩分支生成独立 GLB 候选；三者均使用低显存配置（5 steps、256 octree、20000 chunks、最多 40000 faces）。它们仍需在 Blender/Studio 中做比例、穿插和动作贴合审查。

部件产物位于：

`workspace/model_test/male_adventurer_v1/parts/masks/`

`workspace/model_test/male_adventurer_v1/parts/hunyuan/`

ComfyUI 可复用工作流位于：

`workspace/model_test/male_adventurer_v1/comfyui/male_adventurer_hair_wig_workflow.json`

## P3-SAM 本地试验结论

P3-SAM 已在 `E:\env\Hunyuan3D-Part-venv` 中独立跑通，并对完整 GLB 进行了低显存自动分割。10,000 点、32 个提示时得到 2 个几何标签；提高到 128 个提示后得到 5 个几何标签，但没有自动产生可靠的“夹克/裤子/发套”语义标签。

这证明 P3-SAM 可以作为整体网格的 3D 初筛工具，但当前融合服装网格仍不足以直接变成生产级服装部件。后续应使用它提供的面标签作为 Blender 修复起点，再由 Actor V1 服装壳层补齐边界和隐藏内层。

候选登记见：

`workspace/model_test/male_adventurer_v1/manifest.json`

## 拆分原则

不要把完整 Hunyuan GLB 直接按拓扑连通块当作衣物分割结果。完整网格通常是连续表面，也没有可靠的“头发/夹克/裤子”语义标签。

ComfyUI 的正确职责是：

1. 读取原始 RGBA 人物图；
2. 为发套、夹克、衬衣、腰带、裤装、手套、靴子和围巾生成独立遮罩；
3. 每个遮罩分支保留原始尺度和正面构图；
4. 将每个部件图分别送入 Hunyuan3D 形状节点；
5. 输出独立 GLB，再在 Blender/Studio 中绑定到 Actor V1 做贴合和动作验证。

身体基底不从完整服装图中猜测隐藏部分，直接以 Actor V1 为结构真相，再移除五官组件；如需 Hunyuan 生成身体，必须另外提供无遮挡身体参考图。

## 通过标准

- 参考图和模型都没有鼻子、嘴、唇线或脸部表情暗示；
- 发套、袖口、领口、腰带、裤脚、手套和靴口在 256px 预览中可辨认；
- 每个部件可独立导出，并能绑定到 Actor V1；
- 正、侧、背和 Walk 动画中不出现明显穿插；
- 只有人工审查通过后，候选才能从 `candidate` 晋级正式里程碑。
