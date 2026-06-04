# Phase 08: Interactive Trajectory Quality DTW

## Goal

在 UniVis viewer 中增加交互式 DTW 质量审查功能。它不是一个离线汇总报告工具，而是当前 episode 可视化的增强模式：用户选择一条 reference/expert trajectory 后，当前打开的 episode 会与 reference 做 dynamic time warping 对齐，并在 3D 轨迹图中直接展示两条轨迹及其匹配关系。

该功能只提供质量提示、相似度/error 展示和 selected episodes 统计辅助，不自动拒绝 episode、不裁剪数据、不修改 `Annotation.review_status`。

## Source Requirements

来自 `/home/dex/app/my_docs/20260520_umi_data_quality` 的算法需求如下：

- 比较同任务下两条相对 pose 轨迹在允许速度差异后的形状一致性。
- 单臂单帧 pose 采用 `xyz + rot6d`，即 shape `(T, 9)`。
- position error 使用欧氏距离。
- rotation error 需要先将 rot6d 转换为 rotation matrix，再计算 geodesic angular distance。
- DTW 逐帧 cost 使用可解释的尺度归一化：默认 `pos_scale=0.01m`，`rot_scale=5deg`。
- 支持不同长度轨迹，并可配置 Sakoe-Chiba window，默认 `window_ratio=0.2`。
- 输出 normalized DTW cost、position/rotation mean/p95/max、final pose error、warp distortion、path length 等指标。

来自当前产品澄清的交互需求如下：

- Quality 区域位于 Annotation 模块下方，是一个带滚动条的区域。
- Quality 区域第一版只有一个 DTW 功能块，默认折叠。
- DTW 折叠标题行需要展示状态：`未启用`、`未选择 reference`、或当前 reference episode 路径。
- 展开后包含一个启用/关闭 DTW 的单选框或 checkbox。
- 展开后包含 `Use current as reference` 按钮。
- 展开后包含 `Find medoid reference` 按钮。
- 选择 reference 成功后弹出提示：已成功将某条 episode 作为 reference，所有轨迹将与该轨迹进行 dynamic time warping 对比。
- DTW 开启且 reference 已选择后，右侧 3D 轨迹展示变成当前 episode 与 reference 的 DTW 对齐对比。
- 3D 对比需要展示 current trajectory、reference trajectory，以及 DTW path 中匹配点之间的连线。
- 左手和左手匹配，右手和右手匹配；同一只手的 current/reference 颜色接近但不同。
- 页面顶部显示一个可拖动、非阻塞的浮动指标弹窗，展示左手和右手独立 error 指标，不做左右臂平均。
- 复用现有 episode selected 功能，支持计算 selected episodes 相对当前 reference 的统计指标。
- selected 统计结果以弹窗展示，不写文件落盘；用户需要保存时自行复制。
- 用户可以再次关闭 DTW 功能，恢复普通轨迹展示。

## Design Principles

- DTW 不属于某个输入格式，不应硬编码在 `pika_raw`、`compressed_hdf5` 或 `lerobot_v3` 中。
- DTW 输入统一消费 `PolicyEpisode`，这样所有 adapter 都天然可用。
- 网络层只负责接收 episode id、reference id 和 selected ids，不实现 DTW 数学逻辑。
- DTW UI 是 viewer 的一个可开关 overlay，不是独立页面。
- DTW 指标左右臂分开展示，第一版不合成总分，避免隐藏具体是哪只手异常。
- selected episodes 统计是 “N 条 episode 分别与 1 条 reference 做 1 对 1 DTW 后的指标聚合”，不是 pairwise all-to-all 汇总。
- 第一版不落盘 DTW report，避免过早固定报告格式。

## Proposed Modules

### `univis.quality.base`

定义质量评估通用抽象。

建议类：

- `TrajectoryQualityBackend`
- `TrajectoryQualityReport`
- `TrajectoryQualityBatchReport`
- `EpisodeQualitySummary`

`TrajectoryQualityBackend` 接收 `PolicyEpisode`，返回可序列化报告。它不依赖 FastAPI、不依赖具体 adapter，也不直接读写磁盘。

### `univis.quality.extractors`

