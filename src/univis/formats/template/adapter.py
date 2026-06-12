"""Template input adapter for a UniVis format package.

Adapter 的职责是把某种外部数据源转换成 UniVis 内部统一的
`PolicyEpisode`。GUI、CLI、质量检测、导出流程都应该只依赖
`PolicyEpisode`，而不直接理解某个 raw data 或 HDF5 的细节。
"""

from __future__ import annotations

from univis.base_io.adapters import EpisodeSource, ImageFrame, RawEpisodeAdapter, SourceValidation
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, PolicyEpisodeMetadata


class TemplateEpisodeAdapter(RawEpisodeAdapter):
    """Example adapter shape for file-backed or dataset-backed input formats.

    一个真实 adapter 通常需要完成三件事：

    1. `list_metadata()`：快速扫描数据源，告诉 UI 有哪些 episode。
    2. `load_episode()`：按 episode id 读取并同步成 `PolicyEpisode`。
    3. `get_image_frame()`：如果支持图像预览，按需返回单帧编码图像。
    4. 可选 annotation 方法：支持网页写回语言标注。

    Important:
        `PolicyEpisode` 不保存完整图像数组。它只保存相机 metadata 和同步后的
        轨迹/state。网页播放图像时，会根据 camera key 和 frame index 再回调
        adapter 的图像接口。
    """

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata used by UI, CLI, and API registries.

        Inputs:
            None. 这是类级别元信息，不应该依赖某个具体数据目录。
        Output:
            `ComponentInfo`，用于前端下拉框、CLI 参数解析、错误提示。

        Key fields:
            name: 稳定的组件名，推荐使用类名。缺少它时 registry 无法区分组件。
            label: 给用户看的名称。缺少它时 UI 只能展示不友好的内部名。
            aliases: CLI 简写，例如 `HDF5`、`PIKARaw`。缺少它不会影响功能，
                但命令行会更难用。
            capabilities: UI 能力声明。缺少某个能力时，前端应假设该能力不可用，
                例如不显示写回 annotation 或图像预览相关入口。
        """

        return ComponentInfo(
            name="TemplateEpisodeAdapter",
            label="Template Input",
            aliases=["Template"],
            description="Example input adapter; copy into a real format package.",
            capabilities={
                "supports_images": False,
                "supports_annotation_writeback": False,
            },
        )

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Check whether the source can be read by this adapter.

        Inputs:
            source: 用户选择的数据源。通常 `source.root_path` 是目录或文件路径，
                `source.options` 是该 adapter 自己定义的额外参数。
        Output:
            `SourceValidation`，告诉 UI/API 这个目录是否可读，以及大致发现了
            多少 episode。

        Missing parameters:
            如果 `source` 或 `source.root_path` 缺失，真实 adapter 应返回
            `valid=False` 和清晰错误信息，而不是让底层 `Path` 报难懂的异常。

        Default behavior:
            基类会调用 `list_metadata()`。如果你的格式扫描很慢，建议重写此方法，
            做更轻量的目录结构检查。
        """

        return super().validate_source(source)

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List available episodes from the source.

        Inputs:
            source: 数据源描述。真实实现通常要求 `source.root_path` 存在。
        Output:
            `PolicyEpisodeMetadata` 列表。每个 metadata 至少应该包含：
            episode_id、num_frames、fps、camera 列表、annotation 初始值等。

        Missing parameters:
            如果没有 `source.root_path`，adapter 无法知道扫描哪个目录，应该抛出
            `ValueError("source.root_path is required ...")` 之类的明确异常。

        Design note:
            这个方法应该尽量快，不要读取全部图像或大数组。UI 会频繁调用它来刷新
            episode 列表。metadata 里的 `cameras` 只描述有哪些相机流，不代表
            图像已经被加载进 `PolicyEpisode`。
        """

        raise NotImplementedError("template adapter cannot list real episodes")

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one synchronized PolicyEpisode from the source.

        Inputs:
            episode_id: 来自 `list_metadata()` 的稳定 id。缺少或不存在时，应返回
                清晰错误，例如 `ValueError(f"unknown episode: {episode_id}")`。
            source: 数据源描述。通常仍然需要 `source.root_path`。
        Output:
            完整的 `PolicyEpisode`。它应该已经完成时间戳对齐，且每一帧都包含
            双臂 eef pose、gripper、timestamp 等统一字段。

        Missing parameters:
            如果 `source.root_path` 缺失，就无法定位原始数据；如果 `episode_id`
            缺失，就无法定位具体 episode。这两类错误都应该在 adapter 层显式报出。

        Design note:
            HDF5 并不是 UniVis 的内存格式。无论输入来自 raw data、HDF5 还是其他
            数据集，读入后都应该统一变成 `PolicyEpisode`。

            图像仍然不要塞进 `PolicyEpisode`。如果这个 episode 有图像，只需要在
            metadata.cameras 中记录 camera key、label、width、height 等信息；
            实际图像由 `get_image_frame()` 按需读取。
        """

        raise NotImplementedError("template adapter cannot load real episodes")

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one encoded image frame for web preview.

        Inputs:
            episode_id: 来自 `list_metadata()` 的稳定 id，用于定位具体 episode。
            camera_key: 来自 `PolicyEpisodeMetadata.cameras` 的相机 key。缺少或
                不存在时，adapter 应抛出清晰错误，例如 `unknown camera_key`。
            frame_index: 同步后的帧索引，通常对应 `PolicyEpisode.frames[index]`。
                超出范围时应抛出明确错误，而不是返回错帧。
            source: 数据源描述。多数文件型 adapter 仍需要 `source.root_path`。
        Output:
            `ImageFrame(data=..., media_type=...)`。`data` 应是已编码图片字节，
            例如 JPEG/PNG；`media_type` 应是 `image/jpeg` 或 `image/png`。

        Missing parameters:
            如果缺少 `camera_key`，前端无法知道取哪路图像；如果缺少
            `frame_index`，前端无法同步图像和轨迹；如果该 adapter 不支持图像，
            直接继承基类实现即可，它会抛出 `NotImplementedError`。

        Design note:
            如果 `info().capabilities["supports_images"]` 为 True，真实 adapter
            就应该实现这个方法。否则 UI 可能会显示图像面板但请求失败。
        """
        raise NotImplementedError(f"image frames are not supported by {self.info().name}")

    def update_annotation(self, episode_id, annotation, source = None):
        """Write back updated annotation from the web UI."""
        raise NotImplementedError(f"annotation write-back is not supported by {self.info().name}")