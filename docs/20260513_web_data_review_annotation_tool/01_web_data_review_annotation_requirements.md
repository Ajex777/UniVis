# 网页端数据审查、标注、转换与可达性筛选工具需求文档

## 1. 背景

当前 PIKA/UMI 数据处理链路已经具备本地脚本能力：

- 原始 PIKA episode 转 compressed HDF5：`embodichain/dexechain/data/scripts/umi2hdf5/pika_raw_to_compressed_hdf5.py`
- HDF5 本地可视化：`embodichain/dexechain/data/scripts/umi2hdf5/data_replay.py`
- Piper 轨迹可达性筛选：`embodichain/dexechain/data/scripts/umi2hdf5/data_filtering.py`

但 Matplotlib/本地 plot 交互成本较高，不适合作为长期的数据审查与标注入口。新的目标是把“看数据、写语言标注、判定是否保留、转换、复查转换结果、运行 IK 可达性筛选”整合成一个网页端工具。

LeForge 中已有可参考能力：

- `src/visualize_lerobot_v30_panel.py`：Panel 网页式数据可视化、episode 切换、视频帧抽取、Plotly 3D 轨迹、缓存。
- `src/teleop_robot_viewer.py` 与 `src/teleop_viewer_static/teleop_robot_viewer.html`：Python 端通过 iframe/postMessage 驱动 Three.js 机器人视图。
- `tele_to_lerobotv30/easy_transfer_streamlit2026.py`：Web UI 触发多阶段转换、日志显示、参数摘要。
- `lerobot_postprocess/`：面向数据集的 pipeline 式后处理框架。

## 2. 总体目标

建设一个 server-client 结构的数据处理工具，支持：

1. 从原始 PIKA episode 目录或已转换 HDF5 目录加载数据。
2. 在网页端逐条可视化 episode。
3. 在审查时编辑每条 episode 的语言标注、保留状态、备注和问题标签。
4. 支持“审查一条、标注一条、转换一条”的精细流程。
5. 支持跳过可视化，按参数批量直接转换。
6. 支持输入已转换 HDF5，再次进行可视化、复审和可达性查看。
7. 支持在服务端运行 IK/可达性筛选，并把不可达帧回显到网页端。
8. 输出可复现的转换报告、审查报告和可达性报告。

## 3. 可行性结论

整体可行。建议把浏览器端定位为“交互与展示层”，把 HDF5 解码、原始数据同步、转换、IK、报告生成放在 Python server 端。

关键判断：

- HDF5 图像 chunk 依赖 `h5ffmpeg`/HDF5 filter 注册，不适合直接放到浏览器解码；应由服务端解码为 JPEG/PNG/WebP 帧或生成可流式访问的视频片段。
- IK 依赖现有 Piper controller、robot config、numpy/scipy/torch 及可能的 headless runtime，放在 server 端最自然。
- 现有 `data_filtering.py` 已经能生成 `filter_report/filter_report.json`，网页工具可以先复用这个报告格式作为可达性结果。
- LeForge 的 Panel + iframe Three.js 路线可作为 MVP 参考；如果要做长期工具，建议拆成 FastAPI 后端 + React/Vite 前端 + Three.js/Plotly 可视化。

## 4. 用户角色

- 数据审查人员：检查采集质量、填写或修正语言标注、标记是否保留。
- 数据转换人员：配置转换参数，执行单条或批量转换，查看失败原因。
- 机器人/部署人员：运行 IK 可达性筛选，查看不可达帧，决定是否剔除或重采。
- 训练人员：确认最终输出数据集质量，并追踪每条数据的标注与处理状态。

## 5. 输入与输出

### 5.1 输入数据

支持三类输入：

- 原始 PIKA episode 根目录：包含多个 `episode*` 子目录。
- 单个原始 PIKA episode 目录。
- 已转换 HDF5 文件或 HDF5 目录。

当前 HDF5 约定：

- `observations/images/cam_left_wrist`
- `observations/images/cam_right_wrist`
- `observations/qpos`
- `action`
- `language_prompt`
- `chunks`

### 5.1.1 浏览器目录选择与上传策略