负责从 `PolicyEpisode` 提取 DTW 可消费的 pose trajectory。

建议类：

- `PoseTrajectory`
- `TrajectoryExtractor`
- `DualArmEEFExtractor`

第一版 `DualArmEEFExtractor` 从每个 `PolicyFrame` 中提取：

- left arm: `[left.xyz, left.rot6d] -> (T, 9)`
- right arm: `[right.xyz, right.rot6d] -> (T, 9)`

### `univis.quality.dtw`

实现 DTW pose consistency 核心算法。

建议类：

- `PoseDTWConfig`
- `PoseDTWComparator`
- `ArmDTWResult`
- `EpisodeDTWComparison`
- `SelectedEpisodeDTWStats`
- `DTWTrajectoryQualityBackend`

核心职责：

- rot6d -> rotation matrix 的数值稳定转换。
- position error、rotation error、weighted pose distance。
- DTW cumulative cost 和 warping path。
- current/reference 左臂对齐结果。
- current/reference 右臂对齐结果。
- selected episodes 相对 reference 的统计结果。
- medoid reference 自动选择。

纯数学工具函数可放在 `univis.quality.dtw_math` 或 `univis.utils.rotation`，但不要让工具函数直接依赖 `PolicyEpisode`。

### `univis.api.quality`

提供轻量 API，不承载业务逻辑。

候选接口：

- `GET /api/quality/backends`
- `POST /api/quality/dtw/compare`
- `POST /api/quality/dtw/medoid-reference`
- `POST /api/quality/dtw/selected-stats`

`compare` 用于当前 episode 与 reference 的实时对比。`selected-stats` 用于对选中的 episode 列表逐条与 reference 比较并聚合统计。第一版可以同步返回；如果真实数据上耗时明显，再接入 background job。

## UI Design

### Quality Area

位置：

- 放在右侧信息栏的 Annotation 模块下方。
- 区域有固定最大高度和滚动条，避免挤压页面主体。

内容：

- 第一版只包含 `DTW` 功能块。
- DTW 功能块默认折叠。
- DTW 标题行可点击展开/折叠。
- 标题行展示状态：
  - `DTW · 未启用`
  - `DTW · 未选择 reference`
  - `DTW · reference: <episode path>`

### DTW Block Expanded Layout

建议从上到下排列：

1. `Enable DTW` checkbox。
2. 当前 reference 状态小字。
3. `Use current as reference` 按钮。
4. `Find medoid reference` 按钮。
5. `Compute selected stats` 按钮。
6. 参数折叠区，可放 `pos_scale`、`rot_scale_deg`、`window_ratio`，第一版可以先不暴露。

按钮行为：

- `Use current as reference`：把当前打开 episode 设置为 reference。
- `Find medoid reference`：从当前目录 episode 中自动选择 medoid，并设置为 reference。
- `Compute selected stats`：读取现有 selected episode 列表，计算它们与当前 reference 的 1 对 1 DTW 指标均值、p95、max 等聚合值。

### Reference State

reference episode 是前端状态，随每次质量评估请求显式传给 server，而不是由 server 隐式猜测。

行为：

- 未选择 reference 时，开启 DTW 也不改变轨迹图，只提示需要先选择 reference。
- 用户点击 `Use current as reference` 后，前端记录 `reference_episode_id` 和显示路径。
- 切换当前查看 episode 不改变 reference。
- 切换 input source、workspace path 或 dataset root 时清空 reference。
- reference episode 被 selected/filter 排除时仍允许作为 reference 使用。
- reference episode 不存在时 API 返回明确错误，UI 清空 reference 并提示重新选择。

### 3D Alignment Visualization

当 DTW 开启且 reference 已选择时，右侧轨迹图进入对比模式。

显示内容：

- current left trajectory。
- reference left trajectory。
- current right trajectory。
- reference right trajectory。
- left DTW path 的匹配点连线。
- right DTW path 的匹配点连线。
- 当前播放帧位置仍应保留。

颜色建议：

- left current: 深绿色。
- left reference: 浅绿色或青绿色。
- right current: 深橙色。
- right reference: 浅橙色或金色。
- left match lines: 半透明绿色灰。
- right match lines: 半透明橙色灰。

