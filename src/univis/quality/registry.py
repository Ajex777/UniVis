"""Auto-discovery for pluggable quality feature packages."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from univis.quality.base import QualityComponentBundle

QUALITY_COMPONENTS_ENTRYPOINT = "quality_components"
QUALITY_ORDER_ATTR = "QUALITY_ORDER"


def load_quality_components() -> QualityComponentBundle:
    """Load quality components from direct `univis.quality` subpackages.

    Inputs:
        None. Discovery scans importable direct child packages.
    Output:
        Combined bundle containing backend instances and API route builders.
    """

    bundle = QualityComponentBundle()
    for _, builder in _discover_quality_builders():
        contributed = builder()
        bundle.backends.extend(contributed.backends)
        bundle.route_builders.extend(contributed.route_builders)
    return bundle


def _discover_quality_builders() -> list[tuple[str, Callable[[], QualityComponentBundle]]]:
    """Return component builders sorted by package-defined order."""

    import univis.quality as quality_package

    discovered: list[tuple[int, str, Callable[[], QualityComponentBundle]]] = []
    for module_info in pkgutil.iter_modules(quality_package.__path__):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{quality_package.__name__}.{module_info.name}")
        builder = getattr(module, QUALITY_COMPONENTS_ENTRYPOINT, None)
        if builder is None:
            continue
        order = int(getattr(module, QUALITY_ORDER_ATTR, 1000))
        discovered.append((order, module_info.name, builder))
    return [(name, builder) for _, name, builder in sorted(discovered)]