正式数据源入口采用“前端选择本地目录，上传给 server，server 在本地 staging workspace 解析”的模式。浏览器不会把用户本机目录的绝对路径可靠暴露给网页，因此不应把手填 server path 作为主产品路径。

推荐流程：

1. 前端使用目录选择控件读取用户选中的目录文件列表，保留每个文件的相对路径。
2. 前端通过 multipart upload 或分片 upload 将文件上传到 server。
3. Server 在受控 staging 目录下重建相对目录结构，并创建 `UploadedDataset` 记录。
4. Server 根据用户选择的 input adapter 调用 `scan/load_metadata/load_episode`。
5. 后续可视化、标注、转换都基于 server staging 中的数据副本进行。

实现注意：

- 上传目录需要保留 relative path，避免丢失 raw episode/HDF5 目录结构。
- 大数据集应支持分片上传、断点/重试、上传进度和取消。
- Server path 输入只可作为开发调试或同机部署的可选快捷方式，不作为默认用户流程。
- 上传后的 staging 数据应有清理策略，避免长时间占用磁盘。

### 5.2 输出数据

工具应输出：

- 审查/标注 sidecar 文件，例如 `review_annotations.json` 或 SQLite 数据库。
- 转换后的 `.hdf5` 文件。
- `conversion_report.json`。
- `filter_report/filter_report.json`。
- 可选的数据集级汇总报告，例如 `review_report.json`。

确认策略：标注状态可以保存在 annotation store 中，但语言标注需要写回数据本体。raw PIKA 数据写回 `instructions.json`；已转换 HDF5 直接回写 `language_prompt`。

## 6. 核心工作流

### 6.1 原始数据审查后单条转换

1. 用户在网页端选择原始 episode 根目录。
2. 前端上传目录内容到 server staging workspace，并保留相对路径。
3. Server 扫描 uploaded dataset 的 episode 列表，并给出每条状态：未审查、已标注、已转换、转换失败、已过滤。
4. 用户打开某条 episode。
5. Server 通过 `RawEpisodeAdapter` 将原始数据同步为 `PolicyEpisode`，前端可视化的是帧同步后的 `PolicyEpisode`。
6. 用户播放/暂停/拖动时间轴，检查左右腕相机、轨迹和夹爪。
7. 用户填写或修改语言标注。
8. 用户选择保留/丢弃，并可填写原因标签和备注。
9. 用户点击“转换当前 episode”。
10. Server 使用 `RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter` 链路导出 HDF5。
11. 转换完成后可通过 `HDF5EpisodeAdapter` 重新加载 HDF5 并复查，或留在当前列表继续下一条。

### 6.2 不可视化直接批量转换

1. 用户在网页端选择原始根目录并上传到 server，或选择已上传的数据集。
2. 用户配置转换参数：pattern、tolerance、min_frames、frames_per_chunk、downsample、gripper 范围等。
3. 用户选择语言标注来源：原始 `instructions.json`、批量默认 prompt、已有 sidecar。
4. Server 创建批量转换任务。
5. 前端显示任务进度、日志、成功/跳过/失败统计。
6. 任务结束后生成 HDF5 目录与 `conversion_report.json`。

### 6.3 已转换 HDF5 复查

1. 用户在网页端选择 HDF5 文件或目录并上传到 server，或选择已上传的 HDF5 数据集。
2. Server 通过 `HDF5EpisodeAdapter` 将 HDF5 读取为 `PolicyEpisode`。
3. 前端提供多文件切换、播放、帧跳转、速度控制、局部轨迹窗口。
4. 用户可查看或修改语言标注。
5. 用户可标记该 HDF5 是否用于训练。
6. 修改后的语言标注直接回写 HDF5 `language_prompt`。

### 6.4 可达性筛选

1. 用户选择当前 episode 或数据集，并选择可达性 backend 与 robot config。
2. Server 在可视化前基于 `PolicyEpisode` 计算 IK 可达性。
3. 第一版使用 `PiperDexechainReachabilityBackend` 接入当前 dexechain/Piper IK。
4. 前端在轨迹与时间轴上叠加不可达帧：轨迹段、时间轴标记、失败原因列表。
5. 可达性结果只作为提示，不自动剔除整条 episode，也不裁剪不可达帧。

