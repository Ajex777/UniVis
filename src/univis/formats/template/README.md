# UniVis Format 模板

这个目录用于说明“新增一种 UniVis 数据格式”时应该遵守的目录结构和注册约定。

它本身不会被自动注册为真实 format，因为这里没有真正的 `__init__.py`，只有
`__init__.py.sample`。这样它可以作为样例存在，同时不会污染 UI 和 CLI 的格式列表。

## 推荐目录结构

在 `src/univis/formats/<format_name>/` 下创建一个新的 format 包：

```text
<format_name>/
  __init__.py
  adapter.py        # 如果该格式支持读取，则需要
  exporter.py       # 如果该格式支持导出，则需要
  config/
    default.yaml    # 可选，存放该格式自己的结构化配置
```

## 注册约定

真实 format 包的 `__init__.py` 需要暴露 `format_components()`：

```python
FORMAT_ORDER = 100

def format_components() -> ComponentBundle:
    return ComponentBundle(
        input_adapters=[MyEpisodeAdapter()],
        output_exporters=[MyEpisodeExporter()],
    )
```

`FORMAT_ORDER` 是可选字段，但建议提供。它用于稳定 UI 和 CLI 中的格式展示顺序，
避免新增 format 后下拉框顺序突然变化。

## 编写原则

- format 相关的解析、同步、schema、配置都应该留在该 format 自己的目录里。
- 只有通用抽象才应该放到 `univis.base_io.adapters` 和 `univis.base_io.exporters`。
- `PolicyEpisode` 是时间戳对齐后的内存中间格式，但不保存完整图像数组。图像只在
  metadata 中登记相机流信息，真实帧数据由 adapter 的 `get_image_frame()` 按需读取。
- format 特有的可配置行为优先放到结构化 YAML 中，不要把常量散落在代码里。
- 新增 format 时不需要修改 `univis.formats.__init__`。自动扫描会发现所有暴露
  `format_components()` 的 format 包。
- 如果某个 format 只支持读取，可以只返回 `input_adapters`；如果只支持导出，可以只返回
  `output_exporters`。

## 从模板开始

复制这个目录时，建议至少完成以下几步：

1. 将目录名从 `template` 改成真实格式名，例如 `dexforce_w1_teleop`。
2. 将 `__init__.py.sample` 改名为 `__init__.py`。
3. 将 `TemplateEpisodeAdapter` / `TemplateEpisodeExporter` 改成真实类名。
4. 在 `format_components()` 中返回真实 adapter/exporter 实例。
5. 根据需要修改 `config/default.yaml`，并在 format 内部读取它。
