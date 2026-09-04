# Generated Actor seed 20260943 v1

这是 Actor Core 自动生成 V2 的首个可跨机器继续实验检查点，不是已批准资产，也不会被 Studio Gallery 或随机池读取。

## 包含内容

- `source/front_rgba.png`：TripoSG 的单图输入；
- `actor/actor_corrected.glb`：50,000 面、watertight 的校正后静止网格；
- `actor/actor_rigged.glb`：46 骨、最多四权重的独立绑定模型；
- `rig/unirig_skeleton.fbx`：校正后重新预测的一对一骨架；
- `accessory/waist_belt_pouch_fitted.glb`：从既有独立腰带资产重新适配到当前 Actor 的静态候选；
- `preview/`：素体、骨架、腰带静态和压力姿势的四向证据；
- `manifest.json`：输入、版本、指标和所有二进制 SHA-256。

未包含 TripoSG 高模、失败的腰带 v1-v4、虚拟环境或 AI 权重。它们可重新生成，提交只保留继续工作所需的最小资产集。

## 环境恢复

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_actor_core_v2_research.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_unirig_skeleton_research.ps1
```

两个入口均按“显式参数 → 专用环境变量 → `workspace/` → 相邻目录 →用户缓存”搜索环境。权重由 ModelScope 下载：

- `VAST-AI-Research/TripoSG`；
- `VAST-AI-Research/UniRig` 中仅 `skeleton/articulation-xl_quantization_256/model.ckpt`。

只审计而不修改环境：

```powershell
.\tools\setup_actor_core_v2_research.ps1 -CheckOnly
.\tools\setup_unirig_skeleton_research.ps1 -CheckOnly
```

## 当前 Gate

- 形体与封闭减面：通过；
- 有限比例修正：通过，但仍属于人工认可的实验外观；
- 独立骨架与蒙皮：通过；
- 腰带静态相交：通过；
- 腰带单一压力姿势：通过；
- Mixamo walk、完整 Actor 清理、UV/材质和 RTX 3060 真机：未完成。

继续实验时从 `actor/actor_rigged.glb` 开始。若要验证完整可复现性，则使用 `source/front_rgba.png` 和 `manifest.json` 中的参数从 TripoSG 重新生成，不要把本目录模型误当作生成器输入或旧 canonical 模板。
