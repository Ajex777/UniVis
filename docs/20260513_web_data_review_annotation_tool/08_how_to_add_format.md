# 如何新增数据集格式

本文档描述了如何为 UniVis 新增一种数据集格式。以 LeRobot v3 adapter 为主线示例，
同时引用已有的 compressed HDF5 格式来说明每一步。

## 概述

UniVis 中的**格式（format）**是 `src/univis/formats/` 下的一个独立 Python 子包，
负责教会播放器如何读取（以及可选地写入）某种特定数据布局。每种格式可独立测试，
并通过组件系统自动注册——应用程序的其他部分不需要对具体格式类做 `isinstance` 判断。

每个格式子包包含以下三个文件：

| 文件 | 是否必需 | 作用 |
|------|---------|------|
| `schema.py` | 是 | 目录布局常量、合法性校验、帧解码等无状态辅助函数 |
| `adapter.py` | 是 | 一个 `RawEpisodeAdapter` 子类 |
| `__init__.py` | 是 | 导出 `ComponentBundle` 工厂函数 |

格式包可选地包含 `exporter.py`（一个 `EpisodeExporter` 子类），但多数格式初期只需 adapter。

## 详细步骤

### 1. 理解原始数据格式

在写代码之前，你需要从原始数据中搞清楚以下问题：

* **目录结构** — episode、帧和元数据分别存放在哪里？
* **动作/状态编码** — 维度、数据类型、坐标系、夹爪约定
* **图像存储方式** — 单文件（JPEG/PNG）、视频容器（MP4）还是自定义块（chunk）
* **标注来源** — 是否有 `language_prompt`、任务描述或侧文件？
* **Episode 边界** — 如何判断一个 episode 从哪里开始、在哪里结束？

**示例：LeRobot v3 数据集**

```
root/
  meta/
    info.json          # codebase_version, fps, features, chunks_size
    episodes/
      chunk-000/
        file-000.parquet   # 每个 episode 的元数据行
    stats.json
    tasks.parquet
  data/
    chunk-000/
      file-000.parquet     # 合并后的帧数据（所有 episode 在一个表中）
  videos/
    observation.images.cam_0_rgb/
      chunk-000/
        file-000.mp4       # 拼接后的 MP4（所有 episode 连续存储）
```

我们为这个格式做了以下关键设计决策：

- **轨迹向量**：10-D float32 `[x, y, z, rot6d(6), gripper]`（单臂 UMI）。
  本数据集中 `observation.state` 不可用，实际轨迹记录在 `action` 列中。
  通过将单臂数据映射到右臂，并填充左臂为零位移 + identity 旋转 + 夹爪 1.0，
  使现有的双臂 `PolicyEpisode` 模型无需改动即可消费。

- **图像帧**：存储在单个 AV1 编码的 MP4 中。PyAv 无法在 AV1 中精确定位，
  因此首次访问时用 ffmpeg 批量解码 episode 对应的时间段，并将 JPEG 帧缓存在内存中。

- **Episode 边界**：`meta/episodes` parquet 中的 `dataset_from_index` / `dataset_to_index`
  定义了数据行范围，`videos/{key}/from_timestamp` / `to_timestamp` 定义了视频段落。

- **标注**：存储在数据集根目录下的 JSONL 侧文件中（`univis_annotations.jsonl`）。

### 2. 创建格式子包

```bash
mkdir -p src/univis/formats/<format_name>
touch src/univis/formats/<format_name>/__init__.py
touch src/univis/formats/<format_name>/schema.py
touch src/univis/formats/<format_name>/adapter.py
```

### 3. 编写 `schema.py`

schema 模块包含读取格式目录布局的**无状态辅助函数**。不应从 `univis.adapters` 导入，
也不持有可变状态。典型的辅助函数有：

| 函数 | 用途 |
|------|------|
| `require_root(root)` | 校验数据集根目录；不合法时抛出异常 |
| `load_info(root)` | 读取格式级元数据（fps、features、相机列表） |
| `load_episode_records(root)` | 返回每个 episode 的元数据列表（list of dicts） |
| `read_episode_action(root, record)` | 返回 `(N, 10)` float32 动作数组 |
| `read_timestamps(root, record)` | 返回 `(N,)` float32 时间戳 |
| `camera_keys(info)` / `camera_streams(info)` | 提取相机元数据 |
| `action_to_qpos(action)` | 将原始状态向量映射为 20-D 双臂 qpos |
| `extract_episode_frames(root, record, camera_key, fps)` | 解码单个 episode 的全部帧 |

模块控制在 **250 行以内**。如果辅助函数过多，可将领域特定逻辑（如 SE(3) 运算）
拆分到 `univis.utils` 中。

### 4. 编写 `adapter.py`

继承 `RawEpisodeAdapter` 并实现必需的方法：

```python
from univis.adapters.base import RawEpisodeAdapter, EpisodeSource, ImageFrame, SourceValidation
from univis.core.components import ComponentInfo

class MyFormatAdapter(RawEpisodeAdapter):

    @classmethod
    def info(cls) -> ComponentInfo:
        """注册表下拉菜单使用的元数据。"""
        return ComponentInfo(
            name="MyFormatAdapter",
            label="显示名称",
            description="简要描述……",
            capabilities={
                "source": {
                    "directory_upload": "recursive",  # 或 "top_level_matching"
                    "supports_file_upload": False,
                },
                "conversion": {"default_status": "pending", "default_progress": 0.0},
            },
        )

    def list_metadata(self, source) -> list[PolicyEpisodeMetadata]: ...
    def validate_source(self, source) -> SourceValidation: ...
    def load_episode(self, episode_id, source) -> PolicyEpisode: ...
    def get_image_frame(self, episode_id, camera_key, frame_index, source) -> ImageFrame: ...
    def update_annotation(self, episode_id, annotation, source) -> Annotation: ...
```

