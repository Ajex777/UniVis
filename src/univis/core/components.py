"""Shared component metadata and registry helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class ComponentInfo(BaseModel):
    """Serializable metadata for a pluggable UniVis component.

    Inputs:
        name: Stable class-like identifier.
        label: Human-friendly display label.
        aliases: Short command-line names matched case-insensitively.
        description: Short explanation for UI dropdowns and diagnostics.
        capabilities: UI-safe behavior flags that avoid component-specific branching.
    Output:
        JSON-ready metadata shared by adapters, exporters, and backends.
    """

    name: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    capabilities: dict[str, object] = Field(default_factory=dict)


@dataclass
class ComponentBundle:
    """Adapter/exporter instances contributed by a format subpackage."""

    input_adapters: list[object] = field(default_factory=list)
    output_exporters: list[object] = field(default_factory=list)
    preprocessors: list[object] = field(default_factory=list)


@dataclass
class ComponentRegistry:
    """In-memory registry for pluggable UniVis components.

    Inputs:
        input_adapters: Registered raw/HDF5 episode adapters.
        output_exporters: Registered output format exporters.
        reachability_backends: Registered reachability implementations.
        quality_backends: Registered trajectory quality implementations.
    Output:
        Registry object that can produce API-safe dropdown metadata.
    """

    input_adapters: list[object] = field(default_factory=list)
    output_exporters: list[object] = field(default_factory=list)
    reachability_backends: list[object] = field(default_factory=list)
    quality_backends: list[object] = field(default_factory=list)
    preprocessors: list[object] = field(default_factory=list)

    def api_payload(self) -> dict[str, list[dict[str, object]]]:
        """Return registry contents for API consumers.

        Inputs:
            None. The registry reads `info()` from each component instance.
        Output:
            Dict containing serializable component info lists.
        """

        return {
            "input_adapters": self._dump(self.input_adapters),
            "output_exporters": self._dump(self.output_exporters),
            "reachability_backends": self._dump(self.reachability_backends),
            "quality_backends": self._dump(self.quality_backends),
            "preprocessors": self._dump(self.preprocessors),
        }

    def _dump(self, components: list[object]) -> list[dict[str, object]]:
        """Serialize component info.

        Inputs:
            components: Instances exposing an `info()` method.
        Output:
            List of JSON-compatible metadata dicts.
        """

        return [component.info().model_dump() for component in components]


class ComponentNameResolver:
    """Resolve component names and aliases with helpful diagnostics."""

    def __init__(self, components: list[object], kind: str) -> None:
        """Build a case-insensitive index for registered components.

        Inputs:
            components: Component instances exposing `info()`.
            kind: Human-readable component kind for error messages.
        Output:
            Resolver that maps names/aliases to canonical component names.
        """

        self.kind = kind
        self._components = components
        self._index: dict[str, list[str]] = {}
        for component in components:
            info = component.info()
            for token in [info.name, *info.aliases]:
                self._index.setdefault(token.lower(), []).append(info.name)

    def resolve(self, value: str) -> str:
        """Resolve a user-provided name or alias to a canonical name.

        Inputs:
            value: Component name or alias from CLI/API-like callers.
        Output:
            Canonical `ComponentInfo.name`.
        """

        matches = sorted(set(self._index.get(value.lower(), [])))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous {self.kind} `{value}`; candidates: {', '.join(matches)}"
            )
        raise ValueError(
            f"unknown {self.kind} `{value}`; candidates: {', '.join(self.candidates())}"
        )

    def candidates(self) -> list[str]:
        """Return canonical names and aliases for completion/help text."""

        values: list[str] = []
        for component in self._components:
            info = component.info()
            values.extend([info.name, *info.aliases])
        return sorted(set(values), key=str.lower)