## 7. 功能需求

### 7.1 项目与数据源管理

- 支持创建 review project，绑定一个或多个数据源。
- 支持数据源类型：uploaded raw episode root、uploaded single raw episode、uploaded HDF5 directory、uploaded single HDF5。
- 支持浏览器目录选择和上传，server 按相对路径重建 staging 数据集。
- 支持上传进度、失败重试、取消和上传完成后的扫描结果展示。
- 支持限制可访问根目录，避免网页端任意读取系统路径。
- 支持自然排序 episode 文件，例如 `episode1, episode2, episode10`。
- 支持重新扫描数据源，并保留已有标注。

### 7.2 Episode 列表

- 显示 episode 名称、来源路径、帧数、语言标注摘要、审查状态、转换状态、可达性状态。
- 支持按状态过滤：未审查、已保留、已丢弃、已转换、转换失败、存在不可达帧。
- 支持搜索 episode 名称或语言标注。
- 支持批量选择与批量操作。

### 7.3 可视化

- 支持可变相机数的图像 observation，同步播放所有已接入 camera stream。
- 支持时间轴拖动、播放/暂停、逐帧前进后退、跳转到首尾帧。
- 支持 3D 轨迹显示：左手、右手、当前点、局部轨迹、全局轨迹。
- 支持夹爪曲线显示，并标记当前帧。
- 支持显示每帧 qpos、xyz、gripper、timestamp、同步误差等调试信息。
- 支持不可达帧叠加：轨迹段、曲线背景、时间轴 tick、失败原因。
- 支持缓存当前 episode 和相邻 episode，降低切换延迟。
- 前端统一可视化 `PolicyEpisode`，HDF5 和 raw data 都通过 adapter 转成该中间格式。

### 7.4 语言标注与审查

- 每条 episode 有一个主语言标注 `language_prompt`。
- 支持备注 `notes`。
- 支持质量状态：`pending`、`accepted`、`rejected`、`needs_fix`。
- 支持问题标签：画面问题、轨迹异常、夹爪异常、同步异常、语言不确定、IK 不可达等。
- 支持标注自动保存和手动保存。
- 支持撤销到最近一次保存。
- 支持从 HDF5 `language_prompt` 或原始 `instructions.json` 初始化标注。
- raw PIKA 标注写回 `instructions.json`，HDF5 标注直接回写 HDF5 文件。

### 7.5 转换

- 支持单条转换。
- 支持批量转换。
- 支持仅转换已 accepted 的 episode。
- 支持跳过已存在 HDF5，或选择 overwrite。
- 支持沿用现有参数：camera tolerance、pose tolerance、min frames、frames per chunk、downsample rate、gripper key/min/max。
- 转换失败时记录明确错误，并在列表中可见。
- 转换完成后自动关联 output HDF5 路径到 episode 记录。

### 7.6 可达性筛选/IK

- IK 作为 server 端能力运行，并优先在 episode 可视化前完成当前轨迹的可达性检查。
- 第一版输入是内存中的 `PolicyEpisode`。
- 第一版报告只需要能被当前 Web 工具消费。
- 支持缓存 robot backend，避免每次任务重复初始化。
- 支持任务取消、日志查看、失败重试。
- 支持在前端显示候选 start pose、selected candidate、init_qpos、不可达统计。
- 可达性结果只作为提示，不改变 episode 接受/拒绝状态。

### 7.7 报告与导出

- 审查报告：每条 episode 的状态、语言标注、备注、标签、转换路径。
- 转换报告：复用或扩展 `conversion_report.json`。
- 过滤报告：复用 `filter_report/filter_report.json`。
- 支持导出“最终训练清单”，明确哪些 episode 进入训练。

## 8. 非功能需求

### 8.1 性能

