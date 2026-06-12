"""Template backend for a UniVis quality feature.

Quality backend 的职责是基于 `PolicyEpisode` 计算质量报告。它不应该直接理解
某个 raw data、HDF5 或遥操目录结构；这些输入格式差异应该已经被 adapter 抹平。
"""

from __future__ import annotations

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.quality.base import (
    PairwiseQualityBackend,
    ReferenceBatchQualityBackend,
    SingleEpisodeQualityBackend,
)
from univis.quality.template.models import (
    TemplateBatchReport,
    TemplateCompareReport,
    TemplateQualityConfig,
    TemplateSingleEpisodeReport,
)


class TemplateQualityBackend(
    PairwiseQualityBackend,
    ReferenceBatchQualityBackend,
    SingleEpisodeQualityBackend,
):
    """Example backend showing all supported quality capability shapes.

    真实功能通常不需要同时实现三种能力。请根据实际功能删除不需要的父类和方法：

    - 只做 current/reference 对比：保留 `PairwiseQualityBackend.compare()`。
    - 做 selected episodes 相对 reference 的统计：保留
      `ReferenceBatchQualityBackend.selected_stats()`。
    - 只评估单条 episode：保留 `SingleEpisodeQualityBackend.assess()`。
    """

    def __init__(self, config: TemplateQualityConfig | None = None) -> None:
        """Initialize backend-level dependencies and config.

        Inputs:
            config: 可选配置模型。缺失时，真实 backend 通常应从
                `config/default.yaml` 读取默认值。
        Output:
            可复用 backend 实例。backend 应该是无 UI 状态的；reference 选择等交互
            状态应由前端或 service 管理。
        """

        self.config = config or TemplateQualityConfig()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return backend metadata used by UI, CLI, and API registries.

        Inputs:
            None. 这是类级别元信息，不应依赖某个具体 episode。
        Output:
            `ComponentInfo`，用于 `/api/quality/backends`、前端功能块、CLI
            诊断信息。

        Key fields:
            name: 稳定组件名，推荐使用类名。缺少它时 service 无法按名称查找 backend。
            label: 给用户看的名称。缺少它时 UI 只能展示内部类名。
            aliases: CLI 或未来配置中的简写。缺少它不会影响 API，但会降低易用性。
            capabilities: 建议声明该 backend 支持哪些能力，方便 UI 避免硬编码。
        """

        return ComponentInfo(
            name="TemplateQualityBackend",
            label="Template Quality",
            aliases=["TemplateQuality"],
            description="Example quality backend; copy into a real quality package.",
            capabilities={
                "pairwise": True,
                "reference_batch": True,
                "single_episode": True,
            },
        )

    def compare(
        self,
        current: PolicyEpisode,
        reference: PolicyEpisode,
    ) -> TemplateCompareReport:
        """Compare one current episode against one reference episode.

        Inputs:
            current: 当前被评估的 `PolicyEpisode`。
            reference: 用户选定或自动选定的 reference/expert `PolicyEpisode`。
        Output:
            可 JSON 序列化的 compare report。

        Missing parameters:
            如果功能需要 reference 但没有传入，说明调用方选错了 backend 能力；
            应在 service 或 route 层报出清晰错误。不要在这里默默降级成
            single-episode 评估，否则 GUI 和 CLI 指标会变得不一致。
        """

        score = abs(current.metadata.num_frames - reference.metadata.num_frames)
        return TemplateCompareReport(
            current_episode_id=current.metadata.episode_id,
            reference_episode_id=reference.metadata.episode_id,
            score=float(score),
            passed=score <= self.config.max_frame_delta,
        )

    def selected_stats(
        self,
        episodes: list[PolicyEpisode],
        reference: PolicyEpisode,
    ) -> TemplateBatchReport:
        """Aggregate selected episodes against one reference.

        Inputs:
            episodes: 待统计的 episode 列表。调用方通常应提前过滤掉 reference 自身。
            reference: 统计基准 episode。
        Output:
            可 JSON 序列化的 batch report。

        Missing parameters:
            如果 `episodes` 为空，真实 backend 应返回空统计或明确提示，取决于
            UI 需要。不要伪造一个 0 分，避免用户误解为数据质量很好。
        """

        scores = [self.compare(episode, reference).score for episode in episodes]
        mean_score = sum(scores) / len(scores) if scores else None
        return TemplateBatchReport(
            reference_episode_id=reference.metadata.episode_id,
            selected_episode_ids=[episode.metadata.episode_id for episode in episodes],
            mean_score=mean_score,
        )

    def assess(self, episode: PolicyEpisode) -> TemplateSingleEpisodeReport:
        """Assess one episode without a reference episode.

        Inputs:
            episode: 当前被评估的 `PolicyEpisode`。
        Output:
            可 JSON 序列化的 single-episode report。

        Missing parameters:
            如果某个质量功能不需要 reference，就应该实现这个方法并继承
            `SingleEpisodeQualityBackend`，而不是要求调用方构造一个假的 reference。
        """

        return TemplateSingleEpisodeReport(
            episode_id=episode.metadata.episode_id,
            num_frames=episode.metadata.num_frames,
            passed=episode.metadata.num_frames >= self.config.min_frames,
        )
