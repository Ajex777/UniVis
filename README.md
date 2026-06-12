# UniVis

UniVis 是一个面向双臂具身操作的本地优先 Web 可视化、审查、标注与导出工具，核心思想是把不同来源的数据统一转换成内存中的同步轨迹 `PolicyEpisode`，再由同一套网页界面完成可视化、语言标注、质量审查和批量导出。

<img src="images/univis.png" alt="UniVis GUI 展示" width="800">

## 一、项目目标

UniVis 旨在可视化以及处理所有基于双臂 End Effector 的数据，任意输入格式的数据都应该能轻易地被添加到 UniVis 中并复用现成的可视化与处理 pipeline。目前支持的数据 pipeline 为：

1. 本体数据选择：选择一个本机数据目录。
2. 选择输入数据格式：如 PIKA raw、compressed HDF5、LeRobot v3、Dexforce W1 Teleop。
3. 可视化数据检查：在网页中逐条查看图像、轨迹、夹爪状态，以及数据质量。
4. 数据语言标注：对于raw data，给 episode 写入语言标注、接受或拒绝审查结果。
5. 数据预处理：在导出时应用选中的数据预处理操作。
6. 数据格式转换：将任意一种 input 数据类型转换为任意一种 output 数据类型。

Version 0.1 假设 server 和 browser 运行在同一台机器上，因此使用 named workspace 共享本机目录，避免大规模上传原始图片或视频。

## 二、安装

UniVis使用 `uv` 进行高效的依赖管理。

首先，安装 `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

随后，一键安装依赖:

```bash
uv sync --extra dev
```

如果需要可视化 Dexforce W1 遥操数据，并使用本地 FK 将全身 `qpos` 转换为双臂 EEF pose，还需要安装 W1 FK 可选依赖：

```bash
uv sync --extra dev --extra w1-fk
```

`w1-fk` 会额外安装 `torch` 与 `pytorch-kinematics==0.7.6`。如果只查看 PIKA raw、HDF5 或 LeRobot v3 数据，不需要安装这个 extra。

## 三、启动

最常用的启动方式是同时配置输入 workspace 和导出 output root：

```bash
uv run univis \
  --port 8010 \
  --workspace raw=/path/to/rawdata \
  --workspace hdf5=/path/to/hdf5data \
  --output /path/to/output
```

启动后打开：

```text
http://127.0.0.1:8010
```

`--workspace NAME=PATH` 可以重复传入。`NAME` 会显示在网页的 Workspace source 下拉框中，`PATH` 是 server 端能直接访问的数据根目录。

<img src="images/workspace.png" alt="workspace 决定数据目录选择" width="500">

`--output PATH` 指定导出的根目录。网页里的输出路径输入框只填写这个根目录下的相对子路径，例如 `sort_book_0509/pos1`，最终会导出到 `/path/to/output/sort_book_0509/pos1`。

<img src="images/conversion.png" alt="output 决定导出路径" width="500">

如果不指定 `--output`，默认导出到项目目录下的 `.univis/exports`。

如果已安装 W1 FK 可选依赖，启动命令仍然相同：

```bash
uv run --extra w1-fk univis \
  --port 8010 \
  --workspace w1=/path/to/w1_teleop_data \
  --output /path/to/output