- HDF5 图像不要一次性全量传给前端，应按帧或按小窗口懒加载。
- Server 端应缓存 HDF5 metadata、trajectory、最近访问帧、相邻 episode。
- 视频帧输出优先考虑 JPEG/WebP；需要精确调试时支持 PNG。
- 前端时间轴拖动时应节流，避免每个鼠标事件都触发重解码。
- 大目录上传需要支持进度显示和分批提交；第一版可以先实现小型 HDF5 目录的单次 multipart 上传，后续再扩展分片上传。
- 以单条 episode 为转换单位时，`PolicyEpisode` 可以先采用当前 HDF5 转换类似的全量 episode 内存模式；如果后续遇到大 episode 内存压力，再扩展懒加载/流式 frame provider。

### 8.2 稳定性

- 单个 episode 损坏不能导致整个项目不可用。
- 后台任务需要持久化状态，浏览器刷新后仍可查看进度。
- 日志应包含命令参数、输入输出路径、异常堆栈摘要。
- HDF5 filter 缺失、robot config 错误、IK backend 初始化失败应有清晰提示。

### 8.3 可复现性

- 每个转换/过滤任务保存完整参数。
- 每条 HDF5 记录其来源 episode、标注版本、转换时间、工具版本。
- sidecar 标注文件应有 schema version。

### 8.4 安全与权限

- Web server 只允许访问配置的 workspace roots。
- API 不直接执行用户拼接的 shell 字符串。
- 输出目录必须在允许根目录下。
- 多用户场景下需要操作日志和简单锁，避免两个人同时改同一条标注。

### 8.5 渐进实现与验证

- 后续实现必须先拆分模块，再逐个模块实现、验证和测试。
- 每个模块都应有清晰输入、输出和最小可运行验证方式，避免一次性提交过多难以定位正确性的代码。
- 新模块优先提供小型 CLI、单元测试或 smoke test，用于确认核心行为，再接入 Web UI。
- Web UI 每次只接入一个后端能力：先确认 HDF5 浏览，再接 raw adapter，再接标注，再接转换，再接可达性。
- 模块之间通过稳定的数据结构通信，避免前端、转换逻辑、IK 逻辑互相直接依赖内部实现。

## 9. 建议架构

### 9.1 确认架构

- Frontend：React/Vite + Three.js + Plotly 或 ECharts。
- Backend：FastAPI。
- Job Runner：Python background worker，MVP 可用 `ThreadPoolExecutor`/`ProcessPoolExecutor`，后续可切 Celery/RQ。
- Storage：MVP 用 JSON sidecar；多人/长期使用建议 SQLite。
- Static Assets：复用或改造 LeForge 的 Three.js robot viewer。
- 工具最终计划独立成单独仓库或 Python package，因此核心模块需要保持对 `dexechain/embodichain` 的依赖隔离。

### 9.2 实施顺序原则

首要工作是先打出一个可视化界面，让 fake `PolicyEpisode` 能在网页端播放和展示，验证可视化体验可行。随后再逐步接入真实 adapter/exporter，而不是一次性把所有功能写进 UI。

- 第一阶段用 fake `PolicyEpisode` 验证 FastAPI + React viewer。
- 随后实现 `RawEpisodeAdapter`、`EpisodeExporter`、`ReachabilityBackend` 基类。
- 真实数据接入时先做 `HDF5EpisodeAdapter` 和 `HDF5EpisodeExporter`。
- 再接 `PikaRawEpisodeAdapter`，并用当前脚本逐帧一致作为回归测试标准。

### 9.3 服务端模块

- `DatasetScanner`：扫描 raw/HDF5 数据源。
- `RawEpisodeAdapter`：raw data 通用抽象接口，把不同来源 episode 统一成可视化和转换可消费的数据结构。
- `PikaRawEpisodeAdapter`：PIKA raw data 的具体实现，封装当前 `pika_raw_to_compressed_hdf5.py` 中的目录扫描、时间同步、pose/gripper/image 读取逻辑。
- `HDF5EpisodeAdapter`：HDF5 输入实现，将已转换 HDF5 读取成 `PolicyEpisode`，复用同一套可视化界面。
- `EpisodePreviewService`：生成 raw 同步预览与 HDF5 metadata。
- `FrameService`：按 episode/camera/frame 返回图像。
- `TrajectoryService`：返回 qpos、xyz、gripper、可达性 overlay。
- `AnnotationStore`：读写 sidecar/SQLite 标注。
- `EpisodeExporter`：输出格式通用抽象接口，把标准 `PolicyEpisode` 导出到不同目标格式。
- `HDF5EpisodeExporter`：HDF5 输出实现，写出当前 compressed HDF5 schema。
- `ConversionService`：编排 raw adapter、annotation 和 exporter，负责单条/批量转换任务。
- `ReachabilityBackend`：可达性筛选通用抽象接口，定义轨迹可达性检查、报告输出和前端 overlay 数据。
- `PiperDexechainReachabilityBackend`：当前 Piper + dexechain 逻辑的具体实现，封装现有 `data_filtering.py` 能力。
- `ReachabilityService`：编排 reachability backend、异步任务、报告读取和前端展示数据。
- `JobManager`：异步任务、进度、日志、取消、重试。

