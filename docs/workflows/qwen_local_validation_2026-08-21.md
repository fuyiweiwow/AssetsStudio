# Qwen 本地验证记录（2026-08-21）

## 结论

`Qwen-Image` 与 `Qwen-Image-Edit-2511` 的 ModelScope 权重已完整下载并通过本地文件数量、大小和无 `.incomplete` 文件校验，但在当前 Windows + RTX 3060 机器上不应继续使用 57GB safetensors 的 DiffSynth 分层映射。

两次全量加载均触发系统级 `0x1A` 蓝屏。第二次转储报告为 `nt!MiDecrementSubsectionViewCount`，属于 Windows 内存映射视图回收阶段；页面文件从 1GiB 扩容到 64GiB 后仍复现。因此页面文件扩容只能解决 Win32 1455，不能解决当前 Windows 内存映射路径的稳定性问题。

## 已验证内容

- `E:\env\models\Qwen-Image`：约 57.7GB，文件完整。
- `E:\env\models\Qwen-Image-Edit-2511`：约 57.7GB，文件完整。
- RTX 3060 12GiB，CUDA 12.4 探针通过。
- DiffSynth 能完成三组本地权重的模型对象加载。
- 256×256、1 步文字生图未得到有效输出；在进入稳定生成前系统再次蓝屏。

## 事故证据

- 第二次转储：`C:\Windows\Minidump\082026-14406-01.dmp`。
- BugCheck：`0x1A`，WER 名称：`nt!MiDecrementSubsectionViewCount`。
- 此前还出现过 `nvcuda64.dll`、`torch_cpu.dll` Python 崩溃，以及旧的 `0x116` GPU 超时记录。

## 后续方案

1. Windows 本地正式流程停用这两个原始 57GB 权重的 DiffSynth 运行方式。
2. 如需继续本机验证，优先使用 Q4/Q5 量化模型，并通过隔离的 Linux/WSL 环境或 ComfyUI-GGUF 运行；不要直接复用原始 safetensors 分片映射。
3. 在量化路径稳定前，标准件生产继续使用 GPT ImageGen；Qwen 不晋级为默认生图后端。

测试脚本现在默认阻止 Windows 全分片运行；只有显式传入 `--unsafe-windows-run` 才会覆盖保护。
