"""HOSNT12 Finite Element Analysis Engine."""

from hosnt12.constants import BOUNDARY_CONDITIONS, DOF, PRESET_LAMINATE_PROPERTIES
from hosnt12.schemas import (
    AnalysisConfig,
    AnalysisResult,
    ContactPatch,
    FoundationConfig,
    LayerProperty,
    QueryPoint,
    StiffnessDiagnostics,
    VehicleLoad,
)

from .solver import solve_hosnt12, solve_hosnt12_legacy, solve_sweep

__all__ = [
    "BOUNDARY_CONDITIONS",
    "DOF",
    "PRESET_LAMINATE_PROPERTIES",
    "AnalysisConfig",
    "AnalysisResult",
    "ContactPatch",
    "FoundationConfig",
    "LayerProperty",
    "QueryPoint",
    "StiffnessDiagnostics",
    "VehicleLoad",
    "solve_hosnt12",
    "solve_hosnt12_legacy",
    "solve_sweep",
]
