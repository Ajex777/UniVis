# Phase 01: Core Abstractions

## Goal

建立后续所有模块共享的核心数据结构和接口：`PolicyEpisode`、`RawEpisodeAdapter`、`EpisodeExporter`、`ReachabilityBackend`、annotation model。这个阶段重点是边界清楚、可测试、尽量不依赖 `dexechain/embodichain`。

## Scope

- 定义 `PolicyEpisode` 作为内存中的时间戳对齐数据格式。
- 图像 observation 支持可变相机数和可变 camera key。
- action/state 第一版固定为双臂 eef pose + gripper。
- 定义 `RawEpisodeAdapter` 基类。
- 定义 `EpisodeExporter` 基类。
- 定义 `ReachabilityBackend` 基类。
- 定义 annotation model：语言标注、整条 episode 接受/拒绝、备注、质量标签。
- 定义最小 fixture 和 mock implementation。

## Acceptance

- `PolicyEpisode` 能表达 fake episode、HDF5 episode、PIKA raw 同步结果。
- `RawEpisodeAdapter` 至少有 mock adapter，可输出 fake `PolicyEpisode`。
- `EpisodeExporter` 至少有 mock exporter，可接收 `PolicyEpisode` 并返回 `ExportResult`。
- `ReachabilityBackend` 至少有 mock backend，可返回可达/不可达 frame overlay。
- 核心模块不直接 import `dexechain` 或 `embodichain`。

## Tests

- 单元测试覆盖 `PolicyEpisode` shape 校验、camera key 校验、双臂 action/state 校验。
- 单元测试覆盖 mock adapter/exporter/reachability backend 的基本流程。
- smoke test 验证 `RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter` 链路可运行。

## Out Of Scope

- 不实现真实 PIKA adapter。
- 不实现真实 HDF5 exporter。
- 不实现真实 IK。
