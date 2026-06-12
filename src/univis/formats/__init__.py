"""Auto-discovery for built-in UniVis format subpackages.

New format packages should live under `univis.formats.<format_name>` and expose
`format_components() -> ComponentBundle` from their `__init__.py`. Packages can
also define `FORMAT_ORDER` to keep UI/CLI dropdown ordering stable.
"""

from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules

from univis.core.components import ComponentBundle

FORMAT_COMPONENTS_ENTRYPOINT = "format_components"
FORMAT_ORDER_ATTR = "FORMAT_ORDER"


def load_format_components() -> ComponentBundle:
    """Instantiate all built-in format package components.

    Inputs:
        None. The loader scans direct subpackages under `univis.formats`.
    Output:
        Combined component bundle from every package exposing
        `format_components()`.
    """

    components = ComponentBundle()
    for builder in _discover_format_builders():
        bundle = builder()
        components.input_adapters.extend(bundle.input_adapters)
        components.output_exporters.extend(bundle.output_exporters)
    return components


def _discover_format_builders() -> list[object]:
    """Return format component factories discovered from subpackages.

    Inputs:
        None. Discovery is constrained to direct packages in this directory.
    Output:
        Callable objects named `format_components`, ordered by package name for
        deterministic CLI/UI registry output.
    """

    builders: list[tuple[int, str, object]] = []
    package_prefix = f"{__name__}."
    for module_info in sorted(iter_modules(__path__), key=lambda item: item.name):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        module = import_module(f"{package_prefix}{module_info.name}")
        builder = getattr(module, FORMAT_COMPONENTS_ENTRYPOINT, None)
        if builder is None:
            continue
        order = int(getattr(module, FORMAT_ORDER_ATTR, 1000))
        builders.append((order, module_info.name, builder))
    return [builder for _, _, builder in sorted(builders, key=lambda item: (item[0], item[1]))]


__all__ = ["FORMAT_COMPONENTS_ENTRYPOINT", "FORMAT_ORDER_ATTR", "load_format_components"]
