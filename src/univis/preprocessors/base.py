"""Abstract base class for PolicyEpisode preprocessors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, PolicyEpisodeMetadata


class EpisodePreprocessor(ABC):
    """Transform PolicyEpisode data and/or adapter image serving.

    Two extension points:
      - preprocess_episode: transform frame data (action masking, etc.)
      - preprocess_adapter: wrap adapter for image-level transforms (image masking)

    Both default to identity so subclasses only override what they need.
    """

    @abstractmethod
    def info(self) -> ComponentInfo:
        """Return component metadata (instance method — preprocessors are parameterized)."""

    def preprocess_episode(self, episode: PolicyEpisode) -> PolicyEpisode:
        """Transform episode frame data. Default: identity."""
        return episode

    def preprocess_adapter(self, adapter, metadata: PolicyEpisodeMetadata):
        """Wrap adapter for image-level preprocessing. Default: identity."""
        return adapter
