"""Validated Pydantic v2 data contracts for HOSNT12 inputs and outputs (SI units)."""
from __future__ import annotations

import math
from itertools import pairwise
from typing import Literal

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
    def _validate_layer(self) -> LayerProperty:
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

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    x_m: float
    y_m: float
    force_N: float = Field(gt=0.0)
    shape: Literal["rectangle", "circle"] = "rectangle"
    length_m: float | None = Field(default=None, gt=0.0)
    width_m: float | None = Field(default=None, gt=0.0)
    radius_m: float | None = Field(default=None, gt=0.0)
    label: str = ""

    @model_validator(mode="after")
    def _validate_geometry(self) -> ContactPatch:
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

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    nodal_loads: list[tuple[int, float]] = Field(default_factory=list)
    patches: list[ContactPatch] = Field(default_factory=list)


class FoundationConfig(BaseModel):
    """Elastic foundation parameters: either dimensional (Kw, Kp, Kp_y) or dimensionless (K0, J0)."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    Kw: float = Field(default=0.0, ge=0.0)
    Kp: float = Field(default=0.0, ge=0.0)
    Kp_y: float | None = Field(default=None, ge=0.0)
    K0: float | None = Field(default=None, ge=0.0)
    J0: float | None = Field(default=None, ge=0.0)


class QueryPoint(BaseModel):
    """Arbitrary stress/deflection evaluation point in plate coordinates (m)."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    label: str = "custom"
    x_m: float
    y_m: float
    z_m: float
    layer_side: Literal["auto", "above", "below"] = "auto"


class AnalysisConfig(BaseModel):
    """Complete, self-contained input configuration for a single HOSNT12 analysis."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    a: float = Field(default=1.0, gt=0.0)
    b: float = Field(default=3.0, gt=0.0)
    h: float = Field(default=0.1, gt=0.0)
    m: int = Field(default=10, ge=1)
    n: int = Field(default=10, ge=1)

    material_mode: Literal["isotropic", "laminate"] = "isotropic"
    E: float | None = None
    nu: float | None = None
    alpha: float = 0.0
    beta: float = 0.0
    layers: list[LayerProperty] | None = None

    choicebc: int = Field(default=1, ge=1, le=6)
    load_case: Literal["sinusoidal", "uniform"] = "sinusoidal"
    q0: float = Field(default=100.0, ge=0.0)
    nonlocal_parameter: float = Field(default=0.0, ge=0.0)

    t_coeffs: tuple[float, float, float] | None = None
    c_coeffs: tuple[float, float, float] | None = None
    thermal_distribution: Literal["sinusoidal", "uniform"] = "sinusoidal"

    foundation: FoundationConfig = Field(default_factory=FoundationConfig)
    vehicle_load: VehicleLoad | None = None
    query_points: list[QueryPoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_config(self) -> AnalysisConfig:
        if self.material_mode == "isotropic":
            if self.E is None or self.nu is None:
                raise ValueError("Isotropic material requires E and nu; no default material is assumed.")
            if not (math.isfinite(self.E) and self.E > 0.0):
                raise ValueError("Young's modulus E must be positive and finite.")
            if not (math.isfinite(self.nu) and -0.99 < self.nu < 0.4999):
                raise ValueError("Poisson ratio must satisfy -0.99 < nu < 0.4999.")
        if self.material_mode == "laminate" and self.layers:
            ordered = sorted(self.layers, key=lambda layer: layer.h_bottom)
            tol = max(1e-12, self.h * 1e-9)
            if abs(ordered[0].h_bottom + self.h / 2) > tol or abs(ordered[-1].h_top - self.h / 2) > tol:
                raise ValueError("Layers must span the full plate thickness from -h/2 to +h/2.")
            if any(abs(a.h_top - b.h_bottom) > tol for a, b in pairwise(ordered)):
                raise ValueError("Layers must be contiguous without gaps or overlaps.")
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
    global_shape: tuple[int, int]
    reduced_shape: tuple[int, int]
    nnz: int
    density_pct: float
    diag_min: float
    diag_max: float
    frobenius_norm: float
    max_asymmetry: float
    Db_norm: float
    Ds_norm: float
    Db_top_left_4x4: list[list[float]]
    Ds_top_left_2x2: list[list[float]]


class DeflectionField(BaseModel):
    coordinates: list[tuple[float, float]]
    elements: list[list[int]]
    w_m: list[float]


class AnalysisResult(BaseModel):
    """Structured output of a HOSNT12 analysis (JSON-serializable for FastAPI)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: DeflectionField | None = None
    engine: Literal["hosnt12_plate_q8"] = "hosnt12_plate_q8"
    sources: list[Citation] = Field(default_factory=list)
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

    w_bar: float | None = None
    sigma_x_bar: float | None = None
    tau_xy_bar: float | None = None
    tau_xz_bar: float | None = None

    flexural_rigidity_D_Nm: float
    flexural_rigidity_Dy_Nm: float
    stress_sample_locations: dict[str, dict[str, float]]
    point_results: list[PointResult] = Field(default_factory=list)

    stiffness_info: StiffnessDiagnostics
    time_s: float
    solver_warnings: list[str] = Field(default_factory=list)
    modeling_notes: list[str] = Field(default_factory=list)


