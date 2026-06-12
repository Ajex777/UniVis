"""Quality component bundle definitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import APIRouter

from univis.quality.base.backend import QualityBackend

if TYPE_CHECKING:
    from univis.quality.service import QualityService


QualityRouteBuilder = Callable[["QualityService"], APIRouter]


@dataclass
class QualityComponentBundle:
    """Backends and API routes contributed by one quality subpackage.

    Inputs:
        backends: Instantiated quality backend objects.
        route_builders: Functions that receive `QualityService` and return a router.
    Output:
        Bundle consumed by the app-level registry and API router.
    """

    backends: list[QualityBackend] = field(default_factory=list)
    route_builders: list[QualityRouteBuilder] = field(default_factory=list)
