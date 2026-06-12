## WHY

本次修改主要围绕 DTW 质量检测的 CLI 化、GUI 易用性，以及 format 名称简写能力展开。

1. 新增 `univis-dtw` CLI，用于在不启动 GUI 的情况下执行 DTW 质量检测。
   - `compare`：比较两个 episode，输出 JSON 指标和 PNG 轨迹对比图。
   - `stats`：给定 reference，统计多个 episode 相对 reference 的 DTW 指标。
   - 默认 `input-format` 为 `PikaRawEpisodeAdapter`。
   - 支持 `--input-format` 简写为 `--if`。
   - 输出默认写入 `<source>/dtw/compare` 或 `<source>/dtw/stats`。

2. 抽出 `QualityService`，让 GUI API 和 CLI 复用同一套 DTW 计算逻辑。
   - 避免 GUI 和 CLI 出现两套不同的质量检测实现。
   - `selected_stats` 在后端统一自动排除 reference，避免 reference-vs-reference 的 0 error 影响统计。

3. 新增 DTW 静态图导出能力。
   - CLI `compare` 会额外生成 PNG。
   - PNG 展示 current/reference 双臂轨迹及 DTW 对齐连线。
   - 使用 `matplotlib` 后端渲染，适合纯命令行环境。

4. 为组件增加 alias 机制。
   - `ComponentInfo` 新增 `aliases` 字段。
   - 新增 `ComponentNameResolver`，支持大小写不敏感的 name/alias 匹配。
   - 已支持：
     - `PikaRawEpisodeAdapter` -> `PIKARaw`
     - `HDF5EpisodeAdapter` -> `HDF5`
     - `HDF5EpisodeExporter` -> `HDF5`
     - `LeRobotV3EpisodeAdapter` -> `LeRobotV3`
   - 未知 format 时会打印可用候选项。
   - 自动补全功能已按要求移除，仅保留候选项错误提示。

5. 改进 GUI DTW 体验。
   - `DTW Metrics` 和 `Selected DTW Stats` 指标旁增加 `?`。
   - 鼠标悬浮后显示中文指标解释。
   - 移除浏览器原生 `title` tooltip，避免黑底白字和自定义提示框同时出现。
   - `DTW Metrics` 默认位置调整到右侧轨迹模块左上角。
   - 更新静态资源版本号，避免浏览器缓存旧 JS/CSS。

## TEST

1. 测试了GUI一切功能正常

2. 测试了CLI进行DTW检查

## P1: Smooth Trajectory Quality

### WHY

后续需要在 UniVis 中增加 smooth 轨迹质量检测能力，用于判断单条 episode 自身是否存在抖动、不连续或不自然的运动。该能力参考 `/home/dex/app/embodichain` 的 `zzy/teledata-dqa` 分支中 `dexechain/data/scripts/teledata_dqa/assessor.py` 的 smoothness 逻辑，但不应直接绑定 teledata qpos 文件或 PIKA raw data。

UniVis 的统一中间数据是 `PolicyEpisode`，因此 smooth 第一版应实现为独立的 `TrajectoryQualityBackend`，消费 `PolicyEpisode` 中已经对齐好的双臂 EEF pose。这样 HDF5、PIKA raw、LeRobot V3 等输入格式都可以复用同一套 smooth 逻辑。

### 参考算法

`assessor.py` 中的 smoothness 检查核心逻辑是：

1. 读取 episode 的 qpos 轨迹。
2. 根据 episode duration 和帧数计算 `action_dt`。
3. 按 scope 切分轨迹。
4. 分别计算 acceleration smoothness cost 与 jerk smoothness cost。
5. 若 cost 超过 yaml 配置阈值，则认为该 episode 在对应 scope 上不够平滑。

对应数学形式：

- `acceleration_cost = mean(||d2x / dt2||^2) * dt`
- `jerk_cost = mean(||d3x / dt3||^2) * dt`

### UniVis 设计

建议新增模块：

- `univis/quality/smooth.py`
- `univis/quality/config/smooth/default.yaml`

建议新增模型：

- `SmoothnessConfig`
- `ArmSmoothnessSummary`
- `EpisodeSmoothnessReport`

建议新增 backend：

- `SmoothnessTrajectoryQualityBackend`

第一版 scope 建议只默认启用：

- `left_eef_position`
- `right_eef_position`

rotation smoothness 可以预留配置项，但默认不启用。原因是 rot6d 直接做二阶、三阶差分的解释性弱于 position，后续可以再根据需求改为基于 SO(3) 角速度/角加速度的版本。

### 配置建议

```yaml
smoothness:
  backend: SmoothnessTrajectoryQualityBackend

time:
  use_episode_timestamps: true
  fps_fallback: 30.0

scopes:
  left_eef_position:
    enabled: true
    source: left.xyz
    acceleration_cost_threshold: 10.0
    jerk_cost_threshold: 200.0
  right_eef_position:
    enabled: true
    source: right.xyz
    acceleration_cost_threshold: 10.0
    jerk_cost_threshold: 200.0
  left_eef_rotation6d:
    enabled: false
    source: left.rot6d
  right_eef_rotation6d:
    enabled: false
    source: right.rot6d
```

### 输出指标

每只手建议输出：

- `acceleration_cost`
- `jerk_cost`
- `max_acceleration`
- `max_jerk`
- `num_frames`
- `dt`
- `passed`
- `warnings`

这些指标与 DTW 不同：DTW 是相对 reference 的轨迹相似度，smooth 是单条轨迹自身的连续性和平滑性检查。因此 smooth 不需要 reference。

### 实现阶段

第一阶段只实现后端核心：

1. 新增 acceleration 和 jerk smoothness 数学函数。
2. 新增 smoothness config 和 report model。
3. 新增 `SmoothnessTrajectoryQualityBackend`，输入 `PolicyEpisode`，输出 `EpisodeSmoothnessReport`。
4. 增加单元测试：直线匀速轨迹 cost 接近 0，带突变轨迹 cost 明显升高。

第二阶段接入服务层：

1. 扩展 `QualityService`，增加 `smooth_episode(episode_id)`。
2. 增加 API：`POST /api/quality/smooth/episode`。
3. 后续可增加 CLI，例如 `univis-quality smooth` 或单独 `univis-smooth`。

第三阶段接入 GUI：

1. 在 Quality 区域新增可折叠 `Smooth` 功能块。
2. 展示 left/right acceleration、jerk 和 passed 状态。
3. 后续可在 timeline 或 3D 轨迹中标出高 jerk 帧。