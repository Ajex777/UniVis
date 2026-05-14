# Phase 04: Annotation And Review Workflow

## Goal

实现围绕整条 episode 的审查和语言标注流程。第一版只支持整条 episode 接受/拒绝，不支持手动裁剪片段。

## Scope

- annotation store 保存 episode 状态、语言标注、备注、质量标签。
- 原始 PIKA 数据标注写回 `instructions.json`。
- HDF5 数据标注直接回写 HDF5 `language_prompt`。
- 支持整条 episode 的 `accepted` / `rejected` / `pending` 状态。
- 前端提供标注编辑、保存、状态切换和列表过滤。

## Acceptance

- PIKA raw episode 修改 prompt 后，`instructions.json` 被更新。
- HDF5 episode 修改 prompt 后，HDF5 文件被更新。
- 接受/拒绝状态能保存，并在刷新页面后保持。
- episode 列表可以按审查状态过滤。
- 不存在片段级裁剪入口，避免第一版范围膨胀。

## Tests

- Annotation API test：create/read/update status 和 prompt。
- Raw writeback test：`instructions.json` 更新。
- HDF5 writeback test：`language_prompt` 更新。
- Frontend manual test：编辑、保存、刷新、过滤。

## Out Of Scope

- 不支持多人同时编辑冲突解决。
- 不支持片段级标注或裁剪。
- 不支持复杂审核流。
