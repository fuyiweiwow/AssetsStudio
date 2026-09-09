# 项目相关 C 盘缓存清理

2026-09-09 已清理约 **40.3 GiB** 可重新下载的 Python 包缓存。没有卸载 Python 环境、删除 AI 模型权重或改动原始绑定文件。

- pip HTTP 缓存：通过 wheel 内部 `METADATA` 确认的 8 个 PyTorch 下载包及配套缓存元数据，共 **14.909 GiB**。删除前逐项验证绝对路径位于 pip 的 `cache/http-v2` 内、不是目录/重解析点且大小与计划一致。
- uv：对固定缓存目录执行 `uv cache clean torch torchvision torchaudio xformers --offline`，工具报告移除 **95,318 个文件、25.4 GiB**。没有使用 `--force`，保留工具的在用检查。
- 清理后 C 盘可用约 **90 GiB**。这是当时磁盘快照，包含其他进程的同期变化，不能把全部可用空间增量都归因于本次清理。
- 清理后现有 ComfyUI Python 成功导入 `torch 2.11.0+cu128`，CUDA 可用；旧脚底检查点 60 文件校验通过，头部修复检查点校验与无模型重放通过。

未清理 Visual Studio 当日更新临时文件、Codex 运行时缓存、现有 GarmentCode 环境、共享模型文件和其他应用内容。包缓存属于共享可下载依赖；本轮仅选择项目明确使用的上述包名，没有全量清空 pip/uv 缓存。

机器本地明细位于 `workspace/maintenance/c_drive_cleanup_20260909/`。uv 的成功统计写入 stderr，被 Windows PowerShell 显示为 `NativeCommandError`；文件移除统计、磁盘空间与随后环境检查确认清理已实际完成。该显示不代表卸载环境失败。

## 避免后续安装继续填满 C 盘

在项目所在盘的 PowerShell 中，安装依赖前执行：

```powershell
. ./tools/use_project_package_cache.ps1
```

它仅为当前会话及子进程设置 `UV_CACHE_DIR` 和 `PIP_CACHE_DIR`，缓存落在项目的 `workspace/runtime/package_cache/`。不修改系统级环境变量，不迁移已有缓存，不影响已安装环境。正常生成/预览不需要下载这些安装缓存。
