# Phase 07: Dataset Workbench

## Goal

在核心链路稳定后，补齐数据集级工作台能力，包括汇总、过滤、最终训练清单和更完整的任务历史。

## Scope

- 数据集级统计：总数、accepted/rejected、已导出、导出失败、存在不可达提示。
- 最终训练清单导出。
- 批量状态修改和批量重跑。
- 任务历史查看。
- 数据集拆分工作流，用于未来可能的多人并行审查。

## Acceptance

- 用户能一眼看到整个数据集审查和导出进度。
- 可以导出最终训练清单。
- 可以按状态筛选并批量执行转换。
- 可以查看历史任务参数、日志和输出路径。

## Tests

- Report generation test：汇总统计与 annotation store 一致。
- Training list test：只包含 accepted 且成功导出的 episode。
- Task history test：任务刷新后仍可查看。

## Out Of Scope

- 第一版不做多人实时协同。
- 不做权限系统。
- 不做远程数据集管理。
