## WHY

本次修改主要围绕 DTW 质量检测的 CLI 化、GUI 易用性，以及 format 名称简写能力展开。

1. 新增 `univis-dtw` CLI，用于在不启动 GUI 的情况下执行 DTW 质量检测。
   - `compare`：比较两个 episode，输出 JSON 指标和 PNG 轨迹对比图。
   - `stats`：给定 reference，统计多个 episode 相对 reference 的 DTW 指标。
   - 默认 `input-format` 为 `PikaRawEpisodeAdapter`。
   - 支持 `--input-format` 简写为 `--if`。
   - 输出默认写入 `<source>/dtw/compare` 或 `<source>/dtw/stats`。

2. 抽出 `QualityService`，让 GUI API 和 CLI 复用同一套 DTW 计算逻辑。
   - 避免 GUI 和 CLI 出现两套不同的质量检测实现。
   - `selected_stats` 在后端统一自动排除 reference，避免 reference-vs-reference 的 0 error 影响统计。

3. 新增 DTW 静态图导出能力。
   - CLI `compare` 会额外生成 PNG。
   - PNG 展示 current/reference 双臂轨迹及 DTW 对齐连线。
   - 使用 `matplotlib` 后端渲染，适合纯命令行环境。

4. 为组件增加 alias 机制。
   - `ComponentInfo` 新增 `aliases` 字段。
   - 新增 `ComponentNameResolver`，支持大小写不敏感的 name/alias 匹配。
   - 已支持：
     - `PikaRawEpisodeAdapter` -> `PIKARaw`
     - `HDF5EpisodeAdapter` -> `HDF5`
     - `HDF5EpisodeExporter` -> `HDF5`
     - `LeRobotV3EpisodeAdapter` -> `LeRobotV3`
   - 未知 format 时会打印可用候选项。
   - 自动补全功能已按要求移除，仅保留候选项错误提示。

5. 改进 GUI DTW 体验。
   - `DTW Metrics` 和 `Selected DTW Stats` 指标旁增加 `?`。
   - 鼠标悬浮后显示中文指标解释。
   - 移除浏览器原生 `title` tooltip，避免黑底白字和自定义提示框同时出现。
   - `DTW Metrics` 默认位置调整到右侧轨迹模块左上角。
   - 更新静态资源版本号，避免浏览器缓存旧 JS/CSS。

## TEST

1. 测试了GUI一切功能正常

2. 测试了CLI进行DTW检查