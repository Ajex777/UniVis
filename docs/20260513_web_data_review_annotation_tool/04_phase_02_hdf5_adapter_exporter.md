# Phase 02: HDF5 Adapter And Exporter

## Goal

实现 `HDF5EpisodeAdapter` 和 `HDF5EpisodeExporter`。HDF5 不作为前端特殊数据源，而是通过 adapter 读成 `PolicyEpisode` 后复用同一套可视化界面。

## Scope

- `HDF5EpisodeAdapter` 读取当前 compressed HDF5 schema，并输出 `PolicyEpisode`。
- `HDF5EpisodeExporter` 从 `PolicyEpisode` 写出当前 HDF5 schema。
- 支持可变相机数，不只写死左右腕相机。
- 支持读取和直接回写 HDF5 `language_prompt`。
- 保持对当前 `h5ffmpeg` 压缩 HDF5 的兼容。
- 建立小型 HDF5 fixture 用于导入/导出回归测试。

## Acceptance

- 给定现有 HDF5 文件，adapter 能输出帧同步的 `PolicyEpisode`。
- 给定 fixture `PolicyEpisode`，exporter 能写出可被 adapter 再读回的 HDF5。
- 读回后的 frame count、camera keys、qpos/action shape、language prompt 与输入一致。
- 修改 HDF5 语言标注后，重新打开文件能读到新标注。
- 前端 viewer 可以通过 `HDF5EpisodeAdapter` 查看真实 HDF5。

## Tests

- Round-trip test：`PolicyEpisode -> HDF5 -> PolicyEpisode`。
- Existing-data smoke test：选择一条现有 HDF5，验证 metadata、frame、trajectory API 正常。
- Prompt writeback test：修改 `language_prompt` 后重新读取。

## Out Of Scope

- 第一版不实现 LeRobot exporter。
- 不要求批量转换。
- 不做手动裁剪片段。
