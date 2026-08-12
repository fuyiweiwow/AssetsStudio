# F006 Actor 专用 GarmentCode 短袖

- 状态：provisional
- 当前候选：`workspace/garmentcode_restart_actor_length_0p90_repro_v1/actor_transfer_native_weight_mix_v3/`

## 目标

用当前非标准 Actor 的完整参数生成自然短袖，而不是在 Actor 表面复制硬壳或修改 demo 衣服。

## 当前结果

0.90 衣长候选已完成 GarmentCode 衣片、Actor 碰撞静态仿真、精确 panel membership 和 Actor 原生权重混合转移。人工四向预览外观可接受，袖子随人物运动；自动物理报告仍记录 1184 个自相交和 326 个碰撞弹簧，因此尚不是发布里程碑。

## 下一门槛

仅允许围绕肩袖/袖口局部自相交做 GarmentCode 版型或仿真参数实验。不得再次启用已删除的硬壳、重叠补袖、全局下摆缩短或 demo 尺寸路线。每个新候选必须相对 0.90 基线同时报告静态物理数据和四向 Actor 动画。

工作流和失败边界见 [`../WORKFLOW_TOPS.md`](../WORKFLOW_TOPS.md)。