```

W1 FK 的默认配置位于 `src/univis/formats/dexforce_w1_teleop/config/default.yaml`。其中 `has_waist`、URDF 路径、关节名称、相机规则等均可按部署环境调整。

## 四、基本使用方法

> version: 0.1.0

围绕可视化，UniVis有多种使用方法，下面给出几种经典用法。

### 4.1 PIKA数据实时采集与可视化

1. 启动 UniVis，将 workspace 之一设置为 PIKA 原始数据存放的目录，另一个 workspace 设置为 output 的目录，用于后续检查导出的 HDF5。

    ```
    uv run univis \
      --port 8010 \
      --workspace raw=/path/to/realtime/rawdata \
      --workspace output=/path/to/output \
      --output /path/to/output
    ```

2. 选择数据源

    <img src="images/data_format.png" alt="选择数据源" width="300">


3. 选择需要查看的 Episode

    <img src="images/episodes.png" alt="选择episode" width="300">

    点击 episode 右侧的单选框可以选中一条episode，可以用于后续的批量标注

4. 数据检查与导出

    <img src="images/usage.png" alt="功能介绍" width="500">

5. 随采随可视化

    点击Refresh，可以重新加载当前目录，看到最新采集的 episode。从而做到采集一条即可处理一条。

    <img src="images/refresh.png" alt="刷新" width="300">

### 4.2 数据质量检测 —— Dynamic Time Warping (DTW)

在模仿学习中，我们通常会定义一条专家轨迹，我们希望每次采集的数据和专家轨迹比较相似。现在，我们可以在 UniVis 中轻松直观地看到 DTW 的结果。

1. 首先打开专家 episode

2. 点击 DTW 展开操作栏，选中 Enable DTW

    <img src="images/dtw.png" alt="DTW" width="300">

3. 然后选择当前 episode 作为 reference

    启动 dtw 后会弹出一个浮动窗口，展示 dtw 指标。

    <img src="images/dtw_metrics.png" alt="DTW metric" width="300">

4. 切换episode，以进行dtw对比

    <img src="images/dtw_vis.png" alt="DTW visualization" width="600">

5. 导出统计结果

    从左侧 episode 处选中若干 episode，点击 Compute selected stats，便会计算出这样一张统计结果表


    <img src="images/dtw_stats.png" alt="DTW stats" width="600">

**进阶设置**:可以在 `src/univis/quality/dtw/config/default.yaml` 中设置 dtw 参数。

### 4.3 Dexforce W1 遥操数据可视化

Dexforce W1 Teleop 格式读取的是全身 `qpos` 遥操数据。UniVis 会先按相机时间戳同步数据，再通过 W1 FK 工具计算左右 EEF pose，最终仍然转换成统一的 `PolicyEpisode` 用于网页可视化和质量检测。

使用前请确认：

1. 已安装 W1 FK extra：`uv sync --extra dev --extra w1-fk`。
2. `src/univis/formats/dexforce_w1_teleop/config/default.yaml` 中的 `urdf_path` 指向本机存在的 W1 URDF。
3. `has_waist` 与当前数据的 FK 坐标系需求一致。

启动示例：

```bash
uv run --extra w1-fk univis \
  --workspace w1=/path/to/dexforce_w1_teleop_root \
  --output /path/to/output
```

进入网页后，将 Input format 选择为 `Dexforce W1 Teleop`，再在对应 workspace 中选择数据目录即可。

### 4.4 补充标注/补充后处理

UniVis 支持以 HDF5 格式为输入，并继续以 HDF5 格式输出，因此可以实现增量修改。使用方式和 4.1 基本一致，只需要将输入格式替换为 HDF5，并找到需要处理的 HDF5 目录即可。

## 测试

运行完整测试：

```bash
cd /home/dex/app/UniVis
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --extra dev pytest -q
```

检查前端脚本语法：

```bash
node --check src/univis/web/static/app.js
node --check src/univis/web/static/components.js
node --check src/univis/web/static/conversion_components.js
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 用于避免系统里的无关 pytest 插件影响当前项目。

### 扩展输入/输出 Format

新增 format 时，不需要修改 `univis.formats.__init__` 或 `app.py`。推荐从模板目录开始：

```text
src/univis/formats/template/
```

复制为新的 format 包后，至少需要完成：

1. 将 `__init__.py.sample` 改名为 `__init__.py`。
2. 实现自己的 `RawEpisodeAdapter`，负责把外部数据源读成 `PolicyEpisode`。
3. 如果支持导出，实现自己的 `EpisodeExporter`。
4. 在 `format_components()` 中返回 adapter/exporter 实例。
5. 如果有格式特有参数，放在该 format 自己的 `config/default.yaml` 中。

真实 format 包只要暴露：

```python
def format_components() -> ComponentBundle:
    return ComponentBundle(
        input_adapters=[MyEpisodeAdapter()],
        output_exporters=[MyEpisodeExporter()],
    )
```

启动时 UniVis 会自动扫描 `src/univis/formats/*`，所有暴露 `format_components()` 的包都会进入 UI 下拉框和 CLI registry。

### 扩展 Quality 功能

新增质量检测功能同样不需要修改顶层 API。推荐从模板目录开始：

```text
src/univis/quality/template/
```

复制为新的 quality 包后，至少需要完成：

1. 将 `__init__.py.sample` 改名为 `__init__.py`。
2. 根据功能类型选择 backend 能力：
   - `PairwiseQualityBackend`：当前 episode 与 reference episode 对比，例如 DTW。
   - `ReferenceBatchQualityBackend`：多条 episode 相对同一个 reference 的统计。
   - `SingleEpisodeQualityBackend`：单条 episode 独立评估，例如 Smooth。
3. 如果需要 Web API，在该功能自己的 `routes.py` 中实现 route builder。
4. 在 `quality_components()` 中返回 backend 和 route builder。
5. 如果有算法参数，放在该 quality 功能自己的 `config/default.yaml` 中。

真实 quality 包只要暴露：

```python
def quality_components() -> QualityComponentBundle:
    return QualityComponentBundle(
        backends=[MyQualityBackend()],
        route_builders=[build_my_quality_router],
    )
```

启动时 UniVis 会自动扫描 `src/univis/quality/*`，所有暴露 `quality_components()` 的包都会进入 `/api/quality/backends`，并自动挂载自己的 `/api/quality/<feature>/...` 路由。
