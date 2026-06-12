# UniVis Quality 模板

这个目录用于说明“新增一种 UniVis 质量检测功能”时应该遵守的目录结构和注册约定。

它本身不会被自动注册为真实 quality 功能，因为这里没有真正的 `__init__.py`，只有
`__init__.py.sample`。这样它可以作为样例存在，同时不会污染 `/api/quality/backends`
和前端 Quality 区域。

## 推荐目录结构

在 `src/univis/quality/<feature_name>/` 下创建一个新的 quality 功能包：

```text
<feature_name>/
  __init__.py
  backend.py          # 核心质量检测逻辑
  routes.py           # 可选；如果需要 Web/API 入口，则需要
  models.py           # 可选；Pydantic 配置、报告、请求响应模型
  metrics.py          # 可选；纯数学/统计函数
  settings.py         # 可选；读取结构化 YAML 配置
  config/
    default.yaml      # 可选；该功能自己的默认参数
```

## 注册约定

真实 quality 包的 `__init__.py` 需要暴露 `quality_components()`：

```python
QUALITY_ORDER = 100

def quality_components() -> QualityComponentBundle:
    return QualityComponentBundle(
        backends=[MyQualityBackend()],
        route_builders=[build_my_quality_router],
    )
```

`QUALITY_ORDER` 是可选字段，但建议提供。它用于稳定后端 registry 和前端展示顺序。

## Backend 能力选择

Quality backend 应根据功能形态选择合适的基类：

- `PairwiseQualityBackend`：需要比较当前 episode 和 reference episode，例如 DTW。
- `ReferenceBatchQualityBackend`：需要对多个 episode 相对同一个 reference 做统计，例如 selected DTW stats。
- `SingleEpisodeQualityBackend`：只评估单条 episode，不需要 reference，例如 smoothness。

一个 backend 可以同时继承多个能力。例如 DTW 同时支持 `compare()` 和 `selected_stats()`；
Smooth 只需要实现 `assess()`。

## API 可扩展性

如果该功能需要 API，请在自己的 `routes.py` 中提供 route builder：

```python
def build_my_quality_router(service: QualityService) -> APIRouter:
    router = APIRouter(prefix="/my-quality")
    ...
    return router
```

顶层 `api/quality.py` 只负责聚合，不需要为每个功能手动添加路由。只要你的
`quality_components()` 返回了 `route_builders`，应用启动时就会自动挂载到：

```text
/api/quality/<your-prefix>/...
```

## 编写原则

- feature 特有的算法、模型、配置、路由都应该留在该 feature 自己的目录里。
- 只有真正通用的抽象才应该放到 `univis.quality.base`。
- backend 的输入应该尽量是 `PolicyEpisode`，避免直接依赖某个 raw data 或 HDF5 结构。
- 如果参数未来会调整，优先放到结构化 YAML 中，并通过 `settings.py` 读取。
- API route 只做请求解析和异常转换，不要把算法逻辑写进 route。
- CLI 和 GUI 应该尽量共用 `QualityService` 和同一个 backend，避免两套指标不一致。

## 从模板开始

复制这个目录时，建议至少完成以下几步：

1. 将目录名从 `template` 改成真实功能名，例如 `reachability`。
2. 将 `__init__.py.sample` 改名为 `__init__.py`。
3. 将 `TemplateQualityBackend` 改成真实类名。
4. 按功能形态选择并实现 `compare()`、`selected_stats()` 或 `assess()`。
5. 如果需要 API，将 `build_template_quality_router()` 改成真实 route builder。
6. 在 `quality_components()` 中返回真实 backend 和 route builder。
