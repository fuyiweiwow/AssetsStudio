# Gemini 生图 API 可行性调查（2026-08-22）

## 结论

“Gemini 生图 API 可以免费调用”目前不属实。Google AI Studio 网页端可以免费试用部分模型，但当前 Gemini Developer API 的生图模型在官方价格表中均标为 `Free Tier: Not available`。免费 AI Studio 体验不能当作免费、可自动化的生产 API 配额。

本机也没有检测到 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY`，因此本轮没有绑定计费、创建密钥或发起付费生成。

## 官方价格快照

- `gemini-3.1-flash-lite-image`：1K 输出约 `$0.0336 / image`，API 无免费层。
- `gemini-3.1-flash-image`：0.5K / 1K / 2K / 4K 约 `$0.045 / $0.067 / $0.101 / $0.151`，API 无免费层。
- `gemini-2.5-flash-image`：最高 1024 px 约 `$0.039 / image`，API 无免费层。
- Imagen 4 Fast / Standard / Ultra 为 `$0.02 / $0.04 / $0.06`，API 无免费层；官方同时标注 Imagen 4 已于 2026-08-17 停止，不能作为新工作流目标。

官方来源：

- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini image generation API guide](https://ai.google.dev/gemini-api/docs/image-generation)
- [Gemini API billing](https://ai.google.dev/gemini-api/docs/billing)

## 若允许小额付费，建议的实验

1. 先用最低成本的 `gemini-3.1-flash-lite-image` 做 4–8 次风格/比例筛选；只晋级一张 Actor 正面锚点。
2. 将用户认可的比例锚点和默认冒险者服装作为参考图，一次生成同画布的正/侧/背三视图，禁止三个独立无条件请求。固定中性姿态、正交感、同一发型/服装/色板、无道具遮挡。
3. 第二轮使用图像编辑而不是重新文生图，只修正视图对应、耳朵可拆分边界和发型轮廓；不得借编辑改变角色身份。
4. 将结果按现有三视图流程拆分，比较 image_gen 基线：头身比、眼距、肩/胯宽、发型轮廓、服装分件边界和正侧背身份一致性。
5. 只有三视图通过后才送 Hunyuan3D-2MV。生图模型的“好看”不能替代视图注册门禁。

当前决定：保留 `image_gen` 作为正式生图路径；Gemini 仅在用户明确同意计费并提供单独的项目/API key 后进入低成本对照实验。
