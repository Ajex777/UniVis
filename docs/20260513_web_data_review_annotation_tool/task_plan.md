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
| Phase 02 HDF5 foundation | in progress | Round-trip HDF5 adapter/exporter, prompt writeback, and browser directory upload to server staging are complete; real compressed image serving remains. |
| Phase 03 PIKA raw adapter | in progress | First adapter pass plus named workspace local-first source flow are implemented. Real image-preserving HDF5 export remains next. |

## Decisions
| Topic | Decision |
| --- | --- |
| Doc location | `/home/dex/app/UniVis/docs/20260513_web_data_review_annotation_tool/` |
| Output language | Chinese, because the product discussion is in Chinese. |

## Errors Encountered
| Error | Attempt | Resolution |
| --- | --- | --- |
| Phase03 unit test expected frame count | First run expected 4 frames after trimming | Fixture actually keeps 6 frames with converter-compatible trim logic; updated assertion to match behavior. |
| Registry test still expected only HDF5 adapter | Full test run after PIKA registration | Updated registry expectation to include PikaRawEpisodeAdapter. |
