# Actor 短手臂再生成检查点

用户已确认二维比例方向，授权继续新三维实验并阶段性推送资源。当前节点冻结正/背短手臂候选、原侧面权威图、自然垂臂对照、生成导向图和参数，以及可重放 RGBA。旧 Actor 和绑定文件继续作为对照。

## 节点 01：冻结二维输入

资源在 `milestones/actor_regen_20260909`。`recipe.json` 描述来源、限制和三维参数，`manifest.json` 校验资源和执行代码；文本按 LF 归一化校验，兼容 Windows checkout。

新生成侧图的脚边存在 5 像素暗孔，未放宽原检查，改用此前验证的侧面图。左视图仍是右侧镜像，包含镜像照明，不能当独立证据。自然垂臂图是比例示意，不是已证明与 T 姿势完全同构的三维。

人工 RGBA 检查发现旧预处理把背面浅色高光误删成脑壳缺口，虽然旧结构检查报告通过。新增独立 `prepare_actor_regen_inputs.py`，不修改旧检查点的算法：只在上部 60% 高度恢复明亮、有色、接近主体色相的连通像素，RGB 和下部遮罩不变。当前背面恢复 15,351 像素，为原前景的 10.8%；限定此类候选，12% 预算，不宣称通用。增加脑壳逐行连续性检查，回归覆盖真实高光缺口和应拒绝的灰色缺口。

```powershell
python tools/model_test/actor_regen_checkpoint.py verify
python -m unittest discover -s tools/model_test -p test_actor_regen_inputs.py -v
python tools/model_test/actor_regen_checkpoint.py prepare --output workspace/regen_replay_inputs
```

`prepare` 拒绝覆盖，重放结果必须与冻结四张 RGBA 的 SHA256 完全相同。依赖 numpy、Pillow、OpenCV，换机不需要旧 `workspace`。

## 三维实验与后续门

按 [环境发现](ENVIRONMENT.md) 使用 Hunyuan Python、Hunyuan3D-2 源码和 Hunyuan3D-2mv 权重：

```powershell
python tools/model_test/actor_regen_checkpoint.py generate --output workspace/regen_replay_shape
```

需要时加 `--cpu-offload`。权重不重复提交 Git；冻结输入和输出检查点可直接查看。不同 GPU/依赖的推理不保证逐字节一致，应重新检查结构和视觉。

新模型需先通过头部/手脚视觉、单连通、封闭、Euler=2、双脚切片分离，再进行独立 AccuRIG。不能把旧 Actor 的绑定当成新模型已标定，也不能用静态检查声称走路自然。
