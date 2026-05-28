# UniVis

UniVis 是一个面向双臂具身操作的本地优先 Web 可视化、审查、标注与导出工具，核心思想是把不同来源的数据统一转换成内存中的同步轨迹 `PolicyEpisode`，再由同一套网页界面完成可视化、语言标注、质量审查和批量导出。

## 项目目标

UniVis 希望替代彼此独立的数据转换、数据预处理、数据标注、数据质量检查等阶段，让数据处理流程变成：

1. 选择一个本机数据目录。
2. 选择输入数据格式，例如 PIKA raw、compressed HDF5、LeRobot v3。
3. 在网页中逐条查看图像、轨迹、夹爪状态和可达性提示。
4. 给 episode 写入语言标注、接受或拒绝审查结果。
5. 将当前 episode 或所有 accepted episode 批量导出到目标格式。

Version 0.1 假设 server 和 browser 运行在同一台机器上，因此使用 named workspace 共享本机目录，避免大规模上传原始图片或视频。

## 设计概述

UniVis 的主要数据链路是：

```text
RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter
```

`RawEpisodeAdapter` 负责读取某一种输入格式，并输出帧同步的 `PolicyEpisode`。`EpisodeExporter` 负责把 `PolicyEpisode` 导出成某一种目标格式。网页只关心统一的 API，因此新增数据格式时不需要重写 UI。

当前已接入的输入格式包括 compressed HDF5、PIKA raw 和 LeRobot v3。当前主要导出格式是 compressed HDF5。

## 安装

建议使用 Python 3.10 和 uv：

```bash
cd /home/dex/app/UniVis
python3.10 -m pip install --user uv
uv sync --extra dev
```

如果你的机器上 `uv` 已安装在 `~/.local/bin/uv`，也可以直接使用：

```bash
cd /home/dex/app/UniVis
~/.local/bin/uv sync --extra dev
```

## 启动

最常用的启动方式是同时配置输入 workspace 和导出 output root：

```bash
cd /home/dex/app/UniVis
uv run univis \
  --host 127.0.0.1 \
  --port 8010 \
  --workspace raw=/home/dex/app/data \
  --workspace hdf5=/home/dex/app/datasets \
  --output /home/dex/app/exports
```

启动后打开：

```text
http://127.0.0.1:8010
```

`--workspace NAME=PATH` 可以重复传入。`NAME` 会显示在网页的 Workspace source 下拉框中，`PATH` 是 server 端能直接访问的数据根目录。

`--output PATH` 指定导出的根目录。网页里的输出路径输入框只填写这个根目录下的相对子路径，例如 `sort_book_0509/pos1`，最终会导出到 `/home/dex/app/exports/sort_book_0509/pos1`。

如果不指定 `--output`，默认导出到项目目录下的 `.univis/exports`。

## 使用

### 选择数据源

1. 在左侧先选择 `Input format`，例如 `PIKA Raw` 或 `Compressed HDF5`。
2. 选择 `Workspace source`，例如 `raw` 或 `hdf5`。
3. 用目录浏览器进入具体数据目录。
4. 点击 `Use current` 加载当前目录，或选择列表中的某一项后点击 `Use selected`。

PIKA raw 通常选择包含多个 `episode*` 子目录的数据目录，也可以直接选择某一个 episode 目录。HDF5 通常选择包含 `.hdf5` 文件的目录。

<!-- TODO screenshot: 放置“左侧数据源选择区域”的截图，重点展示 Input format、Workspace source、Use current/Use selected。 -->

### 浏览与播放

加载数据后，左侧 episode 列表会展示当前 source 中的 episode。点击任意 episode 可以切换查看。中间区域展示多路相机图像和轨迹，底部时间轴支持逐帧前进、后退和自动播放。

播放速度支持 `0.5x`、`1x`、`2x`、`3x`。如果当前数据带有可达性结果，轨迹区域会展示可达与不可达帧的提示。

<!-- TODO screenshot: 放置“主可视化页面”的截图，包含相机、轨迹、时间轴和右侧信息面板。 -->

### 标注与审查

右侧 Annotation 面板可以编辑语言标注、审查状态和 notes。常用状态是：

- `pending`：尚未审查。
- `accepted`：确认可用于导出或训练。
- `rejected`：拒绝使用。

点击 `Save` 后，标注会通过当前输入 adapter 写回对应的数据源。PIKA raw 会写回 `instructions.json`，HDF5 会直接回写 HDF5 文件。

左侧 episode 列表支持批量选择。选中多个 episode 后，可以把当前 annotation 批量应用到这些 episode。

<!-- TODO screenshot: 放置“Annotation 面板和批量选择 episode”的截图。 -->

### 导出

1. 在左侧选择 `Output format`，例如 `HDF5 Exporter`。
2. 在右侧 Conversion 面板填写输出相对子路径，例如 `sort_book_0509/pos1`。
3. 点击 `Export current` 导出当前 episode。
4. 点击 `Export accepted` 导出所有状态为 `accepted` 的 episode。

导出任务会在后台运行，面板下方会显示最近任务的进度。每次导出会在目标目录生成数据文件，并写入 `conversion_report.json`。

<!-- TODO screenshot: 放置“Conversion 面板”的截图，重点展示 Output root、相对子路径输入框、Export current/accepted 和任务进度。 -->

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

## 可扩展性

UniVis 的扩展点尽量围绕抽象类组织：

- 新输入格式：实现一个新的 `RawEpisodeAdapter`，把自定义 raw data、HDF5、视频数据或其他基于 EEF pose 的数据映射成 `PolicyEpisode`。
- 新输出格式：实现一个新的 `EpisodeExporter`，把 `PolicyEpisode` 导出成 HDF5、LeRobot 或其他训练格式。
- 新预处理：实现 preprocessor，在导出前对 episode 或图像读取器做动作 masking、图像 masking、裁剪等处理。
- 新可达性后端：实现 `ReachabilityBackend`，可以先接 dexechain IK，未来再替换为独立 IK backend。

因此，长期目标是让 UniVis 逐渐成为独立于 dexechain/embodichain 的数据审查与转换工具。业务格式、导出格式、预处理和 IK 都可以作为插件式模块逐步替换，而网页交互层保持稳定。
