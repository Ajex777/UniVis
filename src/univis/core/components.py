"""Shared component metadata and registry helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


class ComponentInfo(BaseModel):
    """Serializable metadata for a pluggable UniVis component.

    Inputs:
        name: Stable class-like identifier.
        label: Human-friendly display label.
        description: Short explanation for UI dropdowns and diagnostics.
    Output:
        JSON-ready metadata shared by adapters, exporters, and backends.
    """

    name: str
    label: str
    description: str = ""


@dataclass
class ComponentRegistry:
    """In-memory registry for pluggable UniVis components.

    Inputs:
        input_adapters: Registered raw/HDF5 episode adapters.
        output_exporters: Registered output format exporters.
        reachability_backends: Registered reachability implementations.
    Output:
        Registry object that can produce API-safe dropdown metadata.
    """

    input_adapters: list[object] = field(default_factory=list)
    output_exporters: list[object] = field(default_factory=list)
    reachability_backends: list[object] = field(default_factory=list)

    def api_payload(self) -> dict[str, list[dict[str, str]]]:
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
        }

    def _dump(self, components: list[object]) -> list[dict[str, str]]:
        """Serialize component info.

        Inputs:
            components: Instances exposing an `info()` method.
        Output:
            List of JSON-compatible metadata dicts.
        """

        return [component.info().model_dump() for component in components]
