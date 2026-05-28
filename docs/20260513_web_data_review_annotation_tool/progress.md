# Progress

## 2026-05-13
- Created documentation workspace for web data review and annotation tool.
- Inspected migrated `dexechain/data/scripts/umi2hdf5` conversion, replay, and reachability filtering scripts.
- Inspected LeForge Panel viewer, static Three.js robot viewer, Streamlit conversion UI, URDF scene helper, and postprocess README.
- Drafted the complete requirements document and README.
- Validated the generated document structure and core workflow coverage.
- Added follow-up requirements for modular implementation, per-module validation, generic raw data adapter abstraction, PIKA adapter, dependency isolation from dexechain/embodichain, and future standalone IK direction.
- Added output-side exporter abstraction, including `EpisodeExporter`, first `HDF5EpisodeExporter`, exporter tests, and the standard `RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter` conversion chain.
- Updated reachability design to use `ReachabilityBackend` base class plus `PiperDexechainReachabilityBackend` first implementation, matching the input adapter and output exporter extension pattern.
- Incorporated user annotations into the main requirements document as confirmed decisions.
- Split phase work and acceptance criteria into standalone phase documents from Phase 00 to Phase 07.
- Updated README with phase document links.
- Implemented Phase 00 in `/home/dex/app/UniVis` with FastAPI, React static frontend, fake `PolicyEpisode` APIs, uv dependency management, and smoke tests.
- Split Phase 001 for viewer UI polish and implemented the first UI pass: client-side directory picker, registered input/output format selectors, collapsible scrollable episode list, conversion-status colors/progress, autoplay speed controls, and annotation button layout fixes.

## 2026-05-14
- Confirmed documentation has moved into `/home/dex/app/UniVis/docs`.
- Implemented Phase 01 core abstractions: `RawEpisodeAdapter`, `EpisodeExporter`, `ReachabilityBackend`, component registry, fake adapter, mock exporter, and mock reachability backend.
- Added `PolicyEpisode` validation for frame count, contiguous indices, timestamp order, unique camera keys, and reachability overlay length.
- Added Phase 01 tests covering model validation, mock adapter/exporter/reachability flow, and registry payload generation.
- Started Phase 02 HDF5 support with `HDF5EpisodeAdapter`, `HDF5EpisodeExporter`, qpos serialization helpers, HDF5 prompt writeback, registry integration, and round-trip tests.
- Added runtime `EpisodeSession` source context and `/api/source`, allowing the same viewer endpoints to switch between fake data and server-local HDF5 files/directories.
- Reframed source loading direction: formal user flow should be browser directory selection plus file upload to server staging, not manual server path entry.
- Marked current server-path HDF5 source switch as a development/debug shortcut to be replaced or hidden after upload session support lands.
- Implemented browser directory upload path for HDF5 review: `UploadManager`, `/api/uploads/*`, staging reconstruction with relative paths, frontend Upload button, and API tests that scan uploaded HDF5 through `HDF5EpisodeAdapter`.
- Implemented Phase 02c first pass for script-compatible HDF5 image serving: the API now reads `observations/images/<camera>/<chunk_id>` with `<camera>_index` and `<camera>_start`, expands BHW chunks to image frames, and returns real PNG frames for HDF5 sources instead of fake SVG placeholders.
- Added tests that build a `pika_raw_to_compressed_hdf5.py`-compatible HDF5 fixture and verify source switching, upload staging, metadata, trajectory, annotation writeback, and raster frame serving.
- Added adapter-level source validation plus `/api/source/validate`, and wired upload completion to reject input format mismatches before switching the active viewer source.
- Updated the browser directory picker path to prefer `showDirectoryPicker()` so HDF5 selection can inspect only top-level files before upload, avoiding recursive full-tree scans when a user accidentally chooses a large root directory.
- Removed the fake adapter and generated fake image fallback from the runtime app. The UI now starts with no selected source and only registers `HDF5EpisodeAdapter` as an input adapter.
- Added `h5ffmpeg` to the uv-managed runtime dependencies and smoke-tested real PIKA HDF5 image serving against `/Users/admin/CS_Engineering/Repositories/Development/dataset/sort_book_0509_right_only/pos1`.
- Added persistent upload manifests plus `/api/uploads/sources` and source activation APIs, so completed browser uploads can be listed and reloaded after page refresh or server restart instead of being uploaded again.
- Added frontend controls for choosing either a top-level HDF5 directory or a single HDF5 file, plus a visible source validation error panel.
- Reverted the main viewer playback path to stable single-frame image requests after the first batched prefetch pass showed incomplete later-episode loading. Batched image prefetch is now tracked as a future optimization rather than the default playback path.
- Phase 02 remaining work: decide how `PolicyEpisode` should carry or reference image payloads before implementing real image export from `HDF5EpisodeExporter`.

