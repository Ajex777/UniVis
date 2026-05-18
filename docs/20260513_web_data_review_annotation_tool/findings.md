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

## 2026-05-15 PIKA Raw 接入调研
- UniVis 最新文档显示 Phase 02 已完成 HDF5 读取、真实帧按需读取、上传源持久化；剩余重点是 raw adapter 输出 PolicyEpisode 与图像按需 provider 的统一。
- 当前 runtime 只注册 HDF5EpisodeAdapter，EpisodeSession 对 HDF5 annotation writeback 有特判；接入 PIKA raw 需要注册新 adapter，并把 annotation writeback 扩展为 adapter 能力而非继续硬编码。
- HDF5 exporter 已存在，但文档强调不要盲写图像占位；PIKA raw adapter 若要导出真实 HDF5，需要让 PolicyEpisode 或 adapter 暴露图像引用/读取能力。

## 2026-05-15 PIKA Raw 自动播放画面冻结问题修复

### 现象
使用 PIKA raw 数据源自动播放时，画面不更新，浏览器 Network 面板看不到新的 GET 请求。HDF5 数据源无此问题。

### 根因分析
`get_camera_frame` API 处理函数（routes.py:132）每次帧请求都调用 `session.get_metadata()` → `get_episode()` → `adapter.load_episode()`，对 PIKA raw（389 帧）每次创建 389 个 PolicyFrame + 778 个 ArmFrame Pydantic 对象做冗余校验，然后直接丢弃。

同时 `image_file_to_png()` 将 PIKA 原始 JPEG 文件（~100KB）用 PIL 解码→转 RGB→重编码为 PNG（~414KB），单帧耗时 ~65ms。

自动播放 30fps（间隔 40ms）下，3 个机位同时请求图片（~200ms 总耗时），浏览器 HTTP/1.1 连接池（每 host 6 连接）迅速饱和，后续请求排队/被取消，画面永远无法完成加载。

HDF5 能正常工作是因为典型 HDF5 数据 FPS 较低（~12fps，间隔 83ms），且图片体积相近（~327KB），浏览器有足够时间完成请求。

### 修复方案
1. **EpisodeSession 增加缓存**（episode_session.py）: 添加 `_episode_cache: dict[str, PolicyEpisode]` 和 `_metadata_cache`，首次加载后缓存。`set_source()` 和 `update_annotation()` 时清空。
2. **图片原样透传**（image_files.py）: 新增 `serve_image_file()`，检测 JPEG/PNG 后缀并原样返回，避免 PIL 重编码。PIKA raw adapter 改用此函数。
3. **Cache-Control 头**（routes.py）: `get_camera_frame` 响应增加 `Cache-Control: max-age=0, must-revalidate`，禁止浏览器缓存帧图片。

### 效果
| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 单帧响应时间 | ~65-130ms | ~1ms |
| 图片体积 (PIKA) | ~414KB (PNG) | ~107KB (JPEG 原样) |
| get_metadata 开销 | ~4ms/次（重复创建对象） | ~0（缓存命中） |
| 测试 | 23 passed | 23 passed |

## 2026-05-18 HDF5 压缩格式兼容性确认与播放优化

### 格式兼容性
UniVis `CompressedHDF5Schema` 与 embodichain `dexechain/data/data_engine/compressed_hdf5.py` 格式完全一致：

| 特性 | embodichain | UniVis |
|------|-------------|--------|
| Schema | `observations/images/{cam}/` + `{cam}_index`/`_start` | 相同 |
| BHW→BHWC | `to_bhwc()` 3D reshape | 相同 |
| 深度量化 | `uint16_depth()` / `float32_depth()` | 相同 |
| 图片 codec (多数 GPU) | `hf.x264(preset="veryfast", tune="fastdecode")` | `hf.x264(preset="veryfast", tune="fastdecode")` |
| 图片 codec (RTX 3060) | `hf.h264_nvenc()` | `hf.h264_nvenc()` |
| 遮罩 codec | `hf.x264(preset="veryslow", tune="ssim", crf=0)` | 相同 |
| GPU 检测 | 支持 A800/3060/3090/4060/4090/5060/5090/Orin | 目前仅检测 RTX 3060 (`DexH5FFmpegCodec`) |
| 索引表 | `np.array_split` chunk ID/start | 相同 |

GPU 检测范围差异不影响解码——解码时 h5ffmpeg 自动识别压缩参数。

### HDF5 播放卡顿问题

#### 现象
PIKA raw 卡顿修复后，HDF5 数据源连续播放时出现同样的画面卡顿。

#### Profiling
逐个测量帧服务管线各环节耗时：

| 环节 | 耗时 | 占比 |
|------|------|------|
| 读取 index 数组 | ~0.5ms | 1% |
| h5ffmpeg chunk 解压（5帧/chunk） | ~22ms | 22% |
| BHW → BHWC 变换 | ~0.5ms | 1% |
| PIL PNG 编码（640×480） | **~35ms** | **60%** |
| BGR → RGB 复制 | ~1.3ms | 2% |
| 其他开销 | ~10ms | 14% |
| **总计** | **~85-94ms** | |

瓶颈不在 h5ffmpeg 解压，而在 PIL PNG 编码，占单帧总耗时 60%。

另外，每次帧请求都重复解压同一个 chunk（5 帧共 22ms），未利用连续播放的局部性。

#### 优化方案

1. **Chunk 缓存**（adapter.py）: `HDF5EpisodeAdapter` 增加 `_chunk_cache: dict[tuple, np.ndarray]`，解码后的 BHWC chunk 缓存复用。LRU 上限 12 entries（~280MB），连续播放同 chunk 时 h5ffmpeg 解压开销降至 0。

2. **JPEG 预览**（schema.py）: 新增 `encode_frame_preview()`，用 JPEG q85 替代 PNG。JPEG 编码快 11 倍（3ms vs 35ms），体积小 6 倍（56KB vs 327KB）。浏览器 `<img>` 标签原生支持，无需前端改动。

3. **缓存清理钩子**（base.py）: `RawEpisodeAdapter` 基类增加 `clear_caches()`，`EpisodeSession.set_source()` 时调用，确保切数据源时释放旧缓存。

#### 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 同 chunk 帧 | ~85-94ms | **~7ms** |
| 跨 chunk 首帧 | ~85-94ms | **~30-39ms** |
| 图片体积 | ~327KB (PNG) | **~56KB** (JPEG q85) |
| Content-Type | image/png | image/jpeg |
| 测试 | 23 passed | 26 passed |
