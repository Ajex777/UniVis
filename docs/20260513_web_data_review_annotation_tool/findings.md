# Findings

## Current umi2hdf5
- `pika_raw_to_compressed_hdf5.py` converts raw PIKA episode directories to compressed HDF5. Output schema includes `observations/images/{cam_left_wrist,cam_right_wrist}`, `observations/qpos`, `action`, `language_prompt`, and `chunks`.
- The converter already supports batch root mode, single episode mode, camera/pose tolerance, min frames, chunk sizing, downsample rate, gripper normalization, and `conversion_report.json`.
- `data_replay.py` loads HDF5 directories, decodes ffmpeg-compressed image chunks through `h5ffmpeg`, displays wrist cameras, qpos trajectory, gripper curves, and reads `filter_report/filter_report.json` to overlay unreachable frames.
- `data_filtering.py` already contains a server-side reusable reachability path: `PiperKinematicsBackend`, candidate start pose search, per-frame dual-arm IK, and output `filter_report.json`.

## LeForge Reference
- `visualize_lerobot_v30_panel.py` is a useful web-style reference: Panel app, dataset selectors, episode slider, Plotly trajectory, cached episode context, parallel video frame extraction via ffmpeg, and camera layout logic.
- `teleop_robot_viewer.py` + `teleop_viewer_static/teleop_robot_viewer.html` provide an iframe-based Three.js viewer. Python sends scene and state JSON to the iframe via `postMessage`.
- `robot_urdf_scene.py` parses URDF meshes and computes FK-style link transforms for web rendering.
- `easy_transfer_streamlit2026.py` is a reference for UI-driven conversion with parameter forms, logs, multi-step conversion modes, and command execution.
- `lerobot_postprocess` is a reference for pipeline-style processing with transform roles, planning/apply phases, and final materialization.

## Design Implications
- The web tool is feasible as a server-client app. IK should live on the Python server because it depends on existing Piper controller/sim-only runtime, robot config, numpy/scipy/torch, and potentially headless rendering/runtime constraints.
- Frontend should treat IK as a job/result overlay rather than a synchronous browser calculation.
- The existing HDF5 `filter_report` contract can be preserved as the first reachability result format, so both CLI and web viewers share the same interpretation.
- Future implementation should be modular and testable module-by-module. HDF5 IO, raw data adapters, annotation store, conversion jobs, and reachability jobs should each have independent smoke tests before being wired into the web UI.
- Raw data support should go through a generic UMI/eef pose `RawEpisodeAdapter` interface. PIKA raw data is the first concrete adapter, and future data formats should be able to reuse the same viewer by implementing the adapter contract.
- Output support should mirror raw input support with an `EpisodeExporter` interface. The first concrete exporter should be `HDF5EpisodeExporter`, while future exporters can target LeRobot, debug JSON/NPZ, or preview video packages without changing raw adapters.
- Long-term architecture should avoid direct dependencies on `dexechain`/`embodichain` in core modules. Existing code can be reused through a temporary compatibility layer while core data structures, web APIs, and adapter interfaces stay independent.
- Reachability should follow the same base-class-plus-implementation pattern. The first implementation can be `PiperDexechainReachabilityBackend`, while future standalone IK or URDF-based backends can implement the same `ReachabilityBackend` contract.
- User decisions clarified the first implementation path: FastAPI + React, fake `PolicyEpisode` viewer first, then core abstractions, then HDF5 adapter/exporter, then PIKA raw adapter.
- HDF5 is an exporter/adapter format, not the in-memory representation. The viewer should consume `PolicyEpisode` regardless of whether the data came from raw PIKA or HDF5.
- Annotation language prompts should be written back to the source format: `instructions.json` for raw PIKA and `language_prompt` for HDF5.
- First version supports variable image observation camera streams, but action/state is fixed to dual-arm eef pose + gripper.
