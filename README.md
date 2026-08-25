# AssetsStudio

AssetsStudio 是一个通用、本地优先的美术素材供给实验室。BombAdventure（`ba`）是当前消费者标签，不是 Studio 的项目边界。

当前唯一生产链：

`StyleProfile → 风格种子 → 无部件 Actor Core → Hunyuan3D 形体 → 手工 AccuRIG → Slot 部件 → Recipe/组合预览`

旧 Actor、完整角色直出、GarmentCode 扫参、历史 Gallery 与失败候选已从当前工作树移除；精确历史仍可从 Git 恢复。

## 启动

双击 `start-local-generation-studio.bat`，或：

```powershell
.\start-local-generation-studio.bat --no-open
```

入口会搜索 ComfyUI 与 Python，并检查 FLUX.2 Klein 所需模型。Studio 地址是 `http://127.0.0.1:4173/`。

## 当前文档

- [当前工作流](docs/CURRENT_WORKFLOW.md)
- [环境发现与模型](docs/ENVIRONMENT.md)
- [AccuRIG 手工交接](docs/ACCURIG_HANDOFF.md)
- [本地资产生命周期](docs/ASSET_LIFECYCLE.md)

## 验证

```powershell
python .\tools\build_studio_style_slot_registry.py
python .\tools\validate_style_slot_profiles.py
python .\tools\validate_accessory_generation_contract.py
python .\tools\validate_studio_local_generation.py --check-models
cd .\studio
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

`workspace/`、模型权重和第三方运行时均保持本地，不上传 Git。
