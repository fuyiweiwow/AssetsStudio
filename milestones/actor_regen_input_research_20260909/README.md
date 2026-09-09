# 短臂超 Q 素体：输入清理检查点 1.0.0

2026-09-09 生成，2026-09-10 完成检查与打包。**本包是可复现的研究方法与输入，不是合格角色或 AccuRIG 输入。** 不携带失败 GLB/FBX/Blend、AI 权重、运行环境或旧绑定。

## 阶段结论

脚部 ROI `[290,690,480,734)` 仅清除 alpha 阴影/毛刺：前、右、后移除 217/79/293 像素；RGB 与 ROI 外内容不变，保留原超 Q 比例。前后底边减少一个阴影像素，左侧镜像右侧。每视图限 500 像素，不增加前景。

原生 Hunyuan 会依各视图 alpha bbox 重新裁切。为消除底边一像素变化带来的全图缩放，新增本地 wrapper 锁定原始裁切窗口；未修改冻结生成器或上游环境。基线 RGB、mask、实际模型输入 tensor 和 view order 与原生处理逐值一致；清理图在模型条件图 420 行以上 RGB/mask 完全一致。只有脚部 261/126/338 个条件图 RGB 像素改变。

常规模型 `hunyuan3d-dit-v2-mv`，seed 20260909、40 步、guidance 5、octree 256、chunks 20000、CPU 初始加载 + CUDA offload。在本地 RTX 3060 12GB 完成，无 Image_gen 或模型下载。

固定裁切结果：脚底局部外扩由 0.0127516H 降至 0，正/侧/斜/底视薄片不再可见；前后 IoU 0.93982/0.94312，宽高比偏差 1.71%/1.91%，通过旧门槛。侧向仍偏厚 4.51%，头部沟痕、指状手型和踝部环线仍存在。条件图局部变化不保证生成几何局部不变。

全网格虽闭合且总 Euler=2，仍有两个组件：主体 265,580 面 Euler=0，另有 8 面小组件 Euler=2。**总 Euler=2 不能代替单组件与各组件拓扑检查；仅删除小组件也不合格。** 没有将任何失败网格提升为标定版本。见 `evidence/fixed_crop_audit.json` 与四向、脚部对照图。

原生裁切清理版也消除了薄片，但条件图脚外产生变化，仅作辅助对照。两个同种子清理试验支持保留该输入清理方向，不代表跨种子稳定性或完整模型风格批准。

## 文件范围

- `baseline/`：原始四向 RGBA、清单及预声明尺度/阈值。
- `cleaned_inputs/`：经过检查的四向清理 RGBA；不是新美术权威。
- `fixed_crop_contract.json`：三维实验配方和裁切约束。
- `evidence/`：固定裁切逐像素证明、失败拓扑报告、四向与脚部对比图（仅诊断）。报告中的原机路径为历史来源，不是换机定位方式。
- `manifest.json`：版本与文件 SHA256；文本按 LF 规范化。
- 复现代码位于仓库 `tools/model_test/`，清单同时校验必需依赖。

## 不加载模型的换机重放

环境要求：Python + NumPy/Pillow/OpenCV/trimesh/scipy；实际 Hunyuan 条件图检查还需要其本地 Python 环境及源码（Torch/einops）。使用现有环境文档发现安装，不默认下载。

```powershell
$auditPython = 'workspace/runtime/actor_core_v2/venv/Scripts/python.exe'
$shapePython = 'E:/Env/Hunyuan3D-2.1-venv/Scripts/python.exe'
$shapeCode = 'E:/Env/Hunyuan3D-2'
$out = 'workspace/input_research_replay' # 必须不存在
& $auditPython tools/model_test/regen_research_checkpoint.py verify
& $auditPython tools/model_test/regen_research_checkpoint.py prepare --output $out
# 期待四张清理 RGBA 哈希完全相同；不要求带有本机来源路径的 JSON 字节相同。
& $shapePython tools/model_test/run_regen_fixed_crop.py --authority milestones/actor_regen_input_research_20260909/baseline/input_replay/inputs --candidate "$out/input_replay/inputs" --processor "$shapeCode/hy3dgen/shapegen/preprocessors.py" --audit-output "$out/conditioning_audit"
```

只有 `native_tensor_exact=true` 且所有逐像素/脚外保护检查通过才允许继续实验。检测范围针对这套冻结输入，不是任意图片的通用裁切承诺。

## 重跑三维诊断（预计仍会被门槛拒绝）

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& $shapePython tools/model_test/run_regen_fixed_crop.py --authority milestones/actor_regen_input_research_20260909/baseline/input_replay/inputs --model E:/Env/models/Hunyuan3D-2mv --code-root $shapeCode --subfolder hunyuan3d-dit-v2-mv --device cpu --cpu-offload --front "$out/input_replay/inputs/front.png" --left "$out/input_replay/inputs/left.png" --back "$out/input_replay/inputs/back.png" --input-manifest "$out/input_replay/inputs/input_manifest.json" --output "$out/shape_seed20260909/shape.glb" --manifest "$out/shape_seed20260909/shape.json" --seed 20260909 --steps 40 --guidance-scale 5 --octree-resolution 256
# 失败返回非零，但会保存诊断网格。不能用该返回前生成的文件作为合格模型。
& E:/Env/Blender/blender.exe --factory-startup -b -t 4 --python-exit-code 1 --python tools/model_test/review_actor_regen_blender.py -- --input "$out/shape_seed20260909/shape.glb" --output "$out/review" --contract "$out/preflight.json"
& E:/Env/Blender/blender.exe --factory-startup -b -t 4 --python-exit-code 1 --python tools/model_test/render_actor_foot_review_blender.py -- --input "$out/shape_seed20260909/shape.glb" --output "$out/foot_review"
& $auditPython tools/model_test/audit_actor_regen_review.py --root $out
```

结构检查、侧面比例、头/手/脚局部视觉仍必须全部通过。不能只用 silhouette IoU 或全体 Euler 求和宣布合格。跨设备 GPU 生成不承诺 GLB 字节一致，以参数、输入与重新验证为准。

## 下一步

保留通过的脚部清理，锁定裁切。分别研究头部明暗是否导致沟痕、手部二维投影与侧向厚度；每轮只改变一种假设，所有视角重新检查。尚不启动新 AccuRIG，不复用旧骨架。

用户要求清理不合格内容：仅本次三个实验 GLB 从工作目录移入回收站；原始冻结 2D、已认可旧素体/绑定、用户未提交代码和 stash 均不动。必要失败报告/图片作为研究证据保留。清理清单见 `evidence/cleanup.json`。
