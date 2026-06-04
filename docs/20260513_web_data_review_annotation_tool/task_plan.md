# Web Data Review Annotation Tool Plan

## Goal
整理一份面向网页端数据可视化、审查、语言标注、转换、二次可视化、轨迹可达性筛选的完整需求文档，供后续迭代澄清。

## Phases
| Phase | Status | Notes |
| --- | --- | --- |
| Inspect current umi2hdf5 scripts | complete | Read migrated conversion, replay, filtering entrypoints. |
| Inspect LeForge reference | complete | Focused on Panel visualizer, static Three.js robot viewer, Streamlit conversion UI, postprocess pipeline. |
| Draft requirements document | complete | Included user flows, architecture, data model, APIs, IK feasibility, milestones, open questions. |
| Validate and summarize | complete | Checked generated docs and report paths. |
| Incorporate user annotations | complete | Converted answers into confirmed decisions and split phase work/acceptance into standalone docs. |
| Phase 00 fake viewer | complete | Built FastAPI + React fake `PolicyEpisode` viewer in `/home/dex/app/UniVis`. |
| Phase 001 viewer polish | complete | Added directory picker placeholder, component-driven format selectors, episode status/progress list, autoplay, and layout fixes. |
| Phase 01 core abstractions | complete | Added adapter/exporter/reachability base classes, mock implementations, registry, model validation, and tests. |
| Phase 02 HDF5 foundation | complete | Round-trip adapter/exporter, prompt writeback, browser upload, script-compatible image serving, and adapter-backed image export are implemented. |
| Phase 03 PIKA raw adapter | in progress | First adapter pass, named workspace local-first source flow, and PIKA raw -> HDF5 image-preserving export are implemented. Legacy converter regression remains. |
| Phase 04 annotation review | in progress | Prompt/status/notes/tags persist for PIKA raw and HDF5 through adapter writeback; list filtering remains. |
| Phase 05 conversion workflow | in progress | Background single current-episode and accepted-only batch conversion APIs/UI are implemented with job progress and `conversion_report.json`; overwrite/skip options remain. |
| Phase 08 trajectory quality DTW | in progress | First implementation pass added `univis.quality` DTW backend, quality APIs, Quality/DTW UI block, 3D current/reference overlay, draggable metrics popup, and selected stats popup. Needs real dataset UX verification. |

## Decisions
| Topic | Decision |
| --- | --- |
| Doc location | `/home/dex/app/UniVis/docs/20260513_web_data_review_annotation_tool/` |
| Output language | Chinese, because the product discussion is in Chinese. |
| DTW integration boundary | DTW quality evaluation consumes `PolicyEpisode` and stays independent from PIKA/HDF5/LeRobot format adapters. |

## Errors Encountered
| Error | Attempt | Resolution |
| --- | --- | --- |
| Phase03 unit test expected frame count | First run expected 4 frames after trimming | Fixture actually keeps 6 frames with converter-compatible trim logic; updated assertion to match behavior. |
| Registry test still expected only HDF5 adapter | Full test run after PIKA registration | Updated registry expectation to include PikaRawEpisodeAdapter. |
