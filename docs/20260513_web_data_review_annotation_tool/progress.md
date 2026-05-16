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
- Closed the first raw review -> HDF5 workflow loop: PIKA raw annotation now persists full `Annotation` state in `instructions.json` under `univis_annotation`, while preserving legacy prompt writeback.
- Added `ConversionService`, `ConversionRouter`, `/api/conversions/episodes/{episode_id}`, and `/api/conversions/accepted`; conversion writes output artifacts plus `conversion_report.json`.
- Added frontend conversion controls for `Export current` and `Export accepted`, using the selected registry output exporter rather than a hard-coded exporter id.
- Added conversion workflow tests for raw annotation/review -> single HDF5 export and accepted-only batch export.
- Optimized long-running UX: workspace directory browsing and source activation now show a loading mask, and conversion runs as background jobs with `/api/conversions/jobs` polling plus a bottom-right export records panel and progress bars.
- Replaced the source-panel-local loading mask with a full-screen overlay mounted at `document.body`, so `Open`, `Use current`, `Use selected`, upload completion, and uploaded-source activation show an unmistakable loading state while the backend resolves directories or episode metadata. Static asset query strings were bumped to avoid stale frontend code.
- Scoped annotation save feedback to the currently selected episode by splitting annotation UI into `annotation_components.js`; switching episodes now clears the local "Annotation saved" message.
- Changed episode-list status colors/text to use the adapter-agnostic `PolicyEpisodeMetadata.annotation.review_status` contract. Adapters without native review metadata can still return the default `Annotation(review_status="pending")`, while adapters that support persistence save through their own `update_annotation()` implementation.
- Remaining next step: perform stricter legacy converter regression for PIKA raw synchronization, add review-status list filtering, and add conversion overwrite/skip controls plus richer progress display.
