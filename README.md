# AssetsStudio

AssetsStudio 是从 AssetsLab 的长实验分支整理出的正式资产工作区。它只保存可继续使用的里程碑、重建脚本、人工审查素材和当前工作流；失败参数扫掠与重复试验仍留在原 `AssetsLab` Git 历史中。

当前工作流实际依赖的模型文件会随仓库上传，包括 `.blend`、`.fbx`、动作源、眼睛贴图和鞋源模型，换机后不需要回到 AssetsLab 找模型。第三方鞋源包未附明确许可证，因此远程仓库默认保持私有。

## 当前入口

- 开发原则：[`PRINCIPLES.md`](PRINCIPLES.md)
- 开发管理基准：[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- 产品与技术基线讨论稿：[`docs/PRODUCT_TECH_BASELINE.md`](docs/PRODUCT_TECH_BASELINE.md)
- 美术方向基准：[`docs/ART_DIRECTION.md`](docs/ART_DIRECTION.md)
- 总里程碑清单：[`docs/MILESTONES.md`](docs/MILESTONES.md)
- 迁移边界：[`docs/MIGRATION.md`](docs/MIGRATION.md)
- 静态审查页：[`gallery/index.html`](gallery/index.html)
- 机器可读状态：[`docs/ASSET_STATUS.json`](docs/ASSET_STATUS.json)

## 目录

```text
milestones/
  body/       Actor V1、Walk/Run、眼睛贴图与耳朵源
  hair/       `sources/female|male` 源发型、组件 catalog 与随机池
  body/       Actor、骨架、动作、眼睛纹理、内嵌3D耳朵与 Face 合同
  tops/       当前短袖候选
  pants/      当前 Blender-native 短裤里程碑
  shoes/      已确认的卡通运动鞋 v10
references/   外部参考源与来源清单
tools/        仅保留当前重建、渲染、随机化与 Gallery 工具
docs/         总文档和各类别唯一工作流
gallery/      无需 Blender 即可查看的人工审查入口
workspace/    本地实验输出，不提交 Git
```

## 状态词义

- `accepted`：用户已明确认可，可作为下一阶段正式基线。
- `provisional`：当前最值得继续的版本，但仍带已知视觉缺陷。
- `source_contract`：源资产、随机池或生成接口已经固定，但没有单个“最终造型”。
- `technical_baseline`：技术闭环通过，不等同于最终美术验收。

不要通过自动碰撞统计把 `provisional` 自动提升为 `accepted`。所有衣物与鞋子必须保留人工 GIF 审查。

## 快速检查

```powershell
python .\tools\validate_studio.py
python .\tools\build_studio_gallery.py
```

## 启动 Studio（F001）

第一版 Studio 是 Windows 单用户本地工具。Node.js 与 Blender 可用后：

- 最简单：双击仓库根目录的 `start-studio.cmd`，保持弹出的命令窗口开启；脚本会在服务就绪后打开浏览器。重复双击不会再次启动服务：若检测到 AssetsStudio 已在 `4173` 端口运行，脚本会直接打开现有页面；若该端口被其他程序占用，会明确提示并停止。
- 命令行方式：

```powershell
cd .\studio
npm.cmd install
npm.cmd run dev
```

Studio 不是可以双击或复制 `file://` 地址打开的单个离线 HTML；浏览器的 ES Module、GLB 和 JSON 加载需要本机 HTTP 服务。请使用上述启动入口，再访问 `http://127.0.0.1:4173/`。`npm run dev` 的预启动步骤会从正式状态生成六类前端注册表，并把当前 Actor、短袖、短裤和鞋导出为被 Git 忽略的本地 GLB；发型尚未装入首个组合 GLB，页面会明确禁用该开关。需要只重建本地预览时可运行 `npm.cmd run assets:prepare`。

页面按“选择模型 → 选择骨骼 → 选择动画 → 拼装部件 → 结果预览”工作。当前前三步各只有一套经过登记的选项；拼装、动画控制、时间轴、固定视角与直接拖动旋转已经可用。多模型导入、自动绑定和动画重定向仍是后续功能。

生成新候选时输出到 `workspace/`。只有人工审核通过后，才替换对应 `milestones/<category>/` 内容并更新 `docs/ASSET_STATUS.json`。

开始 Studio 功能开发前，必须先按 `PRINCIPLES.md` 的顺序阅读开发基准、产品技术基线、里程碑和对应功能文档。技术变化、内容删除与重要保存检查点必须同步更新仓库内的追溯记录。
