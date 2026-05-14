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