class SweepRequest(BaseModel):
    base_config: AnalysisConfig
    load_cases: list[AnalysisConfig | VehicleLoad] = Field(min_length=1)


class BenchmarkResult(BaseModel):
    computed: dict[str, float]
    reference: dict[str, float]


class PaperValidationRequest(BaseModel):
    # The original Table 2 deflection self-test uses a relative tolerance of 0.001.
    tolerance_pct: float = Field(default=0.1, ge=0, allow_inf_nan=False)


class PaperComparison(BaseModel):
    case: str
    table: int
    K0: int
    J0: int
    parameter: str
    reference: float
    computed: float
    absolute_error: float
    error_pct: float
    passed: bool


class PaperValidationReport(BaseModel):
    tolerance_pct: float
    comparisons: list[PaperComparison]
    passed_cases: list[str]
    failed_cases: list[str]
    mean_error_pct: float
    worst: PaperComparison


class H2MeshResult(BaseModel):
    mesh: int
    w_bar: float
    sigma_x_bar: float


class H2Refinement(BaseModel):
    meshes: list[H2MeshResult]
    stress_reference: float
    observed_order: float | None
    stress_limit_estimate: float | None


class IRCPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    case: str
    a: float = Field(gt=0)
    b: float = Field(gt=0)
    x_m: float
    y_m: float
    group_load_kN: float = Field(default=80, gt=0)
    wheel_offsets_m: list[float] = Field(default_factory=list)
    spacing_m: float = Field(default=1.3, gt=0)
    tyre_pattern: Literal["L", "M", "N"] = "L"
    aa_wheel_offsets_y_mm: list[float] | None = None
    prime_mover_contacts: list[ContactPatch] | None = None
    sv_eccentricity_mm: float = 0
    flexural_strength_MPa: float | None = Field(default=None, gt=0)
    water_cm: float | None = Field(default=None, gt=0)


class Citation(BaseModel):
    code: str
    location: str
    printed_pages: list[int]
    pdf_pages: list[int]
    filename: str


class IRCOption(BaseModel):
    case: str
    label: str
    mode: Literal["flexible", "rigid", "bridge"]


class IRCPreview(BaseModel):
    vehicle_load: VehicleLoad
    inside_plate: bool
    sources: list[Citation]
    notes: list[str]


class IRCCheck(BaseModel):
    name: str
    status: Literal["pass", "fail", "needs_input"]
    message: str
    source: Citation


