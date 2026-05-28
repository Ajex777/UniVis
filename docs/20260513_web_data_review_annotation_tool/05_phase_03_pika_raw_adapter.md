# Phase 03: Pika Raw Format

## Goal

实现 `univis.formats.pika_raw`，把 PIKA raw data 同步为 `PolicyEpisode`。拆分后需要和当前转换脚本逐帧一致，作为回归测试标准。

## Scope

- 扫描 PIKA raw episode root 和单个 episode。
- 读取可变相机数据，但 action/state 第一版仍固定为双臂 eef pose + gripper。
- 复用或迁移当前同步逻辑：timestamp files、左右相机匹配、pose/gripper 插值、静止边界裁剪、downsample、policy vector 构建。
- 读取和写回原始 `instructions.json`。
- 输出 `PolicyEpisode`，供 viewer、annotation、HDF5 exporter 复用。

## Current Implementation Notes

- PIKA raw 已迁移为独立 format 子包：`src/univis/formats/pika_raw/`。`univis.adapters.pika_*` 仅保留兼容导入，不再承载真实实现。
- `pika_raw_components()` 通过 `univis.formats.load_format_components()` 注册 `PikaRawEpisodeAdapter`，`app.py` 不再硬编码 PIKA adapter。
- PIKA 专属目录布局、相机 key/label、同步容差、静止边界裁剪、pose rebase、gripper 归一化等默认参数集中在结构化 YAML：`src/univis/formats/pika_raw/config/default.yaml`。
- 已新增 `PikaEpisodeSynchronizer`，按 YAML 配置执行同步顺序：左相机为基准、右相机 nearest match、pose/gripper 插值、首尾静止裁剪、downsample、双臂 20D qpos 拼接。
- 当前实现不依赖 `dexechain/embodichain`，SE(3) 的 `xyz+rpy -> matrix -> xyz6d` 已在 UniVis 内部实现。
- raw 图像不进入 `PolicyEpisode` 内存主体，adapter 通过 `get_image_frame()` 按需读取同步后的原始图片，并尽量原样透传 JPEG/PNG。
- `instructions.json` 已支持写回。写回时优先更新已有的 `instruction/text/prompt/language_prompt` 字段；没有这些字段时新增 `language_prompt`。
- 前端目录选择在 `PIKA Raw` 模式下会递归收集选中目录内文件并上传到 server staging，然后由 adapter 扫描。
- 已用 `/home/dex/app/tmp/pika_demo` 做真实目录烟测：默认参数下可识别 2 条 synchronized PIKA episode。
- 已实现 adapter-backed image-preserving HDF5 export：PIKA raw 图像仍由 adapter 懒加载，`HDF5EpisodeExporter` 写出真实 chunked image datasets。

## Remaining Work

- 与 legacy converter 进行更严格的 fixture 回归比对，确认 qpos 与 frame path 选择逐帧一致。
- 如需更多 PIKA 变体，优先扩展 `config/default.yaml` 或新增 YAML 配置加载入口，而不是在 adapter/sync 里继续增加硬编码。

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
- 不移除第一版中必要的兼容导入，但真实实现必须隔离在 format 子包内。

## Named Workspace Source Flow

PIKA raw 目录通常包含大量图片和 JSON，浏览器上传整个目录会触发 multipart 文件数限制，也会造成不必要的数据复制。第一版本机工具应改为 local-first workspace 模式：

1. Server 启动时通过 `--workspace name=/abs/path` 注册一个或多个 named workspace。
2. 前端通过 `/api/workspaces` 获取可用 workspace，通过 `/api/workspaces/{name}/children?path=...` 浏览 server 可见目录。
3. 用户在前端选择 workspace 内的相对目录或 HDF5 文件后，通过 `/api/workspaces/source` 激活数据源。
4. Adapter 直接读取 server 本机路径，不上传 raw 文件，因此可以支持“采集一条，刷新目录，立刻可视化一条”。
5. 前端 source 区域必须显示当前模式小字，例如 `Mode: workspace · raw_data:/session_001` 或 `Mode: upload fallback`。

Upload flow 保留为 fallback，不作为 PIKA raw 的推荐路径。