### 9.4 Raw Data Adapter 抽象

raw data 接入层应抽象出一个 UMI/eef pose 泛用基类，目标是让可视化界面不关心底层原始数据格式。PIKA 只是第一个子类；后续其他 UMI 数据，甚至其他基于 eef pose 的 raw data，只要实现同一接口，就可以复用同一套审查、标注、预览和转换入口。

建议核心接口：

- `scan(root) -> list[EpisodeRef]`：扫描数据源，返回 episode 列表和基础元信息。
- `validate_episode(episode_ref) -> ValidationResult`：检查目录结构、必要传感器、时间戳和字段是否完整。
- `load_metadata(episode_ref) -> EpisodeMetadata`：读取语言标注、相机列表、帧数估计、时间范围等。
- `build_preview(episode_ref, params) -> PreviewEpisode`：按统一时间轴生成预览所需的相机帧索引、eef pose、gripper、同步误差。
- `get_frame(episode_ref, camera, frame_index) -> ImageFrame`：按统一帧号返回图像。
- `to_policy_episode(episode_ref, params, annotation) -> PolicyEpisode`：输出转换可消费的标准结构，包含 `images`、`qpos/action`、`language_prompt`、`timestamps` 和 provenance。

建议统一中间结构：

- `EpisodeRef`：数据源类型、episode id、路径、adapter 名称。
- `EpisodeMetadata`：相机、时长、估计帧数、语言标注来源、原始格式版本。
- `PreviewEpisode`：预览时间轴、camera frame mapping、left/right eef pose、gripper、诊断信息。
- `PolicyEpisode`：转换成 HDF5/LeRobot 前的标准内存表示。

PIKA adapter 的实现应先从当前转换脚本中拆出可测试的纯函数：扫描 episode、读取 timestamped files、同步左右相机、插值 pose/gripper、静止边界裁剪、downsample、生成 policy vector。每一步都应该能单独验证。

### 9.5 Output Exporter 抽象

输出端也应采用可插拔 exporter 设计。raw adapter 负责把不同来源数据统一成 `PolicyEpisode`，exporter 负责把 `PolicyEpisode` 写成具体格式。这样后续新增 HDF5、LeRobot、调试用 JSON、视频预览包或其他训练框架格式时，不需要修改 raw data adapter。

建议核心接口：

- `validate(policy_episode, params) -> ValidationResult`：检查标准 episode 是否满足目标格式约束。
- `build_output_path(policy_episode, output_root, params) -> Path`：决定输出路径和命名。
- `export_episode(policy_episode, output_path, params) -> ExportResult`：写出单条 episode。
- `export_batch(policy_episodes, output_root, params) -> ExportReport`：批量导出并生成汇总报告。
- `read_metadata(output_path) -> EpisodeMetadata`：可选，用于导出后复查和 Web UI 重新加载。

建议第一版 exporter：

- `HDF5EpisodeExporter`：实现当前 HDF5 schema，包含 `observations/images`、`observations/qpos`、`action`、`language_prompt`、`chunks`。

后续可扩展 exporter：

- `LeRobotEpisodeExporter`：直接输出 LeRobot v3.x 数据集。
- `DebugJsonExporter`：输出轻量 JSON/NPZ，用于 adapter 单元测试和人工排查。
- `VideoPreviewExporter`：输出低码率 mp4/webp 预览包，用于快速分享或离线审查。