class IRCRigidRequest(BaseModel):
    base_config: AnalysisConfig
    cbr_percent: float
    cbr_code: Literal["IRC:58-2015", "IRC:15-2017"] = "IRC:58-2015"
    support: Literal["raw", "effective"] = "raw"
    subbase: Literal["DLC", "untreated", "cement_treated"] = "DLC"
    subbase_thickness_mm: float | None = None
    explicit_dlc: bool = False
    interpolate: bool = False
    raw: bool = False
    temperature_zone: str | None = None
    temperature_period: Literal["day", "night"] = "day"


class IRCFoundationLookup(BaseModel):
    cbr_percent: float
    cbr_code: Literal["IRC:58-2015", "IRC:15-2017"] = "IRC:58-2015"
    subbase: Literal["DLC", "untreated", "cement_treated"] = "DLC"
    subbase_thickness_mm: float
    interpolate: bool = False
    raw: bool = False


class IRCFlexibleRequest(BaseModel):
    base_config: AnalysisConfig
    category: str
    cbr: float
    traffic_msa: float
    bituminous_E_MPa: float
    subgrade_thickness_m: float = Field(gt=0)
    x_m: float
    y_m: float
    ctb_fatigue: bool = False


class ElasticLayer(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    name: str
    thickness_m: float | None = Field(gt=0)
    E_Pa: float = Field(gt=0)
    nu: float = Field(gt=-1, lt=0.5)


class DepthPoint(BaseModel):
    """Depth positive down from the surface. The default interface limit is below."""

    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    label: str = ""
    x_m: float
    y_m: float
    depth_m: float = Field(ge=0)
    side: Literal["above", "below"] = "below"


class ElasticResponse(DepthPoint):
    layer: str
    w_m: float
    sigma_z_Pa: float
    sigma_r_Pa: float
    sigma_theta_Pa: float
    tau_rz_Pa: float
    eps_z: float
    eps_r: float
    eps_theta: float
    max_horizontal_strain: float
    max_horizontal_stress_Pa: float


class CatalogueOptions(BaseModel):
    categories: list[str]
    cbr: list[float]
    traffic_msa: list[float]


class LayeredElasticRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    category: Literal["a", "b", "c", "d", "e", "f"]
    cbr: float = Field(gt=0)
    traffic_msa: float = Field(gt=0)
    bituminous_E_MPa: float = Field(gt=0)
    wheels: Literal["single", "dual"] = "dual"
    ctb_fatigue: bool = False
    wheel_force_N: float | None = Field(default=None, gt=0)
    pressure_Pa: float | None = Field(default=None, gt=0)
    spacing_m: float | None = Field(default=None, gt=0)
    points: list[DepthPoint] = Field(default_factory=list, max_length=64)


class LayeredElasticResult(BaseModel):
    engine: Literal["layered_elastic_irc37"] = "layered_elastic_irc37"
    profile: dict
    layers: list[ElasticLayer]
    patches: list[ContactPatch]
    pressure_Pa: float
    critical: list[ElasticResponse]
    points: list[ElasticResponse]
    checks: list[IRCCheck]
    sources: list[Citation]
    modeling_notes: list[str]


class IRCPrepared(BaseModel):
    config: AnalysisConfig
    sources: list[Citation]
    modeling_notes: list[str]
    details: dict = Field(default_factory=dict)


class IRCClimateZone(BaseModel):
    zone: str
    region: str


class IRCClimateOptions(BaseModel):
    zones: list[IRCClimateZone]
    source: Citation
    notes: list[str]


class IRCClimateRequest(BaseModel):
    zone: str
    thickness_m: float = Field(gt=0)
    period: Literal["day", "night"] = "day"
    interpolate: bool = False


class IRCClimateResult(BaseModel):
    delta_T_K: float
    source: Citation
    notes: list[str]


class IRCComplianceRequest(BaseModel):
    kind: Literal["pqc", "dlc", "wbm", "dowel", "grading", "tie_bars"]
    arguments: dict


class IRCComplianceResult(BaseModel):
    checks: list[IRCCheck] = Field(default_factory=list)
    options: list[dict] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)


class IRCSweepRequest(BaseModel):
    base_config: AnalysisConfig
    placements: list[IRCPlacement] = Field(min_length=1)