性能约束：

- DTW path 可能很长，前端绘制连线应支持 decimation，例如最多显示 80 到 150 条匹配线。
- 连线采样只影响可视化，不影响指标计算。
- 当前 episode 切换后，如果 DTW 开启且 reference 存在，应自动重新请求 compare result。

### Floating Metrics Panel

DTW 开启且 compare result 可用时，页面顶部显示一个非阻塞浮动指标弹窗。

行为：

- 可拖动。
- 不阻止用户点击页面主体、切换 episode、播放视频。
- 可关闭或最小化。
- 当前 episode 切换后自动更新内容。

内容：

- current episode path。
- reference episode path。
- left arm 指标。
- right arm 指标。
- 每只手展示 normalized DTW cost、mean/p95/max position error、mean/p95/max rotation error、final pose error、warp distortion。
- 不展示左右臂平均分作为第一版主指标。

### Selected Episode Stats Popup

`Compute selected stats` 用于快速评估一批已选 episode 与 reference 的整体一致性。

计算方式：

- 对每条 selected episode，分别与 reference 做 1 对 1 DTW。
- 左臂和右臂分别统计。
- 对每个指标计算 mean、p95、max。
- 可列出 top abnormal episodes，按 normalized DTW cost 或 p95 error 排序。

展示方式：

- 弹窗展示。
- 不写文件。
- 支持用户复制文本或表格内容。

## Data Model Sketch

```python
class PoseDTWConfig(BaseModel):
    pos_scale: float = 0.01
    rot_scale_deg: float = 5.0
    window_ratio: float | None = 0.2
    max_visual_links: int = 120
```

```python
class ArmDTWSummary(BaseModel):
    dtw_cost: float
    dtw_cost_normalized: float
    mean_position_error: float
    p95_position_error: float
    max_position_error: float
    final_position_error: float
    mean_rotation_error_deg: float
    p95_rotation_error_deg: float
    max_rotation_error_deg: float
    final_rotation_error_deg: float
    warp_distortion: float
    path_length: int
    length_current: int
    length_reference: int
    length_ratio: float
```

```python
class ArmDTWAlignment(BaseModel):
    summary: ArmDTWSummary
    warping_path: list[tuple[int, int]]
    visual_links: list[tuple[int, int]]
```

```python
class EpisodeDTWComparison(BaseModel):
    current_episode_id: str
    reference_episode_id: str
    left: ArmDTWAlignment
    right: ArmDTWAlignment
```

```python
class SelectedEpisodeDTWStats(BaseModel):
    reference_episode_id: str
    selected_episode_ids: list[str]
    left_summary: dict[str, float]
    right_summary: dict[str, float]
    abnormal_episodes: list[dict[str, object]]
```

## Implementation Stages

### Phase 08a: Core DTW Library

实现纯 Python backend，不接 UI。

范围：

- 新增 `univis.quality` 包和 base 抽象。
- 新增 pose extraction 类。
- 新增 DTW comparator。
- 输出左右臂独立 comparison result。
- 输出 warping path 和 decimated visual links。

验收：

- 两条 `(T, 9)` 轨迹可完成 pairwise DTW。
- rot6d rotation error 不使用 raw 6D Euclidean distance。
- 不同长度轨迹可比较。
- 左右臂指标互相独立。
- 输出字段覆盖 MVP 指标和 3D 对齐可视化需要的 path。
- 所有新增文件小于 250 行；数学函数和模型必要时拆文件。

### Phase 08b: Medoid And Selected Stats

实现 reference 辅助选择和 selected episode 统计。

范围：

- 支持从当前目录 episode 中自动寻找 medoid reference。
- 支持 selected episode ids 相对 reference 的 1 对 1 DTW 批量计算。
- 输出左右臂独立聚合统计。
- 输出 abnormal episode 排序。

验收：

- 对 3 条以上 fake episode 能选择 medoid。
- 用户指定 reference 时，selected stats 稳定使用该 reference。
- selected stats 不做 pairwise all-to-all 汇总。
- 结果可 JSON 序列化。

### Phase 08c: API Integration

