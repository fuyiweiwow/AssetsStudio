# Actor Core 离线预处理与结构检查

## 范围和边界

这是现有「风格种子 → 素体图 → Hunyuan 形体」流程中的可重放处理层，不是用规则生成新人体，也不是让聊天模型逐个雕刻模型。当前入口为 `tools/model_test/actor_core_offline.py`，不调用在线图像 API、不下载模型、不启动桌面窗口。

支持的 profile 为 `biped_colored_neutral_v2`：中性背景、着色素体、正交正/背视图、双腿已分开、同画布且高度一致。使用相对比例定位，不包含 Actor93 的顶点索引、脸部坐标或固定图片尺寸。灰度人体、复杂背景、交叉腿、多足、非对称姿态不在当前覆盖范围；判定不足时拒绝，不猜测切割。仍需多种真实 Actor 验证，不能据单个样本宣称通用产线完成。

## 原因与处理规则

旧输入使用 `RETR_EXTERNAL` 后填满外轮廓。暖色地面阴影连接双脚后，原本灰色的腿间背景也变成不透明前景；3D 模型因此收到了错误结构证据。

新流程：

1. 检查背景并按自适应饱和度提取主体。
2. 根据腿部多行截面的相邻轮廓，定位有证据支持的腿间走廊。只清理走廊内向下的遮罩，不缩腿、不改 RGB；删除预算不超过初始前景的 2%。
3. 走廊打开后，保留内部浅色高光：只填不连通外部背景的小面积、有色内部区域，合计不超过前景的 5%。中性/暗色孔洞拒绝；不超过 4 像素的孤立栅格噪声另限总前景 0.01%。禁止再使用外轮廓整体填充。
4. 检查正侧背高度差不超过 2.5%，输出 RGBA、源文件/输出 SHA256 和版本清单。左侧暂镜像右侧，包括照明，仍是限制。
5. 生成前核对清单、profile、文件路径和 SHA256，防止混入旧图或改过的遮罩。
6. 生成后检查单连通、封闭、一致面朝向、Euler=2，并在高度 0.2%、0.5%、1%、2%、4%、8%、12% 检查脚部横截面。它是有限采样的预警，不是无自交或可绑定证明。

结构失败仍保留原始实验输出与报告，但不能入资产库或进入绑定。渲染器的 `BLENDER_MV_PASS` 只表示导入/渲染完成，不覆盖结构失败。脚的美术形状、腋下、面部与源图的差异仍需人工审核。

## 换机运行

先按 [环境发现](ENVIRONMENT.md) 找到已有 Hunyuan Python、源码和拆分权重；激活该 Python 环境后从仓库根目录运行以下命令。没有硬编码本机盘符；代码和模型由 `hunyuan_environment.py` 搜索，必要时设置 `HUNYUAN3D_SOURCE`、`HUNYUAN3D_MODEL_ROOT`。本轮无需 ComfyUI、生图模型或额外下载。

```powershell
python -m unittest discover -s tools/model_test -p test_actor_core_offline.py -v
python tools/model_test/actor_core_offline.py prepare --front <正面图> --right <右侧图> --back <背面图> --output <新的输入目录>
python tools/model_test/actor_core_offline.py generate --inputs <输入目录> --output <新的实验目录> --seed 20260908 --steps 40
python tools/model_test/actor_core_offline.py audit --mesh <实验目录>/shape.glb --report <实验目录>/audit.json
```

`prepare` 和 `generate` 拒绝已存在的输出目录；不要为重跑覆盖旧记录。`generate` 强制传入输入清单，使用本地 Hunyuan3D-2mv、CFG5、octree256；低层脚本无清单模式仅供旧实验兼容。检查失败返回非零；以 JSON 的 `status` 为机器判据，不以是否生成了 GLB 为成功。

本轮 Actor93 源图选择器可重放：

```powershell
python tools/model_test/prepare_actor93_shape_probe.py --output workspace/local_generation/actor_offline_replay/inputs
python tools/model_test/actor_core_offline.py generate --inputs workspace/local_generation/actor_offline_replay/inputs --output workspace/local_generation/actor_offline_replay/run
```

发现 Blender 后，使用其 `--background` 模式运行 `validate_hunyuan_mv_blender.py` 和 `render_actor93_shadowless.py`，详见 [此前对照](ACTOR93_SHAPE_PROBE_20260908.md)。不允许 GUI 回退。`review_offline_actor_inputs.py --before <旧输入目录> --after <新输入目录> --output <png>` 可检查 RGB/Alpha 对照。

## 测试和硬件

8 个单元测试覆盖 18 组尺寸/平移/腿宽组合、RGB 不变、浅色高光、拒绝中性孔洞/复杂背景/无腿缝、清单被篡改、拒绝覆盖，以及三维脚部桥接检测与尺度/平移一致性。解析几何夹具只用于测试检测器，不是生产素体。

预处理用 numpy、Pillow、OpenCV；网格检查另需 trimesh 及其切片依赖，沿用 Hunyuan 专用环境即可。本次 5070 Ti 的 Hunyuan CUDA 分配峰值约 5.43 GiB，并不等于整卡占用，更不是 RTX3060 12GB 的实机验收。`generate --cpu-offload` 可用于后续 3060 验证；在该卡上应单独记录成功率、总显存、耗时与一致性。

## 2026-09-08 对照结果

冻结输入在 `workspace/local_generation/actor_offline_gate_20260908/inputs_v2`，输出在 `run_v2/shape.glb` 和 `run_v2/shape.json`。源图由此前已保存的正面 B、右侧 B、背面 v2 提供，没有新生成二维图。

相同 seed20260908、40步、CFG5、octree256 下，原始新网格为 135098 顶点、270192 面、单连通、封闭、Euler=2、面朝向一致，7 层脚部切片均分离，结构检查全部通过。没有移除碎片、改顶点或手工补洞。旧网格脚底桥接未通过；过渡输入 v1 则因高光孔洞被废弃。

预览仍可见脚缘小凸边与手/肩局部瑕疵；当前停在人工审核，不自动绑定或入库。源图、冻结 RGBA、原始 GLB、生成报告及预览随检查点保存。模型权重继续按环境发现/ModelScope 获取，不提交重复大权重。8 项测试通过仅证明已覆盖案例，不等于所有 Actor 均可用。

## 与 Studio 的关系（集成边界）

这是可由 Studio 子进程调用的离线 CLI/JSON 合同，尚未接入 Studio 页面。调用方必须检查 `status`，失败只进入实验审核，不得自动添加到本地资产库。当前不替换已有生产后端，不触碰 AccuRIG 标定文件。历史 `clean_actor93_cheek_spike.py` 是锁定单一网格的诊断 workaround，未列入新产线；通用毛刺修复、眼部处理、美术形态约束仍未完成。
