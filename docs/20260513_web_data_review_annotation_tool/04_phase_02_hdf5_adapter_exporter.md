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

## Implementation Checkpoints

- Phase 02a：先完成 `PolicyEpisode -> HDF5 -> PolicyEpisode` 闭环、20D qpos layout、camera metadata、reachability metadata、`language_prompt` 读写和 registry 接入。
- Phase 02b：接入浏览器目录选择后的 HDF5 文件上传。前端上传文件内容和 relative path，server 在 staging workspace 重建目录结构后调用 `HDF5EpisodeAdapter` 扫描。当前已完成小型目录的一次性 multipart 上传。
- Phase 02c：再接入当前 compressed HDF5 的图像帧解码/懒加载，避免 HDF5 filter 或 ffmpeg plugin 问题影响 trajectory/metadata 的基础验证。

当前 Phase 02c 实现以 `pika_raw_to_compressed_hdf5.py` 生成结构为准：`observations/images` 下包含 `<camera>_index`、`<camera>_start` 和 `<camera>/<chunk_id>`，chunk 内图像为 BHW/BHWC。Web `/frame` API 按需读取单帧并返回 PNG。`h5ffmpeg` 已加入 uv runtime dependencies，`uv sync` 后可解码真实 ffmpeg-compressed HDF5。

当前主 viewer 播放路径使用稳定的单帧 `/frame` image request。50 帧 batch image API 和前端预取缓存先作为未来优化点保留设计方向；再次启用前需要验证全 episode 缓存淘汰、后半段窗口加载、拖动 seek 和多 camera 同步。

## Upload-Based Source Flow

正式用户路径不要求用户填写 server-local path。设计上应按以下流程实现：

1. 前端通过目录选择控件获取 `.hdf5/.h5` 文件列表和相对路径。
2. 前端创建 upload session，并把文件以 multipart 或分片方式上传给 server。
3. Server 将上传内容落到受控 staging 目录，例如 `.univis/uploads/<upload_id>/dataset_root/...`。
4. Upload complete 后，server 创建 active dataset/source，调用 `HDF5EpisodeAdapter.list_metadata(EpisodeSource(root_path=staging_root))`。
5. Viewer 继续复用 `/api/episodes`、`/metadata`、`/trajectory`、`/frame`、`/annotation`。
6. Server 持久化 completed upload manifest，前端刷新后可通过 uploaded sources 列表重新激活之前上传过的数据集。

当前 `server path` 切源能力仅作为开发调试捷径保留，正式 UI 已转向 upload session flow。

## Tests

- Round-trip test：`PolicyEpisode -> HDF5 -> PolicyEpisode`。
- Upload staging test：上传一个或多个 HDF5 文件后，server 能在 staging 目录扫描出 episode。
- Existing-data smoke test：选择一条现有 HDF5，验证 metadata、frame、trajectory API 正常。
- Prompt writeback test：修改 `language_prompt` 后重新读取。

## Current Notes

- `HDF5EpisodeAdapter` 已支持读取 script-compatible chunked image frame。
- `HDF5EpisodeAdapter` 已支持 source validation：合法输入为单个 `.hdf5/.h5` 文件，或顶层直接包含 `.hdf5/.h5` 文件的目录；暂不支持目录下再嵌套多个 HDF5 子目录。
- 前端优先使用 `showDirectoryPicker()` 选择目录，只枚举顶层条目进行早期校验，避免 `webkitdirectory` 在误选根目录时递归扫描全树。前端同时支持选择单个 `.hdf5/.h5` 文件。
- 浏览器不会提供用户机器上的绝对原始路径，因此 uploaded sources 保存的是用户选择时的显示名、上传时间、文件统计和 server-side staging path。
- `PolicyEpisode` 当前仍主要承载帧同步后的轨迹/action/annotation metadata，图像通过 adapter 按需读取；后续实现 raw adapter 时也应输出帧同步后的 episode，并提供同一帧号下的 image frame provider。
- `HDF5EpisodeExporter` 目前不要盲写图像占位数据；在明确 `PolicyEpisode` 如何携带或引用图像 payload 后，再实现真实图像导出。

## Out Of Scope

- 第一版不实现 LeRobot exporter。
- 不要求批量转换。
- 不做手动裁剪片段。
