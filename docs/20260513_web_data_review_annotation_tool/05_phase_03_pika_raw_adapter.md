# Phase 03: Pika Raw Adapter

## Goal

实现 `PikaRawEpisodeAdapter`，把 PIKA raw data 同步为 `PolicyEpisode`。拆分后需要和当前转换脚本逐帧一致，作为回归测试标准。

## Scope

- 扫描 PIKA raw episode root 和单个 episode。
- 读取可变相机数据，但 action/state 第一版仍固定为双臂 eef pose + gripper。
- 复用或迁移当前同步逻辑：timestamp files、左右相机匹配、pose/gripper 插值、静止边界裁剪、downsample、policy vector 构建。
- 读取和写回原始 `instructions.json`。
- 输出 `PolicyEpisode`，供 viewer、annotation、HDF5 exporter 复用。

## Acceptance

- 对同一条 PIKA raw episode，adapter 输出的帧数、图像帧选择、qpos/action 与当前 `pika_raw_to_compressed_hdf5.py` 保持逐帧一致。
- 可变 camera keys 能被 metadata 正确列出，并在前端显示。
- 修改语言标注后，`instructions.json` 被写回且再次加载能读到更新。
- 能通过 `PikaRawEpisodeAdapter -> PolicyEpisode -> HDF5EpisodeExporter` 导出 HDF5。

## Tests

- Regression test：选定 fixture raw episode，与当前脚本输出逐帧比对。
- Metadata test：检查 camera keys、帧数、语言标注来源。
- Instruction writeback test：修改 prompt 后重新读取。
- Conversion smoke test：raw adapter 输出导入 HDF5 exporter。

## Out Of Scope

- 不支持手动片段裁剪。
- 不接其他 raw data 格式。
- 不移除第一版中必要的兼容依赖，但依赖必须隔离在 adapter/compat 层。
