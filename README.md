# AssetsStudio

AssetsStudio 是一个通用、本地优先的美术素材供给实验室。BombAdventure（`ba`）是当前消费者标签，不是 Studio 的项目边界。

当前唯一生产链：

`StyleProfile → 风格种子 → 无部件 Actor Core → Hunyuan3D 形体 → 手工 AccuRIG → 动作库适配/变形 QA → Slot 部件 → Recipe/组合预览`

旧 Actor、完整角色直出、GarmentCode 扫参、历史 Gallery 与失败候选已从当前工作树移除；精确历史仍可从 Git 恢复。

## 启动

双击 `start-local-generation-studio.bat`，或：

```powershell
.\start-local-generation-studio.bat --no-open
```

入口会搜索 ComfyUI 与 Python，并检查 FLUX.2 Klein 所需模型。Studio 地址是 `http://127.0.0.1:4173/`。

两枚当前已批准风格种子随 Git 位于 `references/style_profiles/published_seeds/`。首次在新机器启动 API 时会自动引入本地种子库；模型权重仍需按环境文档从 ModelScope 获取。

## 当前文档

- [当前工作流](docs/CURRENT_WORKFLOW.md)
- [环境发现与模型](docs/ENVIRONMENT.md)
- [AccuRIG 手工交接](docs/ACCURIG_HANDOFF.md)
- [骨骼动画资产与自动适配](docs/ANIMATION_RETARGET.md)
- [本地资产生命周期](docs/ASSET_LIFECYCLE.md)

## 验证

```powershell
python .\tools\build_studio_style_slot_registry.py
python .\tools\validate_style_slot_profiles.py
python .\tools\validate_accessory_generation_contract.py
python .\tools\validate_studio_local_generation.py --check-models --check-local-assets
cd .\studio
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

除 `references/style_profiles/published_seeds/` 中已批准的可移植种子包外，`workspace/`、模型权重和第三方运行时均保持本地，不上传 Git。