HDF5 exporter 的实现应先独立验证：给定一个小型 `PolicyEpisode` fixture，确认写出的 HDF5 能被现有 `data_replay.py` 或新的 HDF5 reader 正常读取，且 `language_prompt`、图像帧数、qpos/action shape、chunks 都符合预期。

### 9.6 依赖隔离策略

新工具应尽可能独立于 `dexechain` 和 `embodichain`。短期可以通过兼容层复用现有代码，但长期目标是把核心数据审查工具做成相对独立的包。

建议分层：

- `core`：纯数据结构、adapter 基类、标注模型、报告模型，不依赖 dexechain/embodichain。
- `adapters/pika`：PIKA raw data 适配器，可以先少量复用现有工具函数，后续逐步迁出。
- `adapters/hdf5`：HDF5 输入适配器，把已转换 HDF5 读取成 `PolicyEpisode`。
- `exporters/hdf5`：HDF5 输出实现，可以先兼容当前 compressed HDF5 schema。
- `hdf5_io`：HDF5 读写、压缩视频解码、HDF5 schema 兼容。
- `web_server`：API、任务系统、文件访问控制。
- `reachability`：可达性基类、报告模型和不依赖 dexechain 的通用数据结构。
- `reachability/backends/piper_dexechain`：当前 Piper + dexechain 可达性实现，作为第一版子类。
- `compat/dexechain`：临时兼容层，封装当前必须依赖 dexechain/embodichain 的转换或 IK 能力。

实现时应避免在 `core` 和前端 API 层直接 import dexechain/embodichain。依赖应只出现在 adapter 或 compat 层，这样将来替换 IK、替换 robot backend、迁移到独立仓库都更容易。

## 10. 初步 API 草案

### 10.1 Project

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `PATCH /api/projects/{project_id}`

### 10.1.1 Uploads

- `POST /api/uploads/datasets`：创建上传会话，声明 input adapter、目录名、文件数量和总大小。
- `POST /api/uploads/{upload_id}/files`：上传单个文件或一批文件，保留 relative path。
- `POST /api/uploads/{upload_id}/complete`：完成上传，server 重建 staging 数据集并触发扫描。
- `GET /api/uploads/{upload_id}`：查询上传进度、错误和 staging 路径。
- `DELETE /api/uploads/{upload_id}`：取消上传并清理 staging 数据。

### 10.2 Dataset / Episode

- `POST /api/datasets/scan`
- `GET /api/projects/{project_id}/episodes`
- `GET /api/episodes/{episode_id}`
- `GET /api/episodes/{episode_id}/metadata`
- `GET /api/episodes/{episode_id}/trajectory`
- `GET /api/episodes/{episode_id}/frame?camera=cam_left_wrist&frame=0`
- `GET /api/episodes/{episode_id}/reachability`

### 10.3 Annotation

- `GET /api/episodes/{episode_id}/annotation`
- `PATCH /api/episodes/{episode_id}/annotation`
- `POST /api/episodes/{episode_id}/annotation/revert`
- `POST /api/projects/{project_id}/annotations/export`

### 10.4 Jobs