把 DTW backend 接入 server，但保持网络层简单。

范围：

- 注册 `TrajectoryQualityBackend` 到 registry，或新增 quality backend registry 字段。
- 新增 `QualityRouter`。
- `compare` API 接收 `current_episode_id` 和 `reference_episode_id`。
- `medoid-reference` API 返回建议 reference episode。
- `selected-stats` API 接收 `reference_episode_id` 和 selected episode ids。

验收：

- API 可列出 DTW backend。
- API 可比较当前 episode 与 reference。
- API 可返回 medoid reference 建议。
- API 可返回 selected stats。
- API 层不包含 DTW 数学实现。

### Phase 08d: Frontend Interaction

实现 Quality 区域、DTW 折叠块、reference 操作和浮动指标弹窗。

范围：

- 在 Annotation 下方增加 Quality 区域。
- DTW 功能块默认折叠。
- 标题行展示启用状态和 reference 状态。
- 展开后提供 enable checkbox、reference 按钮、medoid 按钮、selected stats 按钮。
- reference 设置成功后显示提示。
- DTW 开启且 reference 存在时，轨迹图切换为 current/reference 对齐模式。
- 页面顶部显示可拖动、非阻塞指标弹窗。
- selected stats 使用弹窗展示，不落盘。

验收：

- 用户能设置当前 episode 为 reference，并在切换 episode 后保持 reference 不变。
- 用户能关闭 DTW 并恢复普通轨迹展示。
- 用户能看到 current/reference 的左右臂 3D 轨迹和匹配连线。
- 用户能看到左手、右手独立 error 指标。
- 用户能对 selected episodes 计算相对 reference 的统计指标。

## Recommended Defaults

- `pos_scale`: `0.01`
- `rot_scale_deg`: `5.0`
- `window_ratio`: `0.2`
- `max_visual_links`: `120`
- `reference_mode`: `selected_episode`
- `selected_stats_p95`: `95.0`

这些默认值应由后端文件配置统一管理，当前实现路径为 `src/univis/quality/config/dtw/default.yaml`。YAML 必须保持结构化，例如区分 `pose_distance.position`、`pose_distance.rotation`、`alignment.window`、`visualization.alignment_links`、`statistics`，再由 `QualityConfig` 解析为 `PoseDTWConfig`。GUI 和未来 CLI 都不应各自维护一套 DTW 默认参数。

## Tests

- rot6d conversion numerical stability test。
- identity trajectory DTW score 接近 0。
- 不同速度但同形状轨迹通过 DTW 后 score 低于直接逐帧比较。
- position-only difference 和 rotation-only difference 能分别反映到对应指标。
- left/right independent metric test。
- visual link decimation test。
- medoid reference selection test。
- selected stats aggregation test。
- API compare smoke test。
- API medoid smoke test。
- API selected stats smoke test。
- dependency boundary test：`univis.quality` 不 import FastAPI、HDF5、PIKA、dexechain、embodichain。

## Out Of Scope

- 不判断 task success。
- 不做碰撞、安全、IK 可达性判断。
- 不做 gripper consistency。
- 不做 object-frame alignment、world-frame alignment 或 start-pose registration。
- 不自动拒绝 episode。
- 不自动裁剪异常片段。
- 不在第一版实现 motion phase segmentation。
- 不在第一版实现 smoothness UI；`trajectory_smoothness.py` 中的想法可作为后续 quality backend。
- 不在第一版落盘 DTW report。

## Resolved Design Questions

- 第一版不是汇总报告优先，而是当前 viewer 的交互式 DTW overlay。
- reference 默认由用户手动设置；medoid 是一个按钮触发的辅助选择。
- current/reference 比较是主要路径，selected episodes stats 是辅助路径。
- 左右臂指标独立展示，不做左右臂平均。
- selected stats 不写文件，弹窗展示，用户自行复制保存。

## Open Questions

1. `Enable DTW` 用 checkbox 还是单选开关组件，视觉上哪个更适合当前 UI？
2. 3D 匹配连线默认显示多少条最合适：80、120，还是随帧数自适应？
3. 浮动指标弹窗默认位置是在页面顶部居中，还是靠近轨迹图右上角？
