# F001/F002 眼睛与交互质量修复记录

日期：2026-08-09

## 失败证据

- 用户观察到眼睛位于脸前悬浮，眼睛上方存在类似眼皮的遮挡，原有眨眼丢失。
- 用户无法确认动画启动/停止和自由拖动能力。
- 左侧资产 Tab 切换没有可感知作用。
- 失败预览来自 F001 `actor-composite-v1.glb`；修复前 Face 合同错误指向旧 `EyePackageV1_*`。

## 诊断

- 主要维度：资产合同迁移遗漏、头部绑定/动画真值、交互编排和缺少回归验证器。
- AssetsLab 当前文档记录的有效眼睛方案是两个 Bone Parent 到 `Armature/CC_Base_Head` 的 `EyeAssemblyV1` 浅曲面，通过同一表面切换 open/half/closed 材质。
- AssetsStudio 迁移时错误退休该方案，保留了更旧的眼框/镜片叠层，并遗漏 half/closed 纹理和眨眼输出。
- 左侧 `AssetRail` 实际只更新右侧资产文字，没有形成用户要求的装配流程。

## 修复决策

- 保留 `chibi_actor_mixamo_walk_v1.blend`，从该基线重建独立的 `chibi_actor_eye_assembly_v2.blend`，不覆盖已接受身体/Walk。
- 恢复 open/half/closed 状态和确定性眨眼；网页 GLB 使用同一贴合网格的互斥状态副本，仅用于让 glTF 携带三份实际材质，不同时叠加。
- 新增 Blender 眼睛合同验证器和四方向 × 8 帧眨眼审查器。
- 用 F002 五步装配工作流替代无效资产 Tab；任意视角直接拖动进入自由模式。

## 已验证结果

- Blender 眼睛校验：两个眼睛对象均绑定 `Armature/CC_Base_Head`，frame 1 到 31 随头部移动。
- Blender 状态审查：open、half、closed 三态可见，闭眼状态没有额外皮肤色眼皮几何。
- 浏览器：五步导航切换配置；Face 步骤定位镜头；暂停后时间轴可精确显示闭眼；停止复位到 0；拖动后“自由”视角激活。
- 自动化：眨眼调度、互斥可见性、分类镜头焦点及现有预览测试覆盖。

## 技能差距结论

现有 Blender/Three.js 能力足以修复，不需要新增项目专用技能。缺口应留在产品仓库的可复现脚本、manifest 合同和测试中，而不是写入通用技能。
