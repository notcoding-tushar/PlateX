"""Validated Pydantic v2 data contracts for HOSNT12 inputs and outputs (SI units)."""
from __future__ import annotations

import math
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LayerProperty(BaseModel):
    """Single orthotropic ply definition in SI units (m, Pa, rad, 1/K).

    E1, E2, nu12, G12, G13, G23, alpha1, alpha2, beta1, beta2 enter the plane-stress
    (sigma_z = 0) laminate model. E3, nu23, nu13, alpha3, beta3 are accepted for 3D
    completeness but remain mathematically inert under TSDT plane-stress kinematics.
    """

    h_bottom: float
    h_top: float
    E1: float = Field(gt=0.0)
    E2: float = Field(gt=0.0)
    E3: float = Field(gt=0.0)
    nu12: float
    nu23: float
    nu13: float
    G12: float = Field(gt=0.0)
    G13: float = Field(gt=0.0)
    G23: float = Field(gt=0.0)
    theta_rad: float = 0.0
    alpha1: float = 0.0
    alpha2: float = 0.0
    alpha3: float = 0.0
    beta1: float = 0.0
    beta2: float = 0.0
    beta3: float = 0.0

    @model_validator(mode="after")
    def _validate_layer(self) -> "LayerProperty":
        vals = [
            self.h_bottom, self.h_top, self.E1, self.E2, self.E3,
            self.nu12, self.nu23, self.nu13, self.G12, self.G13, self.G23,
            self.theta_rad, self.alpha1, self.alpha2, self.alpha3,
            self.beta1, self.beta2, self.beta3,
        ]
        if not all(math.isfinite(v) for v in vals):
            raise ValueError("Layer properties must be finite.")
        if self.h_top <= self.h_bottom:
            raise ValueError("Layer h_top must exceed h_bottom.")
        if self.nu12 ** 2 >= self.E1 / self.E2:
            raise ValueError("Layer Poisson ratio nu12 violates nu12 * nu21 < 1.")
        return self


class ContactPatch(BaseModel):
    """Uniform downward contact patch load in SI units (m, N).

    Supports both rectangular footprints (IRC:6 bridge loads, legacy wheel patches)
    and circular footprints (IRC:37 dual wheels, IRC:58 axle groups).
    """

    x_m: float
    y_m: float
    force_N: float = Field(gt=0.0)
    shape: Literal["rectangle", "circle"] = "rectangle"
    length_m: Optional[float] = Field(default=None, gt=0.0)
    width_m: Optional[float] = Field(default=None, gt=0.0)
    radius_m: Optional[float] = Field(default=None, gt=0.0)
    label: str = ""

    @model_validator(mode="after")
    def _validate_geometry(self) -> "ContactPatch":
        if not (math.isfinite(self.x_m) and math.isfinite(self.y_m) and math.isfinite(self.force_N)):
            raise ValueError("Patch coordinates and force must be finite.")
        if self.shape == "rectangle":
            if self.length_m is None or self.width_m is None:
                raise ValueError("Rectangular patch requires length_m and width_m.")
            if self.radius_m is not None:
                raise ValueError("Rectangular patch cannot specify radius_m.")
        else:
            if self.radius_m is None:
                raise ValueError("Circular patch requires radius_m.")
            if self.length_m is not None or self.width_m is not None:
                raise ValueError("Circular patch cannot specify length_m or width_m.")
        return self

    @property
    def area_m2(self) -> float:
        if self.shape == "circle":
            return math.pi * (self.radius_m ** 2)
        return self.length_m * self.width_m

    @property
    def pressure_Pa(self) -> float:
        return self.force_N / self.area_m2


class VehicleLoad(BaseModel):
    """Discrete 1-based nodal vertical loads and/or contact patch loads."""

    nodal_loads: List[Tuple[int, float]] = Field(default_factory=list)
    patches: List[ContactPatch] = Field(default_factory=list)


class FoundationConfig(BaseModel):
    """Elastic foundation parameters: either dimensional (Kw, Kp, Kp_y) or dimensionless (K0, J0)."""

    Kw: float = Field(default=0.0, ge=0.0)
    Kp: float = Field(default=0.0, ge=0.0)
    Kp_y: Optional[float] = Field(default=None, ge=0.0)
    K0: Optional[float] = Field(default=None, ge=0.0)
    J0: Optional[float] = Field(default=None, ge=0.0)