#### `capabilities.source` 标志

| 标志 | 值 | 前端上传行为 |
|------|-----|-------------|
| `directory_upload` | `"top_level_matching"` | 浏览器选择目录后，仅上传顶层匹配 `file_extensions` 的文件。HDF5 使用此模式。 |
| `directory_upload` | `"recursive"` | 浏览器递归遍历整个目录树。PIKA raw 和 LeRobot v3 使用此模式。 |

这些标志由前端的 `SourceIO` 模块消费，前端据此决定是否递归扫描，
无需在 JS 中硬编码格式名称。

#### Episode ID 约定

使用源数据中的 `str(episode_index)` 作为稳定的 `episode_id`。
前端在所有后续 API 调用中都使用这个 id。

#### 图像帧服务

三种常见模式，从简单到复杂排列：

1. **独立图像文件**（PIKA raw）：从磁盘读取文件，直接返回字节。
   同步结果可缓存，但图像本身按需服务。

2. **压缩 chunk**（compressed HDF5）：用 h5ffmpeg 解码 chunk，缓存解码后的 numpy 数组，
   提取单个帧，编码为 JPEG。

3. **视频容器**（LeRobot v3）：首次访问时用 ffmpeg 批量解码 episode 对应的视频段落，
   将所有帧缓存在内存中。这是最昂贵的模式，但在容器编码（AV1）无法高效随机访问时不可避免。

在 adapter 中添加内存帧缓存（`_frame_cache`），按 episode id + camera key 建立索引。
重写 `clear_caches()` 以在用户切换数据源时释放内存（基类提供了空操作的默认实现）。

#### 单臂→双臂适配

`PolicyEpisode` 期望 20-D qpos：`[left_xyz, left_rot6d, left_gripper, right_xyz, right_rot6d, right_gripper]`。
如果源数据集是单臂数据（10-D），需要决定它代表哪个臂——UMI 风格的数据通常是右臂。
未使用的臂填充为零位移 + identity rot6d + 夹爪 1.0：

```python
# 单臂 action → 双臂 qpos（右臂 = 数据集 action）
left = np.zeros((n, 10), dtype=np.float32)
left[:, 3] = 1.0   # rot6d identity
left[:, 7] = 1.0   # rot6d identity
left[:, 9] = 1.0   # gripper
right = action[:, :10]
qpos = np.concatenate([left, right], axis=1)
```

对于相机布局，为未使用的臂返回一个合成全黑相机，为活跃的臂返回真实视频相机。
使用统一命名（`cam_left_wrist` / `cam_right_wrist`）与 PIKA/HDF5 格式保持一致。

### 5. 编写 `__init__.py`

```python
from univis.core.components import ComponentBundle
from univis.formats.<format_name>.adapter import MyFormatAdapter

def <format_name>_components() -> ComponentBundle:
    return ComponentBundle(
        input_adapters=[MyFormatAdapter()],
        output_exporters=[],  # 或 [MyFormatExporter()]
    )
```

### 6. 注册到 `univis/formats/__init__.py`

在 `load_format_components()` 中加入新的工厂函数：

```python
from univis.formats.<format_name> import <format_name>_components

def load_format_components() -> ComponentBundle:
    components = ComponentBundle()
    for builder in (compressed_hdf5_components, lerobot_v3_components, <format_name>_components):
        ...
```

顺序很重要：它决定了 UI 下拉菜单和注册表 API 响应中 adapter 的排列顺序。

### 7. 安装依赖

如果新格式需要额外的 Python 包（如 parquet 需要 `pyarrow`，视频需要 `av`），
用 `uv add <package>` 添加。

### 8. 编写测试

在 `tests/` 下创建（或扩展）测试文件，覆盖以下内容：

- 用该格式的目录布局创建最小内存数据集
- 验证 `validate_source` 通过和不通过的情况
- 加载一个 episode，检查帧数、qpos 形状、相机 key
- 请求若干图像帧，验证 content-type 和体积
- 如果支持标注写回，测试写入/读取一致性

用 `pytest tests/ -v` 运行。

### 9. 更新注册表测试

`tests/test_api_registry.py` 中的 `test_registry_endpoint_lists_real_input_adapters`
断言了精确的 adapter 名称列表。将新 adapter 名称加入预期列表。

### 10. 更新文档

- `progress.md` — 记录新格式及关键设计决策
- `findings.md` — 记录该格式特有的边界情况（如 AV1 无法 seek 的限制）

## 检查清单

- [ ] `schema.py` 包含无状态辅助函数，不导入 adapter 模块
- [ ] `adapter.py` 实现 `RawEpisodeAdapter`，含帧缓存，重写 `clear_caches`
- [ ] `__init__.py` 导出 `ComponentBundle` 工厂
- [ ] `formats/__init__.py` 注册新工厂
- [ ] `capabilities.source` 标志正确设置
- [ ] Episode ID 是稳定的字符串
- [ ] 单臂数据正确 pad 到 20-D qpos
- [ ] 图像首次访问延迟可接受（目标 < 500 ms）
- [ ] 所有文件 ≤ 250 行（超出时在文件头注释说明原因）
- [ ] `pytest tests/ -v` 包含新 adapter 后全部通过
- [ ] 新依赖通过 `uv add` 添加
- [ ] 文档已更新