## 2026-05-15
- Started Phase 03 PIKA raw adapter implementation. Current target is a minimal but testable adapter path: scan PIKA raw episode directories, synchronize the same qpos frame rows as `pika_raw_to_compressed_hdf5.py`, expose camera frames through adapter frame APIs, and write annotation updates back to `instructions.json`.
- Implemented Phase 03 first pass: `PikaRawEpisodeAdapter`, PIKA manifest scanning, converter-compatible synchronization, standalone SE(3) helpers, raw image frame serving, and `instructions.json` annotation writeback.
- Registered `PikaRawEpisodeAdapter` in the runtime component registry and generalized annotation writeback through the base adapter interface instead of hard-coding HDF5 in `EpisodeSession`.
- Updated frontend source selection so non-HDF5 adapters can recursively upload browser-selected directories, while HDF5 remains top-level-only for safety.
- Added PIKA raw fixtures and tests for adapter loading, frame serving, instruction writeback, and upload activation.
- Verified with `pytest` (`19 passed`), `compileall`, `node --check`, file line-count scan, and a real `/home/dex/app/tmp/pika_demo` adapter smoke test.
- Decided to add named workspace local-first mode because PIKA raw directories exceed multipart file-count limits and server/client are expected to run on the same host.
- Implemented named workspace local-first source flow: `WorkspaceManager`, `/api/workspaces` browsing APIs, `/api/workspaces/source` activation, CLI `--workspace NAME=PATH`, and frontend workspace selector with visible mode text.
- Kept upload as fallback, but workspace mode is now the recommended path for PIKA raw because it avoids multipart file-count limits and supports refreshing newly collected episodes.
- Added workspace tests for HDF5 activation, PIKA raw activation, path escape rejection, and CLI workspace parsing; verified `pytest` (`23 passed`), `node --check`, `compileall`, and file line-count scan.
- Refined workspace source UI after real use: workspace directory listings now select the first entry in React state instead of only visually showing it, so `Use selected` submits `pos1/pos2` instead of the parent directory. Upload fallback is collapsed behind `Show upload tools` by default. Raw workspace adapter auto-detection is intentionally deferred; users should still select `PIKA Raw` manually for raw directories.
- Moved `Input format` above workspace selection so users choose adapter intent before choosing a local path. Added source revision reload semantics and frame URL cache busting so switching between sources with the same episode id still reloads PIKA metadata and triggers frame requests.
- 修复 PIKA raw 自动播放时画面不更新的 bug。根因是 `get_camera_frame` 每次请求都调用 `load_episode()` 重建全部 PolicyFrame 对象（冗余校验），且 `image_file_to_png` 将 JPEG 强制重编码为 PNG（体积膨胀 4 倍、耗时 ~65ms/帧）。修复：`EpisodeSession` 增加 episode 缓存（`_episode_cache` / `_metadata_cache`），`PikaRawEpisodeAdapter.get_image_frame` 改为使用 `serve_image_file` 原样透传 JPEG/PNG，`get_camera_frame` 响应头加入 `Cache-Control: max-age=0, must-revalidate`。优化后单帧响应从 ~65-130ms 降至 ~1ms，图片体积从 ~414KB 降至 ~107KB，`pytest` 保持 23 passed。

