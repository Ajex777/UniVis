# Phase 05: Conversion Workflow

## Goal

实现单条和批量转换任务。转换链路统一为 `RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter`，第一版 exporter 只实现 HDF5。

## Scope

- 单条转换：当前 episode 导出 HDF5。
- 批量转换：按 accepted 状态筛选后导出。
- 支持跳过已存在文件或覆盖。
- 记录转换参数、输入路径、输出路径、成功/失败原因。
- 输出 `conversion_report.json`。
- 前端显示转换进度和日志。

## Acceptance

- 可从 PIKA raw episode 单条导出 HDF5。
- 可从 accepted episode 批量导出 HDF5。
- 导出的 HDF5 能由 `HDF5EpisodeAdapter` 再读回并可视化。
- 转换失败不会中断整个批次，失败原因可在 UI 和 report 中查看。
- 第一版不出现 LeRobot 参数入口。

## Tests

- Single conversion smoke test：raw -> PolicyEpisode -> HDF5。
- Batch conversion smoke test：多 episode，包含成功和失败样例。
- Report test：`conversion_report.json` 字段完整。
- Viewer regression：导出后立即用 HDF5 adapter 加载。

## Out Of Scope

- 不实现 LeRobot exporter。
- 不做分布式任务队列。
- 不做片段级转换。
