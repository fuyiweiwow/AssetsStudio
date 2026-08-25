# 骨骼动画资产与自动适配

骨骼动画是通用、本地资产库，不属于 BombAdventure 或某个 Actor。动画源可以被多个已经完成人工绑定的 Actor 消费；每次适配结果仍与 Actor 和 AccuRIG intake 一对一。

## 当前资产

- 动画 ID：`mixamo_standard_walk_v1`
- 显示名：Mixamo Standard Walk
- 源骨架：Mixamo
- 动作：walk，30 FPS，原地循环
- 本地源：`workspace/local_animation_library/mixamo_standard_walk_v1/source.fbx`
- SHA-256：`17344bc2531dd0062066f7a3ff9ea31c6a75174909914f8de8cbbbc9d54b35f2`
- 来源记录：仓库历史提交 `300dd82` 中的 `milestones/body/animation_sources/mixamo_standard_walk.fbx`

动画 FBX 和生成结果都在被 Git 忽略的 `workspace/`，不上传 Git。资产清单必须声明 source rig、帧率、循环策略、root motion 和源文件哈希；API 会在展示前重新校验哈希。

## Studio 流程

1. 当前 Actor 必须已有状态为 `ready` 的 AccuRIG intake。
2. 在 Actor 卡片的“骨骼动画资产”中选择动作。
3. 点击“自动适配并生成预览”。Studio 调用 Blender 将 Mixamo 22 个核心骨映射到当前 `CC_Base_*` 骨架，烘焙动作并固定为原地循环。
4. 自动检查映射完整度、帧范围、手臂和大腿动作幅度。
5. Studio 显示动态 GLB、前/右/后/左循环 GIF 和四方向接触表。
6. 人工检查手腕、肘、肩、髋、膝、脚底穿插、重心和首尾循环。自动通过不代表动作资产已经被人工批准。

当前映射覆盖躯干、头颈、双侧肩/上臂/前臂/手、双侧大腿/小腿/脚/脚趾，共 22 个核心骨。脚趾、手指或带道具动作需要独立扩展映射与 Gate，不能以当前 Walk 的通过结论替代。

## 本地输出

适配结果写入：

`workspace/actor_core/<actor-id>/manual_accurig/intakes/<intake-id>/animation_previews/<animation-id>/`

主要文件：

- `retargeted.glb`：Studio 动态交互预览和下游运行时候选。
- `retargeted.blend`：保留完整 Actor、骨架和烘焙 Action 的 Blender 工作文件。
- `retarget.json`：映射、动作幅度、自动 Gate 和产物记录。
- `front.gif`、`right.gif`、`back.gif`、`left.gif`：四方向循环。
- `four_direction_contact_sheet.png`：四方向、八个采样帧的人工审查表。

换入新的 AccuRIG intake 后必须重新生成全部动作预览，旧 intake 的结果不晋级、不随机使用。