## 2026-05-16
- Read `docs/AGENT.md` and aligned the next implementation with the project rules: keep behavior behind classes/abstractions, keep network/UI simple, and keep touched files at or below 250 lines.
- Implemented adapter-backed image-preserving HDF5 export. `HDF5EpisodeExporter` now accepts an optional `RawEpisodeAdapter` plus `EpisodeSource`, fetches synchronized camera frames lazily, and writes script-compatible chunked datasets under `observations/images`.
- Added a PIKA raw -> HDF5 export regression test that loads raw data through `PikaRawEpisodeAdapter`, exports with real images, reloads through `HDF5EpisodeAdapter`, compares qpos, and checks exported image pixels against the synchronized raw source frame.
- Decoupled frontend source selection from concrete adapter names. The registry now exposes `ComponentInfo.capabilities.source`; UI directory/file upload behavior uses those capability flags instead of hard-coding HDF5 or PIKA adapter ids.
- Added registry tests for source capabilities and verified targeted Phase 02/03 coverage with `pytest` (`14 passed`), `node --check`, and `compileall`.

## 2026-05-18
- 对比确认 UniVis `CompressedHDF5Schema` 与 embodichain `compressed_hdf5.py` 格式一致：chunk 侧表 (`{camera}_index`/`_start`)、BHW→BHWC 变换、h5ffmpeg x264 压缩参数均匹配。两者 GPU 检测逻辑有差异（codec.py 仅检查 RTX 3060，embodichain 支持更多 GPU），但不影响解码。
- 修复 HDF5 连续播放卡顿问题。Profiling 发现瓶颈不在 h5ffmpeg 解压（~22ms/chunk, 5帧），而在 PIL PNG 编码（~35ms/帧，占总耗时 60%）。优化方案：
  1. `HDF5EpisodeAdapter` 增加 chunk 缓存（`_chunk_cache`），解码后的 BHWC chunk 缓存复用，消除同 chunk 内重复的 h5ffmpeg 解压
  2. `CompressedHDF5Schema` 新增 `encode_frame_preview()`，用 JPEG q85 替代 PNG 编码，耗时从 35ms 降至 3ms（11x），体积从 327KB 降至 56KB（6x）
  3. `RawEpisodeAdapter` 基类增加 `clear_caches()` 钩子，`EpisodeSession.set_source()` 时调用，确保切数据源时释放缓存
  4. `PikaRawEpisodeAdapter` 同步实现 `clear_caches()`
