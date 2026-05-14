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
- Phase 02 remaining work: decode/serve real compressed image frames; current HDF5 viewer path shows trajectory/metadata and generated camera placeholders.
