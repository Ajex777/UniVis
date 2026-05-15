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