- `POST /api/jobs/convert`
- `POST /api/jobs/reachability`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/logs`
- `POST /api/jobs/{job_id}/cancel`
- `GET /api/jobs/{job_id}/events` 或 WebSocket/SSE

## 11. 标注数据模型草案

```json
{
  "schema_version": "pika_review.v1",
  "project": {
    "name": "hand_book_0410",
    "created_at": "2026-05-13T00:00:00+08:00",
    "source_roots": []
  },
  "episodes": {
    "episode0": {
      "source_type": "raw",
      "source_path": "/path/to/episode0",
      "hdf5_path": "/path/to/episode0.hdf5",
      "language_prompt": "pick up the book",
      "review_status": "accepted",
      "quality_tags": ["ok"],
      "notes": "",
      "trim_ranges": [],
      "frame_marks": [],
      "conversion": {
        "status": "success",
        "job_id": "job_001",
        "converted_at": "2026-05-13T00:00:00+08:00"
      },
      "reachability": {
        "status": "done",
        "report_path": "/path/to/filter_report/filter_report.json",
        "fully_reachable": true,
        "unreachable_frame_count": 0
      }
    }
  }
}
```

## 12. 可达性筛选与 IK 集成方案

### 12.1 推荐方案

可达性筛选同样采用“基类规范功能 + 子类实现具体逻辑”的范式。IK 放在 server 端，并作为异步 job 暴露给前端。

实现路径：

1. 定义 `ReachabilityBackend` 基类，描述输入轨迹、机器人配置、检查参数、输出报告和 overlay 数据。
2. 实现第一版 `PiperDexechainReachabilityBackend` 子类，内部复用或封装当前 `data_filtering.py` 的 Piper IK 逻辑。
3. Web server 只依赖 `ReachabilityBackend` 接口，不直接依赖 dexechain/embodichain。
4. 输出继续兼容 `filter_report/filter_report.json`，同时返回标准 `ReachabilityReport` 给前端。
5. 前端读标准报告并叠加显示，不关心后端是 dexechain IK、自研 IK，还是其他 robot backend。

建议核心接口：

- `validate_inputs(target, params) -> ValidationResult`：检查 HDF5/PolicyEpisode、robot config、搜索参数是否可用。
- `prepare(target, params) -> PreparedReachabilityTarget`：加载轨迹、解析 qpos/eef pose、准备机器人模型或缓存 backend。
- `evaluate(prepared_target, params, progress_callback) -> ReachabilityReport`：执行可达性检查并返回标准报告。
- `write_report(report, output_dir) -> Path`：写出报告文件，第一版兼容 `filter_report/filter_report.json`。
- `build_overlay(report, episode_id) -> ReachabilityOverlay`：生成前端需要的不可达帧、失败原因、轨迹段标记等数据。

建议统一中间结构：

- `ReachabilityTarget`：输入 HDF5 文件/目录、episode id 列表、可选 `PolicyEpisode`。
- `ReachabilityParams`：robot config、搜索范围、容差、是否 FK verify、candidate 限制等。
- `ReachabilityReport`：selected candidate、init qpos、每条 episode 的可达比例、不可达帧和原因。
- `ReachabilityOverlay`：前端消费的轻量结构，只包含当前 episode 的帧级 overlay 信息。

第一版子类：

- `PiperDexechainReachabilityBackend`：复用当前 `PiperKinematicsBackend`、candidate 搜索、双臂 IK 检查、`filter_report.json` 输出逻辑。该子类可以放在 compat 或 reachability backend 目录下，明确标注其 dexechain 依赖。

### 12.2 进一步增强

- 后端常驻 backend 池，按 backend type 和 robot config 缓存。
- 支持单条 episode 快速检查。
- 支持返回每帧 IK qpos，后续可用于机器人 3D 姿态回放。
- 支持把 selected candidate 和 init_qpos 写入转换/部署配置。
- 长期目标是实现一个不依赖 dexechain/embodichain 的 IK backend 子类。当前阶段只记录该方向，不作为近期必须完成项。
- 支持未来注册多个 backend，例如 `PiperStandaloneIKBackend`、`URDFIKReachabilityBackend`、`MockReachabilityBackend`。

### 12.3 主要风险

- IK backend 初始化可能慢，且依赖 sim/headless 环境。
- 多用户并发跑 IK 可能抢资源。
- 当前 `verify_fk` 默认关闭且注释中提到 TCP residual mismatch，需要在需求层明确“可达性”的判定标准。
- 如果要在预转换 raw preview 上做 IK，需要先完成和 HDF5 一致的 qpos 构建流程；更稳的路径是先转换 HDF5，再跑 IK。
- 自研 IK 需要明确机器人模型来源、关节限制、TCP 定义、FK/IK 误差验证和与现有 Piper 控制器的一致性测试；这会是独立工程，不应阻塞 Web 审查工具 MVP。

## 13. 前端页面需求

### 13.1 首页/项目页

- 选择或创建 project。
- 显示数据源、episode 总数、审查进度、转换进度、可达性进度。

### 13.2 审查页

- 左侧：episode 列表、过滤器、状态标签。
- 中间：相机画面、播放控制、时间轴。
- 右侧：语言标注、审查状态、质量标签、备注、转换/过滤动作。
- 下方或独立 tab：3D 轨迹、夹爪曲线、IK 不可达详情、日志。

### 13.3 任务页

- 显示正在运行和历史任务。
- 支持查看参数、日志、结果路径。
- 支持取消和失败重试。

### 13.4 设置页

- 配置允许访问的数据根目录。
- 配置默认输出目录。
- 配置默认转换参数。
- 配置 robot config 与 IK 默认参数。

## 14. 分阶段实施文档

阶段工作和验收标准已拆成独立文档，主需求文档只保留索引：

- [Phase 00: Fake PolicyEpisode Web Viewer](./02_phase_00_fake_policy_episode_viewer.md)
- [Phase 001: Viewer UI Polish](./02_phase_001_viewer_ui_polish.md)
- [Phase 01: Core Abstractions](./03_phase_01_core_abstractions.md)
- [Phase 02: HDF5 Adapter And Exporter](./04_phase_02_hdf5_adapter_exporter.md)
- [Phase 03: Pika Raw Adapter](./05_phase_03_pika_raw_adapter.md)
- [Phase 04: Annotation And Review Workflow](./06_phase_04_annotation_review.md)
- [Phase 05: Conversion Workflow](./07_phase_05_conversion_workflow.md)
- [Phase 06: Reachability Backend](./08_phase_06_reachability_backend.md)
- [Phase 07: Dataset Workbench](./09_phase_07_dataset_workbench.md)

## 15. 已确认决策

- 技术栈：FastAPI + React/Vite。
- 第一优先级：先做 fake `PolicyEpisode` Web Viewer，证明可视化体验可行。
- 前端可视化对象：统一可视化 `PolicyEpisode`，raw data 和 HDF5 都通过 adapter 转成该格式。
- HDF5 角色：HDF5 是 exporter 的一种落盘格式，不是内存数据结构。
- 输入扩展：通过 `RawEpisodeAdapter` 接入；第一版包括 `PikaRawEpisodeAdapter` 和 `HDF5EpisodeAdapter`。
- 输出扩展：通过 `EpisodeExporter` 接入；第一版只实现 `HDF5EpisodeExporter`。
- 图像 observation：支持可变相机数和可变 camera key。
- action/state：第一版规范为双臂 eef pose + gripper。
- 标注写回：PIKA raw 写回 `instructions.json`；HDF5 写回 `language_prompt`。
- 审查粒度：只做整条 episode 接受/拒绝，不做手动片段裁剪。
- PIKA 回归标准：拆分 adapter 后，转换结果需要与当前脚本逐帧一致。
- 可达性输入：第一版以 `PolicyEpisode` 作为内存中时间戳对齐的输入。
- 可达性作用：仅作为提示，在轨迹可视化中展示可达/不可达时刻，不自动剔除数据。
- IK 时机：建议在可视化前计算当前轨迹 IK，可视化时直接展示不可达帧。
- IK 实现：第一版先用 dexechain/Piper 逻辑，封装为 `PiperDexechainReachabilityBackend`。
- Reachability report：第一版只要求能被当前 Web 工具消费。
- 多人协作：暂不考虑，必要时通过拆分数据集并行处理。
- 数据根目录：由用户在网页端以目录选择的形式选择，并上传到 server staging 后解析；server path 只作为开发调试快捷入口，不作为正式主流程。
- 项目形态：计划独立成单独仓库或 Python package。

## 16. 当前推荐方案

当前首要目标是 Phase 001：在 Phase 00 fake `PolicyEpisode` viewer 的基础上打磨网页交互和视觉布局，重点验证目录选择入口、episode 列表状态表达、格式选择、自动播放和标注按钮排版。

随后进入核心抽象和真实数据接入：先做 `RawEpisodeAdapter`、`EpisodeExporter`、`ReachabilityBackend` 基类，再做 `HDF5EpisodeAdapter`、`HDF5EpisodeExporter`，最后接入 `PikaRawEpisodeAdapter` 并用现有脚本做逐帧回归。

等可视化、标注和 HDF5 导入导出稳定后，再接入 `PiperDexechainReachabilityBackend`，把 IK 可达性作为轨迹可视化 overlay 展示。