- 优化后 HDF5 帧服务时间从 ~85-94ms 降至：同 chunk 内 ~7ms，跨 chunk 首次 ~30-39ms。测试保持 26 passed。
- Closed the first raw review -> HDF5 workflow loop: PIKA raw annotation now persists full `Annotation` state in `instructions.json` under `univis_annotation`, while preserving legacy prompt writeback.
- Added `ConversionService`, `ConversionRouter`, `/api/conversions/episodes/{episode_id}`, and `/api/conversions/accepted`; conversion writes output artifacts plus `conversion_report.json`.
- Added frontend conversion controls for `Export current` and `Export accepted`, using the selected registry output exporter rather than a hard-coded exporter id.
- Added conversion workflow tests for raw annotation/review -> single HDF5 export and accepted-only batch export.
- Optimized long-running UX: workspace directory browsing and source activation now show a loading mask, and conversion runs as background jobs with `/api/conversions/jobs` polling plus a bottom-right export records panel and progress bars.
- Replaced the source-panel-local loading mask with a full-screen overlay mounted at `document.body`, so `Open`, `Use current`, `Use selected`, upload completion, and uploaded-source activation show an unmistakable loading state while the backend resolves directories or episode metadata. Static asset query strings were bumped to avoid stale frontend code.
- 新增 LeRobot v3 数据格式支持（adapter 侧）。创建 `formats/lerobot_v3/` 包（schema.py + adapter.py + `__init__.py`），可读取 LeRobot v3.0 数据集目录：通过 meta/episodes parquet 获取 episode 边界，从 data parquet 读取 10D observation.state，pad 到 20D qpos（单臂数据兼容双 PolicyEpisode），用 ffmpeg 批量提取 MP4 episode segment 帧并缓存在内存中，标注保存到 `univis_annotations.jsonl` 侧文件。AV1 编码的 MP4 无法通过 pyav 精确定位，故采用一次性批量解码方案（首个帧 ~370ms，后续帧 < 1ms 缓存命中）。添加 `av` 和 `pyarrow` 依赖。注册到 `formats/__init__.py` 和 registry 测试。
- 编写《如何新增数据集格式》指南文档（`08_how_to_add_format.md`），涵盖格式分析、schema 设计、adapter 实现、缓存策略、单臂适配、注册步骤、测试、capabilities.source 标志等完整流程。
- Scoped annotation save feedback to the currently selected episode by splitting annotation UI into `annotation_components.js`; switching episodes now clears the local "Annotation saved" message.
- Changed episode-list status colors/text to use the adapter-agnostic `PolicyEpisodeMetadata.annotation.review_status` contract. Adapters without native review metadata can still return the default `Annotation(review_status="pending")`, while adapters that support persistence save through their own `update_annotation()` implementation.
- Remaining next step: perform stricter legacy converter regression for PIKA raw synchronization, add review-status list filtering, and add conversion overwrite/skip controls plus richer progress display.

## 2026-05-17
- Refactored HDF5 support into the `univis.formats.compressed_hdf5` subpackage. The package now owns its schema helpers, h5ffmpeg codec profile, adapter, exporter, and component bundle entrypoint.
- Added `univis.formats.load_format_components()` so the app can load format packages without hard-coding adapter/exporter modules in the application factory. Old `univis.adapters.hdf5` and `univis.exporters.hdf5` modules are now thin compatibility imports only.
- Tightened HDF5 support around the dexechain compressed HDF5 contract: required root datasets are `observations/qpos`, `action`, `chunks`, `language_prompt`, plus strict chunked image groups under `observations/images/<camera>/<chunk_id>` with `<camera>_index` and `<camera>_start`.
- Changed HDF5 export to write actual dexechain-style h5ffmpeg video chunks through an internal `DexH5FFmpegCodec` instead of gzip image chunks. The codec mirrors dexechain's x264 defaults and keeps RTX 3060 NVENC selection as a codec strategy rather than a superclass dependency.
- Removed core-session coupling to the HDF5 class by replacing `isinstance(HDF5EpisodeAdapter)` conversion status logic with adapter capability metadata.
- Updated HDF5 tests to reflect compressed video behavior: exporter tests now use adapter-backed fixture images, and image comparisons allow small x264 loss instead of expecting byte-identical pixels.

## 2026-05-28
- Added CLI-configured export root support through `--output PATH`. Conversion API/UI now resolve browser-entered output values as safe relative subpaths below the configured root instead of accepting arbitrary absolute output paths.
- Added `/api/conversions/config`, `OutputRootManager`, frontend output-root display, and conversion request `output_subpath` wiring for single and accepted-only export jobs.
- Updated the browser tab title to `UniVis version 0.1`.
- Rewrote `README.md` as a user-facing guide covering project goals, architecture, installation, workspace/output startup, source selection, annotation, batch export, screenshot placeholders, testing, and future extensibility.
- Verified with full pytest (`42 passed`), frontend `node --check`, and Python `compileall`.
- Updated `run.sh` to use `--output /home/dex/app/UniVis/output` instead of registering output as a data workspace.
