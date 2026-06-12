"""Template output exporter for a UniVis format package.

Exporter 的职责是把 UniVis 内部统一的 `PolicyEpisode` 写成某种外部格式。
它不应该关心 episode 最初来自 raw data、HDF5 还是 GUI，只处理已经同步好的
`PolicyEpisode`。
"""

from __future__ import annotations

from pathlib import Path

from univis.base_io.exporters import EpisodeExporter, ExportResult
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode


class TemplateEpisodeExporter(EpisodeExporter):
    """Example exporter shape for writing PolicyEpisode objects.

    一个真实 exporter 通常需要完成两件事：

    1. `info()`：告诉 registry 这个输出格式叫什么、有哪些别名。
    2. `export()`：把一条 `PolicyEpisode` 写入 `output_root`。
    """

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return exporter metadata used by UI, CLI, and API registries.

        Inputs:
            None. 导出格式的元信息不应该依赖某条 episode。
        Output:
            `ComponentInfo`，用于前端输出格式下拉框、CLI `--output-format`
            解析，以及错误提示。

        Key fields:
            name: 稳定组件名。缺少它时 registry 无法定位 exporter。
            label: 给用户看的名称。缺少它时 UI 展示会不友好。
            aliases: CLI 简写。缺少它不会影响 GUI，但 CLI 会更繁琐。
            description: 简短说明。缺少它不会影响功能，但用户很难判断格式用途。
        """

        return ComponentInfo(
            name="TemplateEpisodeExporter",
            label="Template Output",
            aliases=["Template"],
            description="Example output exporter; copy into a real format package.",
        )

    def export(self, episode: PolicyEpisode, output_root: Path) -> ExportResult:
        """Write one PolicyEpisode into this format's output artifact.

        Inputs:
            episode: 已经完成同步的内部统一数据。它应该来自 adapter 的
                `load_episode()`，而不是 exporter 自己重新读取 raw data。
            output_root: 用户指定的导出根目录。真实 exporter 应负责创建必要的
                子目录或文件。
        Output:
            `ExportResult`，包括 episode_id、exporter_name、output_path、
            success、message。调用方会用它展示导出进度和错误信息。

        Missing parameters:
            如果 `episode` 缺失，exporter 没有可写的数据；如果 `output_root`
            缺失，exporter 不知道写到哪里。真实实现应该尽早抛出清晰错误。

        Design note:
            不建议 exporter 直接修改原始数据目录。导出目标应该由 `output_root`
            控制，这样 GUI 和 CLI 可以复用同一条转换逻辑。
        """

        raise NotImplementedError("template exporter cannot write real episodes")