class QueryPoint(BaseModel):
    """Arbitrary stress/deflection evaluation point in plate coordinates (m)."""

    label: str = "custom"
    x_m: float
    y_m: float
    z_m: float
    layer_side: Literal["auto", "above", "below"] = "auto"


class AnalysisConfig(BaseModel):
    """Complete, self-contained input configuration for a single HOSNT12 analysis."""

    a: float = Field(default=1.0, gt=0.0)
    b: float = Field(default=3.0, gt=0.0)
    h: float = Field(default=0.1, gt=0.0)
    m: int = Field(default=10, ge=1)
    n: int = Field(default=10, ge=1)

    material_mode: Literal["isotropic", "laminate"] = "isotropic"
    E: Optional[float] = None
    nu: Optional[float] = None
    alpha: float = 0.0
    beta: float = 0.0
    layers: Optional[List[LayerProperty]] = None

    choicebc: int = Field(default=1, ge=1, le=6)
    load_case: Literal["sinusoidal", "uniform"] = "sinusoidal"
    q0: float = Field(default=100.0, ge=0.0)
    nonlocal_parameter: float = Field(default=0.0, ge=0.0)

    t_coeffs: Optional[Tuple[float, float, float]] = None
    c_coeffs: Optional[Tuple[float, float, float]] = None
    thermal_distribution: Literal["sinusoidal", "uniform"] = "sinusoidal"

    foundation: FoundationConfig = Field(default_factory=FoundationConfig)
    vehicle_load: Optional[VehicleLoad] = None
    query_points: List[QueryPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_config(self) -> "AnalysisConfig":
        if self.material_mode == "isotropic":
            if self.E is None or self.nu is None:
                raise ValueError("Isotropic material requires E and nu; no default material is assumed.")
            if not (math.isfinite(self.E) and self.E > 0.0):
                raise ValueError("Young's modulus E must be positive and finite.")
            if not (math.isfinite(self.nu) and -0.99 < self.nu < 0.4999):
                raise ValueError("Poisson ratio must satisfy -0.99 < nu < 0.4999.")
        for name, coeffs in (("t_coeffs", self.t_coeffs), ("c_coeffs", self.c_coeffs)):
            if coeffs is not None and not all(math.isfinite(v) for v in coeffs):
                raise ValueError(f"{name} must contain three finite numbers.")
        return self


class PointResult(BaseModel):
    """Evaluated response at a single QueryPoint."""

    label: str
    x_m: float
    y_m: float
    z_m: float
    w_m: float
    sigma_x_pa: float
    sigma_y_pa: float
    tau_xy_pa: float
    tau_xz_pa: float
    tau_yz_pa: float


class StiffnessDiagnostics(BaseModel):
    global_shape: Tuple[int, int]
    reduced_shape: Tuple[int, int]
    nnz: int
    density_pct: float
    diag_min: float
    diag_max: float
    frobenius_norm: float
    max_asymmetry: float
    Db_norm: float
    Ds_norm: float
    Db_top_left_4x4: List[List[float]]
    Ds_top_left_2x2: List[List[float]]


class AnalysisResult(BaseModel):
    """Structured output of a HOSNT12 analysis (JSON-serializable for FastAPI)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    mesh: str
    m: int
    n: int
    nodes: int
    elements: int
    ndof: int
    free_dofs: int
    fixed_dofs: int

    w_center_m: float
    max_abs_deflection_m: float
    min_deflection_m: float
    max_deflection_m: float
    sigma_x_pa: float
    tau_xy_pa: float
    tau_xz_pa: float

    w_bar: Optional[float] = None
    sigma_x_bar: Optional[float] = None
    tau_xy_bar: Optional[float] = None
    tau_xz_bar: Optional[float] = None

    flexural_rigidity_D_Nm: float
    flexural_rigidity_Dy_Nm: float
    stress_sample_locations: Dict[str, Dict[str, float]]
    point_results: List[PointResult] = Field(default_factory=list)

    stiffness_info: StiffnessDiagnostics
    time_s: float
    solver_warnings: List[str] = Field(default_factory=list)
    modeling_notes: List[str] = Field(default_factory=list)
