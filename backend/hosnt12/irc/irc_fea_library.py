"""IRC input data, checks and load geometry for an FEA solver.

Sources: the six PDFs supplied with this project ONLY. IRC:37 is 2018 in
its title and running headers despite the uploaded filename containing 2019.
Python >= 3.10; standard library only; no file access or output on import.

Native units: mm, N, MPa=N/mm², k in MPa/m, temperature differences in °C.
FEA export: m, N, Pa, foundation stiffness N/m³. Conversion is explicit.
This module supplies inputs, not a finite element or layered elastic solver.
See IRC_FEA_LIBRARY_GUIDE.md for scope, references and integration examples.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import ceil, isfinite, pi, sqrt
from typing import Any, Iterable, Mapping
import copy

__version__ = "1.0.0"

SOURCE_FILES = {
    "IRC:58-2015": ("Rigid pavement irc 58 2015.pdf", 10),
    "IRC:37-2018": ("irc 37 2019.pdf", 10),
    "IRC:SP:49-2014": ("Supporting Codes.pdf", 8),
    "IRC:15-2017": ("Rigid pavement construction IRC 15 2017.pdf", 2),
    "IRC:19-2005": ("WBM layer IRC 19 2005.pdf", 8),
    "IRC:6-2017": ("Bridge loading IRC 6 2017.pdf", 7),
}


@dataclass(frozen=True)
class Source:
    code: str
    location: str
    printed_pages: tuple[int, ...]

    @property
    def pdf_pages(self) -> tuple[int, ...]:
        return tuple(p + SOURCE_FILES[self.code][1] for p in self.printed_pages)

    @property
    def filename(self) -> str:
        return SOURCE_FILES[self.code][0]


@dataclass(frozen=True)
class Provision:
    data: Any
    units: str
    source: Source
    kind: str
    notes: str = ""


PROVISIONS: dict[str, Provision] = {}


def _add(key: str, code: str, location: str, pages: tuple[int, ...],
         data: Any, units: str = "see field names", kind: str = "data",
         notes: str = "") -> None:
    if key in PROVISIONS:
        raise RuntimeError(f"Duplicate provision: {key}")
    PROVISIONS[key] = Provision(data, units, Source(code, location, pages), kind, notes)


def get(key: str) -> Provision:
    """Return a defensive copy, including units and provenance."""
    return copy.deepcopy(PROVISIONS[key])


def find(text: str) -> dict[str, Provision]:
    """Search keys, clause references, notes and data; no external lookup."""
    q = text.casefold()
    return {k: get(k) for k, v in PROVISIONS.items()
            if q in (k + repr(v)).casefold()}


def _number(value: float, name: str, *, zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    x = float(value)
    if not isfinite(x) or x < 0 or (x == 0 and not zero):
        raise ValueError(f"{name} must be finite and {'non-negative' if zero else 'positive'}")
    return x


def _ratio(value: float, name: str) -> float:
    x = _number(value, name, zero=True)
    if x > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def _lookup(table: Mapping[float, float], x: float, *, interpolate: bool = False) -> float:
    """Exact by default; opt-in straight-line interpolation; never extrapolate.

    Interpolation is a software numerical choice, not an additional IRC equation.
    """
    x = _number(x, "lookup argument", zero=True)
    if x in table:
        return table[x]
    keys = sorted(table)
    if not interpolate or not keys[0] < x < keys[-1]:
        raise ValueError(f"Use tabulated values {keys}; interpolation must be explicit")
    for a, b in zip(keys, keys[1:]):
        if a < x < b:
            return table[a] + (table[b] - table[a]) * (x - a) / (b - a)
    raise ValueError("Unsupported lookup")


# ---------------------- IRC:58-2015 ----------------------
R58 = "IRC:58-2015"
_add("58.layers", R58, "4.1; Fig. 1", (3,), {
    "a_top_to_bottom": ("PQC", "debonding sheet", "DLC", "drainage", "GSB filter", "subgrade"),
    "b_top_to_bottom": ("PQC", "BC debonding", "cement-treated aggregates", "drainage", "GSB filter", "subgrade"),
    "sheet_thickness_mm": 0.125,
    "BC_debonding_thickness_mm": (30, 40),
    "subgrade_thickness_mm": 500,
    "subgrade_min_CBR_percent": 8,
    "geocomposite_replacement_min_CBR_percent": 8,
}, notes="Fig.1(a) labels the 125 micron sheet PVC; caption calls it polythene. "
         "Fig.1(b) diagram labels BC2; caption says BC1. Preserve the debonding function; "
         "the figure alone does not resolve either naming discrepancy.")
_add("58.axles", R58, "5.2", (4,), {
    "historical_axle_limits_kN": {"single": 100, "tandem": 186, "tridem": 235},
    "historical_axle_limits_tonnes": {"single": 10.2, "tandem": 19.0, "tridem": 24.0},
    "spectrum_interval_kN": {"single": 10, "tandem": 20, "tridem": 30},
    "separate_single_axle_when_spacing_exceeds_mm": 2400,
    "common_tyre_pressure_MPa": (0.7, 1.0), "design_tyre_pressure_MPa": 0.8,
}, notes="Loads are historical values stated in this edition, not a maximum analysis load. "
         "Actual axle spectra may include overloaded vehicles; group load is not each-axle load.")
_add("58.spacing", R58, "5.3; 6.1.2", (4, 15), {
    "typical_transverse_joint_spacing_mm": 4500,
    "typical_truck_wheelbase_mm": (3600, "over 5000"),
    "tandem_tridem_individual_axle_spacing_mm": (1300, 1400),
    "analysis_axle_spacing_mm": 1300,
    "top_down_eligible": "consecutive axle spacing < actual transverse joint spacing",
})
_TEMP = {"I": (12.5,13.1,14.3,15.8), "II": (12.5,13.1,14.3,15.8),
         "III": (15.6,16.4,16.6,16.8), "IV": (17.3,19.0,20.3,21.0),
         "V": (15.0,16.4,17.6,18.1), "VI": (14.6,15.8,16.2,17.0),
         "VII": (15.5,17.0,19.0,19.2)}
_add("58.temperature", R58, "5.6.1; Table 1", (6, 7), {
    "thickness_columns_mm": (150, 200, 250, "300-400"),
    "day_delta_T_C": _TEMP,
    "regions": {
        "I": "Hilly Uttaranchal, West Bengal, Jammu & Kashmir, Himachal Pradesh, Arunachal Pradesh",
        "II": "Punjab, UP, Uttaranchal, Gujarat, Rajasthan, Haryana, North MP; excluding hills",
        "III": "Bihar, Jharkhand, West Bengal, Assam, Eastern Orissa; excluding hills/coast",
        "IV": "Maharashtra, Karnataka, South MP, Chattisgarh, Andhra Pradesh, Western Orissa, North Tamil Nadu; excluding hills/coast",
        "V": "Kerala, South Tamil Nadu; excluding hills/coast",
        "VI": "Coast bounded by hills", "VII": "Coast unbounded by hills"},
    "night_to_day_magnitude_approx": 0.5,
    "day_profile": "nonlinear", "night_profile": "nearly linear",
}, notes="Use realistic site data when available. Table is a fallback maximum differential, "
         "not absolute temperature, not a uniform temperature rise. Delta T = top minus bottom.")
_add("58.winkler", R58, "5.7.3.1", (8, 9), {
    "model": "Winkler", "plate_diameter_mm": 750, "test_deflection_mm": 1.25,
    "definition": "k = applied pressure / foundation deflection",
    "test_frequency_per_km_per_lane": 1,
}, units="k: MPa/m", notes="Independent foundation springs. These provisions give no Pasternak shear parameter.")
_CBR_K58 = dict(zip((2,3,4,5,7,10,15,20,50,100),(21,28,35,42,48,55,62,69,140,220)))
_add("58.cbr_k", R58, "5.7.3.4; Table 2", (9,), _CBR_K58,
     "key: soaked CBR percent; value: MPa/m", notes="Homogeneous soil subgrade only; not effective k over DLC.")
_add("58.dlc", R58, "5.7.4.1", (11,), {
    "min_thickness_major_highway_mm": 150, "mean_7d_compressive_strength_MPa": 7,
    "bonded_PQC_min_7d_strength_MPa": 10, "bonded_surface_roughening_hours": (3,6),
}, kind="constraint")
_add("58.pqc_strength", R58, "5.8.2", (12, 13), {
    "min_28d_flexural_strength_MPa": 4.5, "90d_to_28d_strength_factor": 1.10,
}, notes="90-day strength may be used for design under the stated strength-gain rationale.")
_add("58.pqc_elastic", R58, "5.8.4.1", (13,), {"E_MPa":30000, "nu":0.15},
     notes="Stress-analysis values for concrete of 28-day flexural strength 4.5 MPa; "
           "experimentally measured mix properties are preferred. Not a universal material law.")
_add("58.pqc_alpha", R58, "5.8.5", (13,), 10e-6, "1/degree C")
_add("58.positions", R58, "6.1.1-6.1.3; Figs. 3-6", (14,15,16), {
    "interior_mid_panel": "load at longitudinal mid-panel in positive differential; inspect bottom tension",
    "edge_bottom_up": "outer tyre imprint tangent to longitudinal edge; inspect bottom flexural stress",
    "near_transverse_joint_top_down": "successive axles close to transverse joints with negative differential; inspect top tension and loss of support",
}, kind="analysis_requirement", notes="Clauses do not prescribe a universal near-joint offset. "
         "Do not replace pavement edge, joint or curling contact conditions by an arbitrary plate support label.")


def rigid_cbr_to_k(cbr_percent: float, *, interpolate: bool = False,
                   code: str = R58) -> float:
    """Table 2 (58) or Table 5 (15), in MPa/m; no extrapolation."""
    key = {R58:"58.cbr_k", "IRC:15-2017":"15.cbr_k"}[code]
    return _lookup(PROVISIONS[key].data, cbr_percent, interpolate=interpolate)


def rigid_temperature_delta(zone: str, slab_thickness_mm: float, *,
                            period: str = "day", interpolate: bool = False) -> float:
    """58 Table 1. Night is the clause's approximate -0.5 x day assumption.

    No permanent curl or zero-stress correction is added: those are separate
    quantities and are outside the requested 5.6.1 extraction.
    """
    h = _number(slab_thickness_mm, "slab_thickness_mm")
    zone = zone.upper()
    if zone not in _TEMP or period not in ("day", "night"):
        raise ValueError("Use zone I-VII and period day/night")
    v = _TEMP[zone]
    day = v[-1] if 300 <= h <= 400 else _lookup(dict(zip((150,200,250,300),v)), h, interpolate=interpolate)
    return day if period == "day" else -0.5 * day


def rigid_top_down_eligible(axle_spacing_mm: float, joint_spacing_mm: float) -> bool:
    return _number(axle_spacing_mm,"axle spacing") < _number(joint_spacing_mm,"joint spacing")


def winkler_k_from_plate(pressure_MPa: float, deflection_mm: float = 1.25) -> float:
    """58 5.7.3.1 definition; result MPa/m. A different deflection is not the standard test."""
    return _number(pressure_MPa,"pressure") / (_number(deflection_mm,"deflection") / 1000)


def k_to_SI(k_MPa_per_m: float) -> float:
    """MPa/m -> N/m³; numerical unit conversion only."""
    return _number(k_MPa_per_m,"k") * 1e6


# ---------------------- IRC:37-2018 ----------------------
F37 = "IRC:37-2018"
FLEXIBLE_CATEGORIES = {
    "a": ("bituminous", "unbound_base", "GSB", "subgrade"),
    "b": ("bituminous", "granular_crack_relief", "CTB", "CTSB", "subgrade"),
    "c": ("bituminous", "SAMI", "CTB", "CTSB", "subgrade"),
    "d": ("bituminous", "stabilised_RAP", "CTSB", "subgrade"),
    "e": ("bituminous", "granular_crack_relief", "CTB", "GSB", "subgrade"),
    "f": ("bituminous", "unbound_base", "CTSB", "subgrade"),
}
_add("37.categories", F37, "12.2", (35,), FLEXIBLE_CATEGORIES,
     notes="Order is top to bottom; bituminous may comprise surface and DBM/BM courses.")
_add("37.catalogue_scope", F37, "12.1-12.3", (34,35), {
    "CBR_percent": (5,6,7,8,9,10,12,15), "traffic_msa": (5,10,20,30,40,50),
    "purpose": "illustrative trial profiles and initial cost estimation; site-specific design required",
    "bituminous_moduli_MPa": {"below_20_msa":2000,"20_to_50_msa":3000},
    "important_roads_reliability_percent": 90,
    "catalogue_reliability_text": "80% up to 20 msa; 90% higher traffic",
    "CTB_check": "Eq.3.5 only in catalogue; project axle spectrum CFD also required",
    "RF": {"below_10_msa":2,"10_msa_and_above":1},
    "mix_parameters_cases_b_c_e": {"Va_percent":3.5,"Vbe_percent":11.5,"C":2.35},
    "mix_parameters_cases_a_d_f": {
        "lower_traffic_text_5_10_20": {"Va_percent":4.5,"Vbe_percent":10.5,"C":1.12},
        "higher_traffic_text_20_30_40_50": {"Va_percent":3.5,"Vbe_percent":11.5,"C":2.35}},
}, notes="Section 12.3 has overlapping 20 msa mix-parameter lists and wording at the "
         "20 msa reliability boundary. Raw statements retained; no automatic selection of those assumptions.")
_add("37.binder_options", F37, "9.1; Table 9.1", (27,28,29), {
    "over_50_msa": {"surface":(("SMA","modified or VG40"),("GGRB","crumb rubber modified"),("BC","modified")),"base":("DBM","VG40")},
    "20_to_50_msa": {"surface":(("SMA","modified or VG40"),("GGRB","crumb rubber modified"),("BC","modified or VG40")),"base":("DBM","VG40")},
    "below_20_msa": {"surface":("BC","SDBC","PMC","MSS","SD","SMA","GGRB","modified BC"),"unmodified_binder":("VG30","VG40"),"base":("DBM or BM","VG30 or VG40")},
    "NH_expressway_below_20_msa": {"surface_binder":"VG40 or modified", "DBM_binder":"VG40"},
    "VG40_min_viscosity_Poise_at_60C": 3600,
    "snowbound_option": "VG10; especially maximum pavement temperature below 30 C",
    "total_bituminous_under_40mm_option": "BC/SDBC with VG30",
    "high_rainfall_junction_option": "mastic asphalt",
    "nonstructural_thin_surfacings": ("PMC/PC","MSS","SD"),
}, kind="selection_rule")
_BITUMINOUS = {
    "BC_DBM_VG10": (2300,2000,1450,1000,800),
    "BC_DBM_VG30": (3500,3000,2500,2000,1250),
    "BC_DBM_VG40": (6000,5000,4000,3000,2000),
    "BC_MODIFIED": (5700,3800,2400,1600,1300),
}
_add("37.bituminous_modulus", F37, "9.2; Table 9.2", (29,30,31), {
    "temperatures_C": (20,25,30,35,40), "maxima_MPa": _BITUMINOUS,
    "only_at_35C_MPa": {"BM_VG10":500,"BM_VG30":700,"STABILISED_RAP":800},
    "nu":0.35, "normal_test_C":35,"snowbound_test_C":20,
    "load_pulse_s":0.1,"rest_s":0.9,"DBM_specimen_diameter_mm":150,
    "design_selection": "minimum of measured mix modulus and applicable tabulated maximum",
    "combined_layer": "use bottom DBM modulus for all structural bituminous courses",
}, notes="BC_MODIFIED row is reference data, not the combined-layer design default. "
         "Modified surface stiffness is assigned the DBM value in structural analysis.")
_add("37.materials", F37, "Table 11.1", (34,), {
    "BITUMINOUS_VG40": {"E_MPa":3000,"nu":0.35,"selection":"cap; use tested value if lower"},
    "BITUMINOUS_VG30": {"E_MPa":2000,"nu":0.35,"selection":"cap; use tested value if lower"},
    "CTB": {"E_MPa":5000,"nu":0.25},
    "STABILISED_RAP": {"E_MPa":800,"nu":0.35},
    "GRANULAR_CRACK_RELIEF": {"E_MPa":450,"nu":0.35},
    "CTSB": {"E_MPa":600,"nu":0.25},
    "UNBOUND_GRANULAR": {"E_MPa":None,"formula":"Eq.7.1","nu":0.35},
    "GRAVEL_ON_CTSB": {"E_MPa":300,"nu":0.35},
    "CRUSHED_ROCK_ON_CTSB": {"E_MPa":350,"nu":0.35},
    "SUBGRADE": {"E_MPa":None,"formula":"Eqs.6.1-6.2","nu":0.35},
})
_add("37.subgrade_test", F37, "6.2", (19,), {
    "default_soaking_days":4,"min_density_percent_modified_Proctor_MDD":97,
    "moulding_moisture":"OMC at placement density; static compaction",
    "design_moisture":"most critical expected site condition",
    "low_rainfall_threshold_mm_per_year":1000,
    "low_rainfall_exception":"seasonal field moisture data may justify different moulding condition",
    "min_specimens_per_soil_type":3,
    "design_CBR_percentile": {"important_roads":90,"other_under_20_msa":80,"other_20_msa_or_more":90},
}, kind="constraint", notes="Percentile wording is retained from the code; no statistical rank convention is invented.")
_add("37.subgrade_MR", F37, "6.3; Eqs. 6.1-6.2", (19,),
     {"CBR_le_5":"MR=10*CBR", "CBR_gt_5":"MR=17.6*CBR**0.64", "nu":0.35},
     "CBR in percent; MR in MPa", "formula")
_add("37.effective_subgrade", F37, "6.4.1-6.4.2; Eq.6.3", (20,), {
    "wheel_load_N":40000,"pressure_MPa":0.56,"approx_contact_radius_mm":150.8,
    "nu":0.35,"select_subgrade_thickness_mm":500,
    "model":"one or two finite subgrade layers over semi-infinite embankment",
    "formula":"MR=2*(1-nu**2)*p*a/delta", "max_design_MR_MPa":100,
}, kind="formula", notes="delta must come from the specified layered elastic analysis. "
         "It is not an average of CBR values and not deflection of the PQC slab.")
_add("37.gsb", F37, "7.2.1-7.2.3; Eq.7.1", (21,22,23), {
    "min_drainage_mm":100,"min_filter_mm":100,"min_combined_drainage_filter_mm":150,
    "single_combined_layer_if_total_not_over_mm":200,
    "preferred_thickness_to_nominal_max_aggregate_ratio":2.5,
    "min_any_compacted_granular_mm":100,
    "filter_gradings":("I","II","V","VI"),"drainage_gradings":("III","IV"),
    "combined_drainage_filter_gradings":("V","VI"),
    "formula":"MR_granular=0.2*h_mm**0.45*MR_support_MPa", "nu":0.35,
    "analysis_rule":"combine contiguous unbound base+GSB; h is their total thickness",
    "construction_traffic_min_standard_axles":10000,
}, kind="constraint")
_add("37.ctsb", F37, "7.3.1-7.3.2; Eq.7.2", (23,24), {
    "min_thickness_mm":200,"7d_UCS_MPa":(1.5,3.0),
    "formula_intact_28d_E_MPa":"1000*28d_UCS_MPa",
    "typical_intact_E_MPa":(2000,6000),"design_E_MPa":600,"nu":0.25,
    "low_strength_UCS_MPa":(0.75,1.5),"low_strength_design_E_MPa":400,
    "low_strength_only_traffic_under_msa":10,
    "lab_strength_factor_over_design_field":1.5,
    "curing_min_days":3,"curing_days_if_insufficient_strength":7,
}, notes="Intact modulus formula and cracked/traffic-affected design modulus are different quantities; "
         "do not silently substitute 1000*UCS for the 600 MPa design value.")
_add("37.unbound_base", F37, "8.1", (24,25), {
    "types":("WMM","WBM","crusher run","reclaimed concrete"),
    "min_thickness_mm":150,"nu":0.35,
    "over_CTSB_MPa":{"natural_gravel":300,"crushed_rock":350},
    "over_GSB":"Eq.7.1 for combined base+GSB",
}, kind="constraint")
_add("37.ctb", F37, "8.2.1; Table 11.1", (25,26,34), {
    "min_thickness_mm":100,"required_UCS_MPa":(4.5,7.0),
    "cement_UCS_age_days":7,"lime_pozzolanic_UCS_age_days":28,
    "lab_strength_factor_over_design_field":1.5,
    "design_E_MPa":5000,"nu":0.25,"curing_min_days":7,
    "intact_modulus_formula":"Eq.7.2 using 28-day UCS",
}, kind="constraint")
_add("37.ctb_flexural", F37, "8.2.2", (26,), {
    "UCS_28d_factor":0.20,
    "caps_MPa":{"stabilised_aggregate":1.40,"lime_flyash_soil":1.05,"soil_cement":0.70},
    "approx_flexural_to_ITS_ratio_cement_bound_aggregate":1.5,
}, kind="formula")
_add("37.crack_relief", F37, "8.3", (26,27), {
    "granular_thickness_mm":100,"granular_MR_MPa":450,"nu":0.35,
    "granular_density_percent_modified_Proctor_MDD":100,
    "SAMI_binder_kg_per_10m2":(10,12),"SAMI_aggregate_m3_per_10m2":0.1,
    "SAMI_aggregate_size_mm":11.2,"SAMI_structural_layer":False,
}, notes="SAMI remains in construction metadata; exclude it from the structural stiffness stack.")
_add("37.rap", F37, "8.4", (27,), {
    "min_thickness_mm":100,"design_MR_MPa":800,"nu":0.35,
    "ITS_soaked_min_kPa":100,"ITS_dry_min_kPa":225,
    "ITS_test_C":25,"ITS_deformation_rate_mm_per_min":50,
    "foamed_bitumen_grade":"VG30",
}, kind="constraint")
_add("37.standard_load", F37, "3.6; 11.1.4", (6,33), {
    "axle_load_N":80000,"wheels_per_axle":4,"individual_wheel_N":20000,
    "analysis_wheels":2,"dual_spacing_mm":310,"contact_shape":"circle",
    "normal_pressure_MPa":0.56,"CTB_fatigue_pressure_MPa":0.80,
}, notes="Standard layered analysis uses ONE SIDE dual pair: total 40000 N, not the full 80000 N axle.")
_add("37.analysis", F37, "3.3; Table 3.1; Figs.3.1-3.6", (4,9,10,11,12), {
    "material_model":"linear elastic isotropic","interfaces":"fully bonded",
    "geometry":"upper layers infinite horizontally; subgrade semi-infinite",
    "critical_parameters":(("bottom_structural_bituminous","horizontal tensile strain"),
                            ("bottom_CTB","horizontal tensile stress and strain"),
                            ("top_subgrade","vertical compressive strain")),
    "performance_input":"absolute magnitudes; note possible compressive bottom bituminous strain",
    "figure_to_category":dict(zip(("3.1","3.2","3.3","3.4","3.5","3.6"),"abcdef")),
}, kind="analysis_requirement")
_add("37.vdf", F37, "4.4.3; Eqs.4.1-4.4", (15,), {
    "fourth_power_reference_kN":{"single_single":65,"single_dual":80,"tandem_dual":148,"tridem_dual":224},
    "formula":"equivalence=(group_load_kN/reference_kN)**4",
    "VDF":"sum of equivalent standard axles over surveyed vehicles / number of vehicles",
    "single_tyre_multi_axle":"split tandem/tridem into individual single axles and apply Eq.4.1",
}, kind="formula")
_add("37.survey", F37, "4.4.4; Table 4.1", (15,), {
    "min_hours_per_direction":24,
    "rules":(("cvpd<3000",0.20,0),("3000<=cvpd<=6000",0.15,600),("cvpd>6000",0.10,900)),
    "selection":"random loaded and empty vehicles; evaluate directions separately where spectra differ",
}, kind="constraint")
_add("37.spectrum", F37, "4.4.5", (16,), {"single":10,"tandem":20,"tridem":30}, "class interval kN")
_add("37.indicative_vdf", F37, "4.4.6; Table 4.2", (16,), {
    "0_to_150": {"plain_rolling":1.7,"hilly":0.6},
    "150_to_1500": {"plain_rolling":3.9,"hilly":1.7},
    "over_1500": {"plain_rolling":5.0,"hilly":2.8},
}, notes="Fallback only where axle-load information is unavailable and heavy-vehicle proportion is small. "
         "At the overlapping label 150 use the higher band; this is an explicit software boundary convention.")


def subgrade_resilient_modulus(cbr_percent: float, *, design_cap: bool = True) -> float:
    """37 Eqs.6.1-6.2, MPa; percent input e.g. 8, not 0.08.

    design_cap=False is for constituent soils used in the 6.4 layered analysis;
    design_cap=True applies 6.4.2 to a selected/equivalent design subgrade.
    """
    c = _number(cbr_percent,"CBR percent")
    mr = 10*c if c <= 5 else 17.6*c**0.64
    return min(100.0,mr) if design_cap else mr


def effective_subgrade_modulus(deflection_mm: float, *, design_cap: bool = True) -> float:
    """37 Eq.6.3; deflection from the prescribed 40 kN, 0.56 MPa soil system."""
    delta = _number(deflection_mm,"soil-system deflection mm")
    p, nu = 0.56, 0.35
    a = sqrt(40000/(pi*p))
    mr = 2*(1-nu**2)*p*a/delta
    return min(100.0,mr) if design_cap else mr


def granular_resilient_modulus(thickness_mm: float, support_modulus_MPa: float) -> float:
    """37 Eq.7.1; for contiguous GSB+base pass combined thickness."""
    return 0.2*_number(thickness_mm,"granular thickness mm")**0.45*_number(support_modulus_MPa,"support MR MPa")


def cemented_intact_modulus(ucs_28d_MPa: float) -> float:
    """37 Eq.7.2, intact 28-day modulus MPa; not the prescribed design default."""
    return 1000*_number(ucs_28d_MPa,"28-day UCS MPa")


def ctb_flexural_strength(ucs_28d_MPa: float, material: str) -> float:
    """37 8.2.2: min(0.2*28-day UCS, material-specific cap), MPa."""
    caps = PROVISIONS["37.ctb_flexural"].data["caps_MPa"]
    if material not in caps:
        raise ValueError(f"material must be one of {tuple(caps)}")
    return min(0.2*_number(ucs_28d_MPa,"28-day UCS MPa"),caps[material])


def bituminous_modulus(mix: str, temperature_C: float = 35, *,
                       measured_MPa: float | None = None,
                       interpolate: bool = False) -> float:
    """Table 9.2 maximum, capped by measured value when supplied.

    With no measurement the result is an indicative maximum only. For a
    modified surface over DBM, use the bottom DBM mix for structural design.
    """
    if mix in _BITUMINOUS:
        cap = _lookup(dict(zip((20,25,30,35,40),_BITUMINOUS[mix])),temperature_C,interpolate=interpolate)
    else:
        table = PROVISIONS["37.bituminous_modulus"].data["only_at_35C_MPa"]
        if mix not in table or temperature_C != 35:
            raise ValueError("Unsupported mix/temperature; BM/RAP entries exist only at 35 C")
        cap = table[mix]
    return cap if measured_MPa is None else min(cap,_number(measured_MPa,"measured modulus"))


def axle_equivalence(group_load_kN: float, axle_type: str) -> float:
    """37 Eqs.4.1-4.4; tandem/tridem input is TOTAL group load."""
    refs = PROVISIONS["37.vdf"].data["fourth_power_reference_kN"]
    if axle_type not in refs:
        raise ValueError(f"axle_type must be one of {tuple(refs)}")
    return (_number(group_load_kN,"group load",zero=True)/refs[axle_type])**4


def vehicle_damage_factor(vehicles: Iterable[Iterable[tuple[str,float]]]) -> float:
    """Survey vehicles -> mean sum of axle-group equivalence per vehicle.

    Every vehicle, including an empty-load vehicle, counts once. A group is
    (axle_type, total_group_kN); an empty vehicle iterable is invalid.
    """
    totals = [sum(axle_equivalence(load,kind) for kind,load in vehicle) for vehicle in vehicles]
    if not totals:
        raise ValueError("At least one surveyed vehicle is required")
    return sum(totals)/len(totals)


def axle_survey_minimum(cvpd: float) -> int:
    """37 Table 4.1; integer ceiling of minimum daily sample, per surveyed direction."""
    n = _number(cvpd,"cvpd",zero=True)
    rate, floor = (0.20,0) if n < 3000 else ((0.15,600) if n <= 6000 else (0.10,900))
    return ceil(max(rate*n,floor))


def indicative_vdf(cvpd: float, terrain: str) -> float:
    n = _number(cvpd,"cvpd",zero=True)
    if terrain not in ("plain_rolling","hilly"):
        raise ValueError("terrain must be plain_rolling or hilly")
    band = "0_to_150" if n < 150 else ("150_to_1500" if n <= 1500 else "over_1500")
    return PROVISIONS["37.indicative_vdf"].data[band][terrain]

# Catalogue figures were read visually from the supplied charts; no curve fitting.
# Each row: surface, binder, structural base, bottom subbase; six traffic points.
_G1 = [
([30,40,40,40,40,40],[65,80,105,115,130,140]),
([30,40,40,40,40,40],[60,70,95,110,120,130]),
([30,30,30,40,40,40],[50,70,100,100,115,125]),
([30,30,30,40,40,40],[50,60,90,95,105,115]),
([30,30,40,40,40,40],[50,55,75,90,100,110]),
([30,30,40,40,40,40],[50,50,70,85,95,105]),
([30,30,40,40,40,40],[50,50,55,75,90,100]),
([30,30,30,40,40,40],[50,50,50,65,75,85]),
]
_G2_CTB = [[110,120,125,100,100,100],[100,110,125,100,100,100],
[100,100,120,100,100,100],[100,100,115,100,100,100],
[100,100,115,100,100,100],[100,100,110,100,100,100],
[100,100,105,100,100,100],[100,100,100,100,100,100]]
_G3_CTB = [[170,170,160,140,150,150],[170,170,160,140,145,145],
[170,170,160,135,140,145],[160,170,150,130,135,140],
[160,170,150,130,135,140],[160,160,150,130,135,140],
[160,160,150,130,135,140],[150,150,150,120,125,130]]
_G4 = [
([40,40,50,40,40,40],[0,0,0,60,80,90],[100,100,120,120,110,120]),
([40,40,40,40,40,40],[0,0,0,60,70,70],[100,100,120,110,120,130]),
([40,40,40,40,40,40],[0,0,0,60,60,60],[100,100,110,100,120,130]),
]
_G4 += [
([40]*6,[0,0,0,60,60,60],[100,100,100,100,110,120]),
([40]*6,[0,0,0,60,60,60],[100,100,100,100,100,110]),
([40]*6,[0,0,0,60,60,65],[100]*6),
([40]*6,[0,0,0,60,60,60],[100]*6),
([40]*6,[0,0,0,60,60,60],[100]*6),
]
_G5 = [
([50,50,50,60,60,60],[160,170,190,175,180,185]),
([50,50,55,60,60,60],[155,165,185,170,175,175]),
([50,50,55,60,60,60],[155,165,185,165,170,175]),
([50,50,55,60,60,60],[145,155,170,155,160,165]),
([50,50,55,60,60,60],[145,155,170,155,160,165]),
([50,50,50,60,60,60],[135,145,155,150,155,160]),
([50,50,55,60,60,60],[130,140,150,140,145,150]),
]
_G5 += [([50,50,55,60,60,60],[120,130,140,130,135,140])]
_G6_BINDER = [[0,0,50,70,85,95],[0,0,50,65,75,85],
[0,0,50,55,70,75],[0,0,50,50,60,70],[0,0,50,50,55,70],
[0,0,50,50,55,70],[0,0,50,50,55,70],[0,0,50,50,55,65]]

CATALOGUES: dict[int, dict[str, Any]] = {}
_CBR_POINTS = (5,6,7,8,9,10,12,15)
_TRAFFIC_POINTS = (5,10,20,30,40,50)
for _fig in range(1,49):
    _group, _row = divmod(_fig-1,8)
    _rows = []
    for _j in range(6):
        if _group == 0:
            _s,_b = _G1[_row]
            _layers = (("surface",_s[_j]),("binder",_b[_j]),("WMM",250),("GSB",150 if _j == 0 else 200))
        elif _group == 1:
            _layers = (("surface",(40,40,50,40,40,40)[_j]),("binder",(0,0,0,60,60,60)[_j]),
                       ("granular_crack_relief",100),("CTB",_G2_CTB[_row][_j]),("CTSB",200))
        elif _group == 2:
            _layers = (("surface",(40,50,30,40,40,40)[_j]),("binder",(0,0,50,60,60,60)[_j]),
                       ("CTB",_G3_CTB[_row][_j]),("CTSB",200))
        elif _group == 3:
            _s,_b,_rap = _G4[_row]
            _layers = (("surface",_s[_j]),("binder",_b[_j]),("stabilised_RAP",_rap[_j]),("CTSB",200))
        elif _group == 4:
            _b,_ctb = _G5[_row]
            _layers = (("surface",(30,30,30,40,40,40)[_j]),("binder",_b[_j]),
                       ("granular_crack_relief",100),("CTB",_ctb[_j]),("GSB",200))
        else:
            _layers = (("surface",(40,40,30,40,40,40)[_j]),("binder",_G6_BINDER[_row][_j]),("WMM",150),("CTSB",200))
        _rows.append(tuple((name,h) for name,h in _layers if h > 0))
    CATALOGUES[_fig] = {"category":"abcdef"[_group],"effective_CBR_percent":_CBR_POINTS[_row],
                         "traffic_to_layers_mm":dict(zip(_TRAFFIC_POINTS,_rows)),
                         "nonstructural_interface":"SAMI" if _group == 2 else None}
    _add(f"37.figure_12_{_fig}", F37, f"Fig.12.{_fig}; 12.1-12.3", (36+(_fig-1)//3,),
         CATALOGUES[_fig], "top-to-bottom layer thicknesses mm; traffic msa", "trial_catalogue",
         "Illustrative catalogue; no interpolation and no automatic design approval.")
del _fig,_group,_row,_rows,_j,_layers,_s,_b,_rap,_ctb


def catalogue_profile(category: str, effective_cbr_percent: float, traffic_msa: float) -> dict[str, Any]:
    """One of 288 exact trial sections (48 charts x 6 traffic values).

    No rounding to another CBR/traffic and no interpolation. SAMI is metadata.
    """
    if category not in FLEXIBLE_CATEGORIES:
        raise ValueError("category must be a-f")
    _number(effective_cbr_percent,"effective CBR")
    _number(traffic_msa,"traffic msa")
    if effective_cbr_percent not in _CBR_POINTS or traffic_msa not in _TRAFFIC_POINTS:
        raise ValueError(f"Use exact CBR {_CBR_POINTS} and traffic {_TRAFFIC_POINTS}")
    fig = 1 + "abcdef".index(category)*8 + _CBR_POINTS.index(effective_cbr_percent)
    result = copy.deepcopy(CATALOGUES[fig])
    result["layers_mm"] = result.pop("traffic_to_layers_mm")[traffic_msa]
    result["traffic_msa"] = traffic_msa
    result["source"] = PROVISIONS[f"37.figure_12_{fig}"].source
    result["design_verified"] = False
    return result


# ---------------------- IRC:SP:49-2014 ----------------------
D49 = "IRC:SP:49-2014"
_add("49.geometry", D49, "2", (2,), {
    "DLC_extension_each_side_mechanised_mm":500,"DLC_extension_each_side_manual_semi_mm":200,
    "major_NH_SH_min_thickness_mm":150,"other_roads_recommended_thickness_mm":100,
}, kind="constraint")
_add("49.materials", D49, "3.1-3.4; Table 1", (2,3), {
    "cements":("OPC","PPC","PSC"),"sulphate_soil_trigger_percent":0.5,
    "sulphate_cement_options":("sulphate resisting Portland cement","PSC slag up to 50%"),
    "max_aggregate_mm":26.5,"max_aggregate_water_absorption_percent":3,
    "flyash_percent_CM":(15,30),"GBFS_percent_CM":(25,50),
    "OPC_min_with_mineral_admixture_kg_m3":100,"mixing_curing_water_max_pH":9,
    "aggregate_grading_mm_to_percent": {
        26.5:(100,100),19:(75,95),9.5:(50,70),4.75:(30,55),2.36:(17,42),
        0.6:(8,22),0.3:(7,17),0.15:(2,12),0.075:(0,10)},
}, notes="Values as stated in this IRC source; referenced BIS documents were not independently extracted.")
_add("49.strength", D49, "4.1", (4,), {
    "age_days":7,"consecutive_cubes":5,"min_group_mean_MPa":7,"min_individual_MPa":5.5,
}, kind="constraint")
_add("49.mix", D49, "4.2", (4,), {
    "max_aggregate_cement_ratio":{"OPC":14,"PPC":12,"PSC":12},
    "min_cementitious_kg_m3":140,
    "trial_water_percent_total_material_mass":(5,5.5,6,6.5,7),
    "placement_moisture_compensation_percent":1,
}, kind="constraint", notes="Trial moisture range is not a thermal or hygroscopic strain coefficient.")
_add("49.drainage", D49, "5", (4,),
     {"GSB_below_DLC":True,"extent":"throughout road width"}, kind="arrangement")
_add("49.subgrade", D49, "6", (4,), {
    "min_modified_Proctor_density_percent":97,"soft_wet_subgrade_permitted":False,
    "requirement":"uniform compacted support; fill and compact trenches/soft spots",
}, kind="constraint")
_add("49.qc", D49, "7.10; 7.6.1", (6,8), {
    "thickness_tolerance_mm":10,"density_area_m2":2000,
    "strength_samples_per_1000m2_or_part_daily":3,
    "min_density_percent_trial_mean":97,"min_edge_density_percent_trial_mean":95,
    "edge_strip_mm":500,
}, kind="constraint", notes="Three strength samples are not automatically three cubes; "
         "the clause separately specifies cube preparation/testing.")


# ---------------------- IRC:15-2017 ----------------------
C15 = "IRC:15-2017"
_add("15.concrete_materials", C15, "3.1-3.6", (3,4,5,6,7,8), {
    "cement_28d_min_strength_MPa":43,"cement_types":("OPC43/53","PPC","PSC","composite"),
    "sulphate_cement_note":"special cement selection for saline/sulphate conditions; PSC if chlorides present",
    "max_chemical_admixture_percent_CM":2,
    "max_flyash_percent_CM":25,"max_GGBFS_percent_CM":50,
    "max_silica_fume_percent_OPC":10,"max_metakaolin_percent_CM":20,
    "max_aggregate_chloride_percent":0.06,"max_aggregate_SO3_percent":0.25,
    "max_aggregate_water_absorption_percent":2,
    "max_combined_flakiness_elongation_percent":35,"max_aggregate_impact_percent":30,
    "max_PQC_aggregate_mm":31.5,"max_DLC_aggregate_mm":26.5,
    "max_soundness_loss_percent":{"sodium_sulphate_5cycles":12,"magnesium_sulphate_5cycles":18},
    "DLC_only_max_steel_slag_RCA_percent_coarse_aggregate":30,
    "dowel_steel":"Grade I plain steel","tie_steel":"Fe500 TMT",
    "fine_aggregate_max_percent":{"clay_lumps":1,"coal_lignite":1,"75um_natural":3,"75um_crushed":12,"75um_blended":8},
    "temperature_mesh_min_mass_kg_m2":3.14,"temperature_mesh_top_cover_mm":(50,75),
}, kind="constraint")
_add("15.air_entrainment", C15, "3.2.1", (4,), {
    "normal_percent_by_max_aggregate_mm":{31.5:(3.0,6.0),19:(3.5,6.5)},
    "freezing_percent_by_max_aggregate_mm":{31.5:(4.0,7.0),19:(4.5,7.5)},
}, notes="Conditional air-entraining admixture values; not mandatory air content for every concrete.")
_add("15.fine_grading", C15, "3.3.4; Table 1", (6,7), {
    "sieves_mm":(10,4.75,2.36,1.18,0.6,0.3,0.15),
    "I":((100,100),(90,100),(60,95),(30,70),(15,34),(5,20),(0,10)),
    "II":((100,100),(90,100),(75,100),(55,90),(35,59),(8,30),(0,10)),
    "III":((100,100),(90,100),(85,100),(75,100),(60,79),(12,40),(0,10)),
    "crushed_sand_150um_upper_percent":20,
    "tolerance":"outside particular sieve limits up to 5 percentage points, cumulative 10; "
                "not at 600um nor coarse limit of Zone I",
}, "percent passing by mass")
_add("15.dlc_grading", C15, "3.3.5; Table 2", (7,), {
    26.5:(100,100),19:(75,95),9.5:(50,70),4.75:(30,55),2.36:(17,42),
    0.6:(8,22),0.3:(7,17),0.15:(2,12),0.075:(0,5)},
    "sieve mm -> percent passing", notes="75um upper limit 5%, unlike SP:49 Table 1's 10%; "
    "keep the two source requirements separate and choose project governing specification.")
_add("15.pqc_grading", C15, "3.3.5; Table 3", (8,), {
    "sieves_mm":(37.5,31.5,26.5,19,9.5,4.75,0.6,0.15),
    "31.5":((100,100),(90,100),(85,95),(68,88),(45,65),(30,55),(8,30),(0,10)),
    "26.5":((100,100),(100,100),(90,100),(75,95),(50,70),(30,55),(8,30),(0,10)),
    "19":((100,100),(100,100),(100,100),(90,100),(48,78),(30,58),(8,35),(0,12)),
    "wet_75um_max_percent":{"crushed_sand":5,"natural_sand":2},
}, "percent passing by mass")
_add("15.mix", C15, "4.1-4.5", (10,11,12), {
    "28d_flexural_strength_MPa":4.5,"max_free_water_CM_ratio":0.40,
    "min_cement_content_kg_m3":360,"max_OPC_kg_m3":450,
    "site_flyash_max_percent_CM":25,"site_flyash_min_OPC_kg_m3":310,
    "GGBFS_min_cement_kg_m3":250,
    "flexure_test_beam_mm":(150,150,700),"test_loading":"third point",
    "min_paired_cube_beam_specimens_for_correlation":30,
    "fallback_formula":"fcr=0.7*sqrt(fck)",
    "major_project_rule":"measure flexural strength; cube correlation is not allowed for major projects",
    "slump_slipform_mm":(20,30),"slump_fixedform_mm":(40,60),
}, kind="constraint", notes="Section 4.1.3 fallback correlation is retained with its conditions; "
         "not automatically used for PQC material generation.")
_add("15.layers", C15, "6.1; 6.3.1-6.3.6", (16,17), {
    "top_to_bottom":("PQC","DLC","GSB drainage","GSB filter","select subgrade"),
    "min_select_subgrade_thickness_mm":500,"min_subgrade_CBR_percent":8,
    "min_GSB_permeability_m_day":300,
    "min_GSB_filter_mm":100,"min_GSB_drainage_mm":100,
    "drainage_over_geocomposite_min_mm":150,
    "filter_gradings":("I","II","V","VI"),"drainage_gradings":("III","IV"),
    "GSB_min_density_percent_modified_Proctor_MDD":98,
    "min_soaked_10percent_fines_value_kN":50,
    "soundness_test_water_absorption_trigger_percent":2,
}, kind="constraint", notes="6.3.5 also mentions minimum CBR 8%, while Table 4 "
         "specifies CBR30 for gradings I-IV. Table-specific requirements are retained separately.")
_GSB_SIEVES = (75,53,26.5,9.5,4.75,2.36,0.85,0.425,0.075)
_add("15.gsb_grading", C15, "Table 4; 6.3.3-6.3.6", (17,18), {
    "sieves_mm":_GSB_SIEVES,
    "I":((100,100),(80,100),(55,90),(35,65),(25,55),(20,40),None,(10,15),"<5"),
    "II":(None,(100,100),(70,100),(50,80),(40,65),(30,50),None,(10,15),"<5"),
    "III":(None,(100,100),(55,75),None,(10,30),None,None,None,"<5"),
    "IV":(None,(100,100),(50,80),None,(15,35),None,None,None,"<5"),
    "V":((100,100),(80,100),(55,90),(35,65),(25,50),(10,20),(2,10),(0,5),None),
    "VI":(None,(100,100),(75,100),(55,75),(30,55),(10,25),None,(0,8),(0,3)),
    "min_CBR_percent":{"I":30,"II":30,"III":30,"IV":30,"V":None,"VI":None},
    "fraction_under_0_425mm_max_LL_percent":25,"max_PI_percent":6,
}, "percent passing by mass; None means dash/not specified")
_add("15.cbr_k", C15, "6.4; Table 5", (18,),
     dict(zip((5,7,10,15,20,50,100),(42,48,55,62,69,140,220))), "CBR percent -> k MPa/m")
_add("15.effective_k_granular", C15, "6.5.2; Table 6", (19,), {
    "untreated":{150:{28:39,56:63,84:92},225:{28:44,56:75,84:102},300:{28:53,56:88,84:119}},
    "cement_treated":{100:{28:76,56:127},150:{28:108,56:173},200:{28:141,56:225}},
}, "thickness mm -> subgrade k MPa/m -> effective k MPa/m",
     notes="Table dashes at subgrade k=84 for cement-treated subbase are unavailable, not zero.")
_add("15.effective_k_dlc", C15, "6.5.3; Table 7 and footnote", (19,), {
    "raw":{100:{48:208,55:278,62:389},150:{48:277,55:417}},
    "max_design_k_MPa_per_m":300,
}, "thickness mm -> subgrade k MPa/m -> effective k MPa/m",
     notes="Raw 417* retained; footnote requires 300 instead of 417 in proportional calculations. "
           "The maximum design k is 300 MPa/m; raw 389 also exceeds that maximum. "
           "150mm DLC at k=62 is a dash, not an invitation to extrapolate.")
_add("15.joints", C15, "8.3-8.6", (26,33,34,35,36,38), {
    "typical_slab_width_mm":3500,"typical_slab_length_mm":4500,
    "slab_length_at_least_width":True,"curve_joint_spacing_reduction_percent":(20,30),
    "expansion":"at abutting structures as required; not at routine regular intervals",
    "contraction":"weakened-plane sawcut; groove initially 1/4 to 1/3 slab depth",
    "construction_joint_trigger_stop_minutes":30,
    "emergency_construction_joint_zone":"middle third of slab length",
    "longitudinal":"tied warping joint",
}, kind="arrangement")
_add("15.dowels", C15, "8.3.2.2; 8.3.6-8.3.11", (33,34,35), {
    "min_length_mm":500,"depth":"slab mid-depth",
    "depth_tolerance_mm":25,"rotation_horizontal_vertical_tolerance_mm":10,
    "longitudinal_shift_tolerance_mm":50,
    "contraction_sheathed_length_fraction_min":0.60,
    "expansion_sheathed_length":"half bar length + 50 mm",
    "sheath_average_max_thickness_mm":0.5,
    "expansion_cap_length_mm":100,"expansion_cap_thickness_mm":2,
    "max_pullout_mean_bond_stress_MPa_at_7d":0.14,
    "minimum_pullout_displacement_mm":0.25,
    "diameter_and_spacing":"project design per IRC:58; no arbitrary default here",
    "thin_slab_note":"dowels may be omitted if slab thickness below 200 mm",
}, kind="constraint")
_TIE = (
    (150,8,330,530,440,480),(150,10,520,830,510,560),
    (200,10,390,620,510,560),(200,12,560,900,580,640),
    (250,12,450,720,580,640),(300,12,370,600,580,640),
    (300,16,660,1060,720,800),(350,12,320,510,580,640),(350,16,570,910,720,800))
_add("15.tie_bars", C15, "8.4.3-8.4.6; Table 8", (36,37), {
    "table_columns":("slab_mm","diameter_mm","max_spacing_plain_mm","max_spacing_deformed_mm","min_length_plain_mm","min_length_deformed_mm"),
    "rows":_TIE,"table_lane_width_mm":3500,
    "function":"resist tensile separation; not a shear load-transfer device",
    "position":"middle third at mid-depth; minimum 30 mm below joint groove",
    "joint_centre_tolerance_mm":50,"corrosion_coating_each_side_mm":75,
}, kind="constraint")


def effective_k15(subgrade_k_MPa_per_m: float, thickness_mm: float, subbase: str,
                  *, interpolate: bool = False, raw: bool = False) -> float:
    """15 Tables 6/7; bilinear interpolation only when explicitly requested.

    DLC design entries are capped BEFORE interpolation (Table 7 footnote).
    raw=True is an audit lookup only and must not be used as design stiffness.
    Missing/dashed cells and extrapolation always raise ValueError.
    """
    k = _number(subgrade_k_MPa_per_m,"subgrade k")
    h = _number(thickness_mm,"subbase thickness")
    if subbase == "DLC":
        tab = copy.deepcopy(PROVISIONS["15.effective_k_dlc"].data["raw"])
        if not raw:
            tab = {t:{x:min(300,y) for x,y in row.items()} for t,row in tab.items()}
    elif subbase in ("untreated","cement_treated"):
        tab = PROVISIONS["15.effective_k_granular"].data[subbase]
    else:
        raise ValueError("subbase must be DLC, untreated, or cement_treated")
    if h in tab:
        return _lookup(tab[h],k,interpolate=interpolate)
    if not interpolate:
        raise ValueError(f"Use tabulated thicknesses {tuple(tab)}")
    hs = sorted(tab)
    for lo,hi in zip(hs,hs[1:]):
        if lo < h < hi:
            a = _lookup(tab[lo],k,interpolate=True)
            b = _lookup(tab[hi],k,interpolate=True)
            return a+(b-a)*(h-lo)/(hi-lo)
    raise ValueError("Thickness outside tabulated range; extrapolation is prohibited")


# ---------------------- IRC:19-2005 ----------------------
W19 = "IRC:19-2005"
_add("19.description", W19, "2.1.1-2.1.3", (3,4), {
    "material":"mechanically interlocked coarse aggregate with screening/binding fines and water",
    "roles":("subbase","base","surfacing"),
    "directly_on_silty_clayey_subgrade":False,
    "required_intervening_layer":"suitable granular layer",
    "over_existing_bituminous":"scarify or provide adequate bond and interface drainage",
}, kind="constraint")
_add("19.physical", W19, "3.1; Table 1", (4,), {
    "subbase":{"LA_max_percent":50,"AIV_max_percent":40,"flakiness_max_percent":None},
    "base":{"LA_max_percent":40,"AIV_max_percent":30,"flakiness_max_percent":20},
    "surfacing":{"LA_max_percent":40,"AIV_max_percent":30,"flakiness_max_percent":15},
    "abrasion_impact_rule":"either LA or AIV may satisfy the requirement",
    "wet_AIV":"required for aggregates softened by water, e.g. brick, kankar, laterite",
    "flakiness_applicability":"crushed/broken stone and crushed slag only",
}, kind="constraint")
_add("19.aggregate_grading", W19, "3.2; Table 2", (5,), {
    1:{"size_range_mm":(45,90),"compacted_lift_mm":100,"roles":("subbase",),
       "sieves":{125:(100,100),90:(90,100),63:(25,60),45:(0,15),22.4:(0,5)}},
    2:{"size_range_mm":(45,63),"compacted_lift_mm":75,"roles":("subbase","base","surfacing"),
       "sieves":{90:(100,100),63:(90,100),53:(25,75),45:(0,15),22.4:(0,5)}},
    3:{"size_range_mm":(22.4,53),"compacted_lift_mm":75,"roles":("subbase","base","surfacing"),
       "sieves":{63:(100,100),53:(90,100),45:(65,90),22.4:(0,10),11.2:(0,5)}},
}, "mm; sieve -> percent passing by mass")
_add("19.screenings", W19, "3.3; Table 3", (5,6), {
    "A":{13.2:(100,100),11.2:(95,100),5.6:(15,35),0.18:(0,10)},
    "B":{11.2:(100,100),5.6:(90,100),0.18:(15,35)},
    "allowed_by_coarse_grade":{1:("A",),2:("A","B"),3:("B",)},
    "alternative_crushable_screenings":{"LL_strictly_below_percent":20,"PI_strictly_below_percent":6,"75um_max_percent":10},
    "crushable_exception":"Table 3 grading not binding for moorum/gravel; screenings may be omitted for crushable coarse aggregate",
}, "sieve mm -> percent passing by mass")
_add("19.construction", W19, "4.1-4.8", (7,8,9), {
    "sequence":("prepare drained foundation","provide lateral confinement/shoulders",
                "spread coarse aggregates","roll coarse skeleton","apply dry screenings in >=3 thin passes",
                "water, broom and roll/grout","apply binding material in >=2 thin passes if needed",
                "final compact; dry overnight; correct hungry spots; let macadam set"),
    "roller_static_weight_kN":(80,100),
    "max_compacted_grade1_lift_mm":100,"grade2_grade3_lift_mm":75,
    "soft_yielding_subgrade_rolling_permitted":False,
    "traffic":"none before set; bituminous surfacing only when WBM is fully dry",
}, kind="construction_metadata", notes="No elastic modulus is specified in these WBM clauses. "
         "For the flexible-pavement base use IRC:37 support-dependent modulus rules.")

# ---------------------- IRC:6-2017 ----------------------
B6 = "IRC:6-2017"
_add("6.classification", B6, "201.1", (4,), {
    "70R":"permanent bridges/culverts; also check Class A",
    "AA":"specified municipal/industrial/highway areas; also check Class A",
    "A":"normal permanent bridges/culverts","B":"normally timber bridges",
    "SV":"new bridges in selected corridors where occasional special transport is expected",
}, notes="Bridge load classes are separate optional deck load cases, not pavement legal axle limits.")
_add("6.load_types", B6, "202.1", (5,6), {
    "G":"dead","Q":"live","Gs":"snow","Qim":"vehicular impact",
    "Fim":"floating-body/vessel impact","VC":"vehicle collision","W":"wind",
    "Fwc":"water current","Fa/Fb/Ff":"tractive/braking/bearing restraint",
    "Fcf":"centrifugal","Gb":"buoyancy","Fep":"earth pressure/live surcharge",
    "Fte":"temperature restraint effects","Fd":"deformation","FS":"secondary",
    "Fer":"erection","Feq":"seismic","Fwp":"wave","Ge":"grade",
}, kind="load_case_labels", notes="Only labels from the requested clause; no wind/seismic/impact formulas "
         "or load factors outside the requested provisions are introduced.")
_add("6.positioning", B6, "204.1.2-204.1.5; Fig.1 notes", (10,11), {
    "search":"translate trains longitudinally/transversely within clearances for maximum response",
    "all_unit_axles_simultaneous":True,"adjacent_direction":"governing stress direction",
    "uncovered_area":"no extra live load except Table 6 provision",
    "70R_min_CW_mm":5300,"70R_kerb_clearance_mm":1200,"70R_passing_clearance_mm":1200,
    "70R_occupied_lanes":2,
    "70R_max_single_axle_tonnes":20,"70R_max_two_axle_bogie_tonnes":40,
    "70R_max_bogie_centres_mm":1220,
}, kind="analysis_requirement")
_add("6.70R_wheeled", B6, "204.1; Fig.1; Annex A notes 1-3", (10,11,84), {
    "axle_loads_tonnes":(8,12,12,17,17,17,17),
    "axle_gaps_mm":(3960,1520,2130,1370,3050,1370),
    "front_overhang_mm":610,"rear_overhang_mm":910,
    "min_last_to_next_first_axle_mm":30000,"total_tonnes":100,
    "max_tyre_pressure_kgf_cm2":5.273,
    "tyre_patterns":{
        "L":{"overall_width_mm":2790,"tyre_width_mm":410,"rim_diameter_mm":610,
             "dual_pair_width_mm":860,"wheel_centres_y_mm":(-1190,-740,740,1190)},
        "M":{"overall_width_mm":2790,"tyre_width_mm":410,"rim_diameter_mm":610,
             "central_clear_gap_mm":380,"wheel_centres_y_mm":(-1190,-395,395,1190)},
        "N":{"overall_width_mm":2790,"tyre_width_mm":230,"rim_diameter_mm":510,
             "dual_pair_width_mm":510,"between_pair_clear_gap_mm":250,
             "wheel_centres_y_mm":(-1280,-1000,-520,-240,240,520,1000,1280)}},
    "tread_width_rule":"overall tyre width minus 25mm if <=225mm; minus 50mm otherwise",
    "contact_area_rule":"tyre force / selected pressure",
}, notes="610/510mm are tyre/rim dimensions, NOT rectangular ground-contact lengths. "
         "Transverse centre coordinates are reconstructed from the dimension chains. "
         "The Fig.1 max-single/bogie cases are separate from the 100t train.")
_add("6.70R_tracked", B6, "204.1; Fig.1", (10,11), {
    "total_tonnes":70,"tonnes_per_track":35,"track_length_mm":4570,
    "track_width_mm":840,"overall_outside_track_width_mm":2900,
    "derived_track_centre_spacing_mm":2060,"min_nose_tail_gap_mm":90000,
})
_add("6.A_train", B6, "204.1; Fig.2; Table 2", (12,13), {
    "axle_loads_tonnes":(2.7,2.7,11.4,11.4,6.8,6.8,6.8,6.8),
    "axle_gaps_mm":(1100,3200,1200,4300,3000,3000,3000),
    "transverse_wheel_centres_mm":1800,"min_nose_tail_gap_mm":18500,
    "last_to_next_first_axle_mm":20000,
    "contact_B_longitudinal_W_transverse_mm":{11.4:(250,500),6.8:(200,380),2.7:(150,200)},
})
_add("6.B_train", B6, "204.1; Fig.4; Table 4", (14,15), {
    "axle_loads_tonnes":(1.6,1.6,6.8,6.8,4.1,4.1,4.1,4.1),
    "axle_gaps_mm":(1100,3200,1200,4300,3000,3000,3000),
    "transverse_wheel_centres_mm":1800,"min_nose_tail_gap_mm":18500,
    "last_to_next_first_axle_mm":20000,
    "contact_B_longitudinal_W_transverse_mm":{6.8:(200,380),4.1:(150,300),1.6:(125,175)},
    "multi_lane_min_CW_mm":5060,
})
_add("6.A_B_clearances", B6, "Tables 3 and 5; Figs.3 and 5", (13,15), {
    "kerb_min_mm":150,
    "A":{"two_train_width_start_mm":5300,"full_gap_width_mm":6100},
    "B":{"two_train_width_start_mm":5060,"full_gap_width_mm":5860},
    "passing_gap_start_mm":400,"passing_gap_full_mm":1200,
}, notes="Passing gap varies linearly with CW between the stated endpoints.")
_add("6.lane_combinations", B6, "204.3; Tables 6 and 6A", (16,17,18,19,20), {
    "CW_design_lanes_mm":((0,5300,1),(5300,9600,2),(9600,13100,3),
                          (13100,16600,4),(16600,20100,5),(20100,23600,6)),
    "single_lane_class_A_occupied_width_mm":2300,
    "single_lane_remaining_mass_load_kg_m2":500,
    "substitution":"70R wheeled may be replaced by 70R tracked, AA tracked or AA wheeled",
    "heavy_vehicle_exclusion_zone_at_kerb_mm":7250,
    "heavy_vehicle_exclusion_zone_internal_mm":7000,
    "partial_occupancy":"also consider fewer vehicles if governing, e.g. torsion",
}, notes="Table 6 prints an overlapping 4-lane upper bound of 20.1m; "
         "Table 6A explicitly gives 13.1<=CW<16.6m, used here. "
         "Mixed/heavy patterns have extra minimum widths in Table 6A; see lane_load_cases(). "
         "Table 6A one-lane illustration starts at 4.25m; narrower widths need project review.")
_add("6.SV", B6, "204.5.1-204.5.3; Figs.6,6A,6B", (21,22), {
    "total_tonnes":385,"prime_mover_axles_tonnes":(6,9.5,9.5),
    "trailer_axles":20,"trailer_axle_tonnes":18,
    "prime_mover_gaps_mm":(3200,1370),"rear_prime_to_first_trailer_mm":5389,
    "trailer_axle_gap_mm":1500,"trailer_first_to_last_mm":28500,
    "trailer_tyre_count_per_axle":8,"trailer_tonnes_per_tyre":2.25,
    "trailer_tyre_B_transverse_mm":156,"trailer_tyre_W_longitudinal_mm":274,
    "trailer_transverse_dimension_chain_mm":(244,375,900,403,506),
    "derived_trailer_tyre_centres_y_mm":(-1397,-1153,-647,-403,403,647,1153,1397),
    "trailer_width_mm":3000,"nominal_height_dimension_mm":"1175+300",
    "max_transverse_eccentricity_mm":300,
    "centering":"centre of the relevant carriageway in Fig.6B; consider independent/common support configurations",
}, notes="Trailer coordinates are reconstructed from the wheel-centre dimension chain. "
         "Fig.6A gives trailer contacts, not prime-mover contact geometry. "
         "Full SV axle data are provided; full contact patches require explicit prime-mover tyre data.")
_add("6.AA", B6, "Annex A; Fig.A-1", (86,), {
    "tracked":{"total_tonnes":70,"tonnes_per_track":35,"track_length_mm":3600,
               "track_width_mm":850,"outside_width_mm":2900,"derived_centre_spacing_mm":2050},
    "wheeled":{"total_tonnes":40,"axle_loads_tonnes":(20,20),"axle_gaps_mm":(1200,),
               "tyre_loads_each_axle_tonnes":(3.75,6.25,6.25,3.75),
               "wheel_centres_y_mm":None,
               "contact_longitudinal_mm":150,"contact_transverse_mm":300,
               "transverse_view_labels_m":("2.050","1.150","0.850"),
               "plan_inner_centre_label_m":"1.000",
               "geometry_status":"the supplied low-resolution cross-section and plan do not resolve to one unambiguous transverse centre chain"},
    "min_CW_mm":5300,"kerb_min_mm":1200,"occupied_lanes":2,
    "min_nose_tail_spacing_mm":90000,
    "independent_max_single_axle_tonnes":20,"independent_max_bogie_tonnes":40,
    "max_bogie_centres_mm":1200,
}, notes="The wheeled figure labels 3.75/6.25/6.25/3.75 tonnes across EACH 20t axle; "
         "do not replace them with four equal wheel loads. Transverse labels in the "
         "low-resolution cross-section and plan are retained separately; caller must "
         "supply verified transverse wheel centres for contact generation.")

# These are physical unit definitions, not additional IRC material constants.
STANDARD_GRAVITY_M_S2 = 9.80665
TONNE_FORCE_N = 1000 * STANDARD_GRAVITY_M_S2
KGF_CM2_TO_MPA = STANDARD_GRAVITY_M_S2 / 100


@dataclass(frozen=True)
class Patch:
    """Uniform normal pressure, positive DOWNWARD. x=travel, y=transverse.

    Coordinates/dimensions mm, force N, pressure MPa. Rectangle: length along
    x and width along y. Circle: radius_mm. No point loads are silently created.
    """
    x_mm: float
    y_mm: float
    force_N: float
    shape: str
    length_mm: float | None = None
    width_mm: float | None = None
    radius_mm: float | None = None
    label: str = ""

    def __post_init__(self) -> None:
        for name in ("x_mm","y_mm"):
            x = getattr(self,name)
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x):
                raise ValueError(f"{name} must be finite numeric")
        _number(self.force_N,"patch force")
        if self.shape == "rectangle":
            _number(self.length_mm,"patch length")
            _number(self.width_mm,"patch width")
            if self.radius_mm is not None:
                raise ValueError("Rectangle cannot also have a radius")
        elif self.shape == "circle":
            _number(self.radius_mm,"patch radius")
            if self.length_mm is not None or self.width_mm is not None:
                raise ValueError("Circle cannot also have rectangular dimensions")
        else:
            raise ValueError("shape must be circle or rectangle")

    @property
    def area_mm2(self) -> float:
        return pi*self.radius_mm**2 if self.shape == "circle" else self.length_mm*self.width_mm

    @property
    def pressure_MPa(self) -> float:
        return self.force_N/self.area_mm2

    @property
    def bounds_mm(self) -> tuple[float,float,float,float]:
        hx = self.radius_mm if self.shape == "circle" else self.length_mm/2
        hy = self.radius_mm if self.shape == "circle" else self.width_mm/2
        return self.x_mm-hx,self.y_mm-hy,self.x_mm+hx,self.y_mm+hy

    def to_SI(self) -> dict[str, Any]:
        return {"x_m":self.x_mm/1000,"y_m":self.y_mm/1000,"force_N":self.force_N,
                "pressure_Pa":self.pressure_MPa*1e6,"shape":self.shape,
                "length_m":None if self.length_mm is None else self.length_mm/1000,
                "width_m":None if self.width_mm is None else self.width_mm/1000,
                "radius_m":None if self.radius_mm is None else self.radius_mm/1000,
                "label":self.label}


def circular_patch(force_N: float, pressure_MPa: float, *, x_mm: float = 0,
                   y_mm: float = 0, label: str = "") -> Patch:
    """A=P/p; equivalent circle. Geometry conversion, not a new design formula."""
    radius = sqrt(_number(force_N,"force")/(pi*_number(pressure_MPa,"pressure")))
    return Patch(x_mm,y_mm,force_N,"circle",radius_mm=radius,label=label)


def flexible_standard_patches(*, ctb_fatigue: bool = False) -> tuple[Patch, ...]:
    """37 Table3.1/3.6: one dual pair, 20kN each, 310mm centres."""
    if not isinstance(ctb_fatigue,bool):
        raise TypeError("ctb_fatigue must be bool")
    p = 0.80 if ctb_fatigue else 0.56
    return tuple(circular_patch(20000,p,y_mm=y,label="37 standard dual pair") for y in (-155,155))


def rigid_axle_group_patches(total_group_load_kN: float, group: str, *,
                             wheel_offsets_y_mm: Iterable[float],
                             axle_spacing_mm: float = 1300,
                             tyre_pressure_MPa: float = 0.8) -> tuple[Patch,...]:
    """58 5.2/6.1.2: single/tandem/tridem with caller-supplied transverse geometry.

    Equal group load sharing and circular contacts are EXPLICIT modelling
    choices. The requested clauses do not prescribe all transverse wheel
    centres, so they are required inputs; no IRC:37 spacing is imported here.
    """
    count = {"single":1,"tandem":2,"tridem":3}.get(group)
    if count is None:
        raise ValueError("group must be single, tandem or tridem")
    ys = tuple(wheel_offsets_y_mm)
    if not ys:
        raise ValueError("Supply actual wheel offsets for each individual tyre")
    gap = _number(axle_spacing_mm,"axle spacing")
    force = _number(total_group_load_kN,"total group kN")*1000/(count*len(ys))
    return tuple(circular_patch(force,tyre_pressure_MPa,x_mm=i*gap,y_mm=y,
                 label=f"58 {group} equal-share circle") for i in range(count) for y in ys)


def axle_coordinates(axle_gaps_mm: Iterable[float]) -> tuple[float,...]:
    xs = [0.0]
    for g in axle_gaps_mm:
        xs.append(xs[-1]+_number(g,"axle gap mm"))
    return tuple(xs)


def bridge_axles(vehicle: str, *, tonne_force_N: float = TONNE_FORCE_N) -> tuple[dict[str,float],...]:
    """All axles in one bridge vehicle/train; x measured from first axle."""
    scale = _number(tonne_force_N,"N per tonne-force")
    if vehicle in ("A","B"):
        data = PROVISIONS[f"6.{vehicle}_train"].data
    elif vehicle == "70R_WHEELED":
        data = PROVISIONS["6.70R_wheeled"].data
    elif vehicle == "AA_WHEELED":
        data = PROVISIONS["6.AA"].data["wheeled"]
    elif vehicle == "SV":
        data = PROVISIONS["6.SV"].data
        loads = data["prime_mover_axles_tonnes"]+(data["trailer_axle_tonnes"],)*20
        gaps = data["prime_mover_gaps_mm"]+(data["rear_prime_to_first_trailer_mm"],)+(1500,)*19
        return tuple({"x_mm":x,"load_N":t*scale,"load_tonnes":t} for x,t in zip(axle_coordinates(gaps),loads))
    else:
        raise ValueError("Use A, B, 70R_WHEELED, AA_WHEELED or SV")
    return tuple({"x_mm":x,"load_N":t*scale,"load_tonnes":t}
                 for x,t in zip(axle_coordinates(data["axle_gaps_mm"]),data["axle_loads_tonnes"]))


def bridge_patches(vehicle: str, *, tyre_pattern: str | None = None,
                   tyre_pressure_MPa: float | None = None,
                   aa_wheel_offsets_y_mm: Iterable[float] | None = None,
                   tonne_force_N: float = TONNE_FORCE_N) -> tuple[Patch,...]:
    """Generate one bridge train/vehicle, without impact or partial load factors.

    A/B: one equivalent contact on each side of each axle, Tables2/4.
    70R_WHEELED: choose L/M/N. Rectangular tread contact length derived from
    load/pressure; width follows Annex A tread deduction. Equal tyre sharing
    is an explicit symmetric-load assumption, not a new source table.
    SV_TRAILER: only 20 trailer axles, at their actual x positions relative to
    the prime-mover first axle. Full SV tyre geometry is not given for the
    prime mover; use bridge_axles('SV') plus project contact data for it.
    """
    scale = _number(tonne_force_N,"N per tonne-force")
    patches: list[Patch] = []
    if vehicle in ("A","B"):
        d = PROVISIONS[f"6.{vehicle}_train"].data
        for a in bridge_axles(vehicle,tonne_force_N=scale):
            length,width = d["contact_B_longitudinal_W_transverse_mm"][a["load_tonnes"]]
            for y in (-900,900):
                patches.append(Patch(a["x_mm"],y,a["load_N"]/2,"rectangle",length,width,label=f"Class {vehicle}"))
    elif vehicle in ("70R_TRACKED","AA_TRACKED"):
        d = PROVISIONS["6.70R_tracked"].data if vehicle == "70R_TRACKED" else PROVISIONS["6.AA"].data["tracked"]
        gap = d.get("derived_track_centre_spacing_mm",d.get("derived_centre_spacing_mm"))
        for y in (-gap/2,gap/2):
            patches.append(Patch(d["track_length_mm"]/2,y,35*scale,"rectangle",d["track_length_mm"],d["track_width_mm"],label=vehicle))
    elif vehicle == "AA_WHEELED":
        d = PROVISIONS["6.AA"].data["wheeled"]
        if aa_wheel_offsets_y_mm is None:
            raise ValueError("Supply four verified aa_wheel_offsets_y_mm: the supplied "
                             "low-resolution AA transverse dimension chains are ambiguous")
        ys = tuple(aa_wheel_offsets_y_mm)
        if len(ys) != 4 or any(isinstance(y,bool) or not isinstance(y,(int,float)) or not isfinite(y) for y in ys):
            raise ValueError("Supply four finite transverse wheel centres, left to right")
        if any(b-a < 300 for a,b in zip(ys,ys[1:])):
            raise ValueError("AA contact centres must be ordered and contacts must not overlap")
        for a in bridge_axles(vehicle,tonne_force_N=scale):
            for y,t in zip(ys,d["tyre_loads_each_axle_tonnes"]):
                patches.append(Patch(a["x_mm"],y,t*scale,"rectangle",150,300,label=vehicle))
    elif vehicle == "70R_WHEELED":
        d = PROVISIONS["6.70R_wheeled"].data
        if tyre_pattern not in d["tyre_patterns"]:
            raise ValueError("Select tyre_pattern='L', 'M' or 'N'; all are separate cases")
        pattern = d["tyre_patterns"][tyre_pattern]
        maxp = d["max_tyre_pressure_kgf_cm2"]*KGF_CM2_TO_MPA
        p = maxp if tyre_pressure_MPa is None else _number(tyre_pressure_MPa,"tyre pressure")
        if p > maxp+1e-12:
            raise ValueError("70R tyre pressure exceeds the Fig.1 maximum")
        width = pattern["tyre_width_mm"]-(25 if pattern["tyre_width_mm"] <= 225 else 50)
        ys = pattern["wheel_centres_y_mm"]
        for a in bridge_axles(vehicle,tonne_force_N=scale):
            force = a["load_N"]/len(ys)
            for y in ys:
                patches.append(Patch(a["x_mm"],y,force,"rectangle",force/(p*width),width,label=f"70R {tyre_pattern}"))
    elif vehicle == "SV_TRAILER":
        d = PROVISIONS["6.SV"].data
        for a in bridge_axles("SV",tonne_force_N=scale)[3:]:
            for y in d["derived_trailer_tyre_centres_y_mm"]:
                patches.append(Patch(a["x_mm"],y,2.25*scale,"rectangle",274,156,label="SV trailer"))
    elif vehicle == "SV":
        raise ValueError("Full SV has 23 axles; Fig.6A lacks prime-mover tyre contacts. "
                         "Use bridge_axles('SV'), bridge_patches('SV_TRAILER'), and explicit project prime-mover contacts.")
    else:
        raise ValueError("Unsupported bridge vehicle")
    return tuple(patches)


def translate_patches(patches: Iterable[Patch], *, dx_mm: float = 0,
                      dy_mm: float = 0, reverse: bool = False) -> tuple[Patch,...]:
    """Coordinate operation for a solver's moving-load sweep; does not find maximum stress."""
    s = -1 if reverse else 1
    return tuple(replace(p,x_mm=s*p.x_mm+dx_mm,y_mm=p.y_mm+dy_mm) for p in patches)


def class_AB_passing_clearance(carriageway_mm: float, vehicle: str = "A") -> float:
    """6 Tables3/5: kerb 150mm separately; result minimum passing gap mm."""
    w = _number(carriageway_mm,"carriageway width")
    if vehicle not in ("A","B"):
        raise ValueError("vehicle must be A or B")
    d = PROVISIONS["6.A_B_clearances"].data[vehicle]
    start,end = d["two_train_width_start_mm"],d["full_gap_width_mm"]
    if w < start:
        raise ValueError("Carriageway too narrow for two trains")
    return min(1200.0,400+w-start)


def lane_load_cases(carriageway_mm: float) -> tuple[dict[str,Any],...]:
    """6 Tables6/6A; vehicle sequences from left to right and mirrored cases.

    Each H occupies TWO design lanes; H may be 70R/AA as in the table note.
    Widths are bounds for applicability, not automatically placed wheel y's.
    These are maximum-occupancy patterns; also investigate fewer vehicles
    if they cause a worse response (e.g. torsion).
    """
    w = _number(carriageway_mm,"carriageway width")
    # (minimum CW, maximum CW exclusive, sequence); transcription of Table6A.
    cases = (
        (4250,5300,("A",)), (5300,9600,("H",)), (5300,9600,("A","A")),
        (9600,13100,("A",)*3), (9700,13100,("A","H")),
        (13100,16600,("A",)*4), (13200,16600,("A","A","H")),
        (14500,16600,("H","H")),
        (16600,20100,("A",)*5), (16700,20100,("A","A","A","H")),
        (16800,20100,("H","A","H")), (16700,20100,("A","H","H")),
        (20100,23600,("A",)*6), (20200,23600,("A","A","A","A","H")),
        (20200,23600,("A","A","H","H")),(20300,23600,("H","A","A","H")),
    )
    if not 4250 <= w < 23600:
        raise ValueError("Table6A illustrated CW range is 4250<=width<23600 mm; no extrapolation")
    result = []
    for lo,hi,seq in cases:
        if lo <= w < hi:
            for s in dict.fromkeys((seq,tuple(reversed(seq)))):
                result.append({"vehicles_left_to_right":s,"minimum_CW_mm":lo,
                    "single_lane_extra_mass_kg_m2":500 if len(s)==1 and s[0]=="A" else 0,
                    "single_lane_A_occupied_width_mm":2300 if len(s)==1 and s[0]=="A" else None,
                    "source":PROVISIONS["6.lane_combinations"].source})
    return tuple(result)

# ---------------------- FEA-facing adapters and checks ----------------------
@dataclass(frozen=True)
class Material:
    name: str
    E_MPa: float
    nu: float
    source: Source | None = None
    alpha_per_C: float | None = None

    def __post_init__(self) -> None:
        _number(self.E_MPa,"E MPa")
        if isinstance(self.nu,bool) or not isinstance(self.nu,(int,float)) or not isfinite(self.nu) or not -1 < self.nu < 0.5:
            raise ValueError("Isotropic nu must satisfy -1 < nu < 0.5")
        if self.alpha_per_C is not None:
            _number(self.alpha_per_C,"thermal expansion coefficient",zero=True)

    def to_SI(self) -> dict[str,Any]:
        return {"name":self.name,"E_Pa":self.E_MPa*1e6,"nu":self.nu,
                "alpha_per_C":self.alpha_per_C,"source":self.source}


@dataclass(frozen=True)
class Layer:
    name: str
    material: Material
    thickness_mm: float | None
    structural: bool = True

    def __post_init__(self) -> None:
        if self.thickness_mm is not None:
            _number(self.thickness_mm,"layer thickness")

    def to_SI(self) -> dict[str,Any]:
        return {"name":self.name,"material":self.material.to_SI(),
                "thickness_m":None if self.thickness_mm is None else self.thickness_mm/1000,
                "structural":self.structural}


def irc_material(name: str, *, E_MPa: float | None = None,
                 cbr_percent: float | None = None,
                 combined_granular_thickness_mm: float | None = None,
                 support_modulus_MPa: float | None = None) -> Material:
    """Named, conditional source presets. Project test inputs remain explicit.

    For bituminous entries E_MPa is REQUIRED (measured or explicitly selected
    trial modulus); the prescribed 35 C cap is applied. No density or moisture
    expansion constant is invented. For arbitrary project materials construct
    Material(name,E_MPa,nu) directly.
    """
    if name == "PQC":
        d = PROVISIONS["58.pqc_elastic"].data
        return Material(name,d["E_MPa"] if E_MPa is None else E_MPa,d["nu"],
                        PROVISIONS["58.pqc_elastic"].source,PROVISIONS["58.pqc_alpha"].data)
    if name == "SUBGRADE":
        if cbr_percent is None:
            raise ValueError("Supply design CBR percent")
        return Material(name,subgrade_resilient_modulus(cbr_percent),0.35,PROVISIONS["37.subgrade_MR"].source)
    if name == "UNBOUND_GRANULAR":
        if combined_granular_thickness_mm is None or support_modulus_MPa is None:
            raise ValueError("Supply combined granular thickness and support modulus")
        return Material(name,granular_resilient_modulus(combined_granular_thickness_mm,support_modulus_MPa),
                        0.35,PROVISIONS["37.gsb"].source)
    d = PROVISIONS["37.materials"].data
    if name not in d:
        raise ValueError(f"Unknown preset: {name}; supply project E and nu using Material")
    row = d[name]
    if name.startswith("BITUMINOUS"):
        if E_MPa is None:
            raise ValueError("Supply measured or explicitly selected trial E_MPa; table value is a cap")
        modulus = min(row["E_MPa"],_number(E_MPa,"bituminous E"))
    else:
        modulus = row["E_MPa"] if E_MPa is None else _number(E_MPa,"project modulus")
    return Material(name,modulus,row["nu"],PROVISIONS["37.materials"].source)


def catalogue_layers(category: str, effective_cbr_percent: float, traffic_msa: float,
                      *, bituminous_E_MPa: float) -> tuple[Layer,...]:
    """Convert an exact trial profile to the combined-layer IRC:37 analysis form.

    Caller selects bottom DBM modulus; normal 35 C VG30/VG40 cap applied.
    Adjacent WMM+GSB combine as required by 7.2.3; SAMI is excluded. This is
    a layered elastic input stack, not proof that a plate solver represents it.
    """
    prof = catalogue_profile(category,effective_cbr_percent,traffic_msa)
    rows = list(prof["layers_mm"])
    subgrade = irc_material("SUBGRADE",cbr_percent=effective_cbr_percent)
    cap = 2000 if traffic_msa < 20 else 3000
    e = min(cap,_number(bituminous_E_MPa,"selected bottom DBM modulus"))
    material = Material("combined structural bituminous",e,0.35,PROVISIONS["37.bituminous_modulus"].source)
    bit_h = sum(h for name,h in rows if name in ("surface","binder"))
    result = [Layer("bituminous",material,bit_h)]
    below = [(name,h) for name,h in rows if name not in ("surface","binder")]
    if category == "a":
        h = sum(t for _,t in below)
        m = irc_material("UNBOUND_GRANULAR",combined_granular_thickness_mm=h,support_modulus_MPa=subgrade.E_MPa)
        result.append(Layer("unbound_base+GSB",m,h))
    else:
        for name,h in below:
            if name == "GSB":
                m = irc_material("UNBOUND_GRANULAR",combined_granular_thickness_mm=h,support_modulus_MPa=subgrade.E_MPa)
            elif name == "WMM":
                m = irc_material("CRUSHED_ROCK_ON_CTSB")
            else:
                key = {"CTB":"CTB","CTSB":"CTSB","stabilised_RAP":"STABILISED_RAP",
                       "granular_crack_relief":"GRANULAR_CRACK_RELIEF"}[name]
                m = irc_material(key)
            result.append(Layer("unbound_base" if name == "WMM" else name,m,h))
    result.append(Layer("subgrade",subgrade,None))
    return tuple(result)


def critical_locations(layers: Iterable[Layer]) -> tuple[dict[str,Any],...]:
    """37 3.3/Figs3.1-3.6: depths measured from pavement surface.

    Query the one-sided material limits at interfaces. A plate solver's w alone
    cannot provide the required through-depth horizontal and vertical strains.
    """
    result = []
    z = 0.0
    for layer in layers:
        if not layer.structural:
            continue
        if layer.name == "subgrade":
            result.append({"layer":layer.name,"depth_mm":z,"side":"just_inside_subgrade",
                           "response":"vertical compressive strain"})
            break
        if layer.thickness_mm is None:
            raise ValueError("Only final subgrade may have semi-infinite thickness")
        z += layer.thickness_mm
        if layer.name == "bituminous":
            result.append({"layer":layer.name,"depth_mm":z,"side":"just_above_interface",
                           "response":"horizontal tensile strain"})
        if layer.name == "CTB":
            result.append({"layer":layer.name,"depth_mm":z,"side":"just_above_interface",
                           "response":"horizontal tensile stress and strain"})
    return tuple(result)


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # pass / fail / needs_input
    message: str
    source: Source


def _check(name: str, ok: bool, message: str, key: str) -> Check:
    return Check(name,"pass" if ok else "fail",message,PROVISIONS[key].source)


def check_dlc(*, thickness_mm: float, cube_strengths_7d_MPa: Iterable[float],
              major_highway: bool = True, bonded_to_pqc: bool = False,
              cement_type: str | None = None, aggregate_cement_ratio: float | None = None,
              cementitious_kg_m3: float | None = None,
              subgrade_density_percent_MDD: float | None = None) -> tuple[Check,...]:
    """49/58 checks only for supplied inputs; no E is inferred from cube strength."""
    h = _number(thickness_mm,"DLC thickness")
    values = tuple(_number(x,"cube strength",zero=True) for x in cube_strengths_7d_MPa)
    if len(values) != 5:
        raise ValueError("Supply one consecutive group of exactly five 7-day cubes")
    minimum = 150 if major_highway else 100
    results = [
        _check("DLC thickness",h>=minimum,f"{h:g} mm; required >= {minimum} mm","49.geometry"),
        _check("DLC mean cube strength",sum(values)/5>=7,"5-cube mean at 7d must be >=7 MPa","49.strength"),
        _check("DLC individual cube strength",min(values)>=5.5,"Every 7d cube must be >=5.5 MPa","49.strength")]
    if bonded_to_pqc:
        results.append(_check("bonded DLC strength",sum(values)/5>=10,
                              "Bonded PQC-DLC requires 7-day DLC strength >=10 MPa","58.dlc"))
    if cementitious_kg_m3 is not None:
        results.append(_check("DLC cementitious content",_number(cementitious_kg_m3,"cementitious content")>=140,
                              "Cementitious material >=140 kg/m3","49.mix"))
    if aggregate_cement_ratio is not None:
        if cement_type not in ("OPC","PPC","PSC"):
            raise ValueError("Supply OPC/PPC/PSC for the ratio check")
        limit = 14 if cement_type == "OPC" else 12
        results.append(_check("DLC aggregate:cement ratio",_number(aggregate_cement_ratio,"ratio")<=limit,
                              f"Aggregate:cement <={limit}:1","49.mix"))
    if subgrade_density_percent_MDD is not None:
        results.append(_check("subgrade compaction",_number(subgrade_density_percent_MDD,"compaction")>=97,
                              "Subgrade >=97% modified Proctor MDD","49.subgrade"))
    return tuple(results)


def check_pqc(*, flexural_strength_28d_MPa: float, water_cementitious_ratio: float,
              cement_content_kg_m3: float | None = None) -> tuple[Check,...]:
    results = [
        _check("PQC flexural strength",_number(flexural_strength_28d_MPa,"flexural strength")>=4.5,
               "28-day flexural strength >=4.5 MPa","58.pqc_strength"),
        _check("PQC free water/CM",_number(water_cementitious_ratio,"water/CM")<=0.40,
               "Free water/cementitious ratio <=0.40","15.mix")]
    if cement_content_kg_m3 is not None:
        results.append(_check("PQC standard cement content",_number(cement_content_kg_m3,"cement content")>=360,
                              "General minimum 360 kg/m3; site-blended flyash/GGBFS exceptions need separate checks","15.mix"))
    return tuple(results)


def check_wbm(*, role: str, grading: int, compacted_lift_mm: float,
              la_percent: float | None = None, aiv_percent: float | None = None,
              flakiness_percent: float | None = None,
              flakiness_applicable: bool = True,
              directly_on_silty_clayey_soil: bool = False) -> tuple[Check,...]:
    """19 Tables1/2. LA OR AIV; each lift is distinct from total base thickness."""
    if role not in ("subbase","base","surfacing") or grading not in (1,2,3):
        raise ValueError("Invalid WBM role or grading")
    spec = PROVISIONS["19.physical"].data[role]
    grade = PROVISIONS["19.aggregate_grading"].data[grading]
    h = _number(compacted_lift_mm,"compacted lift")
    results = [
        _check("WBM role",role in grade["roles"],"Grading 1 is restricted to subbase","19.aggregate_grading"),
        _check("WBM lift thickness",h==grade["compacted_lift_mm"],
               f"Table2 nominal compacted lift {grade['compacted_lift_mm']} mm","19.aggregate_grading"),
        _check("WBM support",not directly_on_silty_clayey_soil,
               "Provide granular intervention over silty/clayey subgrade","19.description")]
    supplied = []
    if la_percent is not None:
        supplied.append(_number(la_percent,"LA percent",zero=True)<=spec["LA_max_percent"])
    if aiv_percent is not None:
        supplied.append(_number(aiv_percent,"AIV percent",zero=True)<=spec["AIV_max_percent"])
    results.append(_check("WBM abrasion or impact",any(supplied),"Either LA or AIV may satisfy Table1","19.physical")
                   if supplied else Check("WBM abrasion or impact","needs_input","Supply LA or AIV result",PROVISIONS["19.physical"].source))
    limit = spec["flakiness_max_percent"]
    if limit is not None and flakiness_applicable:
        results.append(Check("WBM flakiness","needs_input","Supply flakiness result",PROVISIONS["19.physical"].source)
                       if flakiness_percent is None else _check("WBM flakiness",_number(flakiness_percent,"flakiness",zero=True)<=limit,
                                                                             f"Flakiness <= {limit}%","19.physical"))
    return tuple(results)


def check_flexible_stack(layers: Iterable[Layer], *, category: str) -> tuple[Check,...]:
    """Minimum structural checks only; no fatigue/rutting approval is implied."""
    stack = tuple(layers)
    if category not in FLEXIBLE_CATEGORIES:
        raise ValueError("category must be a-f")
    results = []
    names = tuple(l.name for l in stack if l.structural)
    expected = tuple(n for n in FLEXIBLE_CATEGORIES[category] if n != "SAMI")
    if category == "a" and "unbound_base+GSB" in names:
        expected = ("bituminous","unbound_base+GSB","subgrade")
    results.append(_check("flexible layer arrangement",names==expected,
                          f"Expected top-down: {expected}","37.categories"))
    for i,layer in enumerate(stack):
        if not layer.structural:
            continue
        if layer.name == "subgrade":
            results.append(_check("semi-infinite subgrade",i==len(stack)-1 and layer.thickness_mm is None,
                                  "Subgrade final and semi-infinite for IRC:37 analysis","37.analysis"))
            continue
        if layer.thickness_mm is None:
            results.append(_check("finite upper layer",False,f"{layer.name} requires finite thickness","37.analysis"))
            continue
        minima = {"CTSB":(200,"37.ctsb"),"CTB":(100,"37.ctb"),
                  "stabilised_RAP":(100,"37.rap"),"unbound_base":(150,"37.unbound_base"),
                  "granular_crack_relief":(100,"37.crack_relief"),"GSB":(150,"37.gsb")}
        if layer.name in minima:
            minimum,key = minima[layer.name]
            results.append(_check(layer.name+" thickness",layer.thickness_mm>=minimum,
                                  f"{layer.name}: >= {minimum} mm","37.crack_relief" if layer.name=="granular_crack_relief" else key))
    results.append(Check("site design checks","needs_input",
                         "Evaluate site-specific critical strains/stresses and performance; trial stack is not a completed design",
                         PROVISIONS["37.analysis"].source))
    return tuple(results)


def check_patch_domain(patches: Iterable[Patch], *, length_mm: float, width_mm: float,
                       lateral_edge_clearance_mm: float = 0,
                       allow_longitudinal_overhang: bool = False) -> bool:
    """Check whole contact footprints against a rectangular [0,L]x[0,W] domain.

    Overhanging moving loads need intersection integration by the solver.
    Do not rescale a partly clipped patch to recover its original full force.
    """
    length,width = _number(length_mm,"domain length"),_number(width_mm,"domain width")
    c = _number(lateral_edge_clearance_mm,"edge clearance",zero=True)
    patches = tuple(patches)
    if not patches:
        raise ValueError("At least one patch is required")
    for p in patches:
        x0,y0,x1,y1 = p.bounds_mm
        if y0 < c or y1 > width-c:
            return False
        if not allow_longitudinal_overhang and (x0 < 0 or x1 > length):
            return False
    return True


def combine_sv_contacts(prime_mover_contacts: Iterable[Patch], *,
                        eccentricity_mm: float = 0,
                        tonne_force_N: float = TONNE_FORCE_N) -> tuple[Patch,...]:
    """Complete SV only with explicit project prime-mover tyre contacts.

    Provide contacts in the unshifted SV frame; x must match the three prime
    axle stations, y is about the vehicle centreline. Per-axle resultants are
    checked against 6/9.5/9.5 tonnes, then the complete set is shifted by e.
    """
    if isinstance(eccentricity_mm,bool) or not isfinite(eccentricity_mm) or abs(eccentricity_mm)>300:
        raise ValueError("SV eccentricity must be within +/-300 mm")
    contacts = tuple(prime_mover_contacts)
    axles = bridge_axles("SV",tonne_force_N=tonne_force_N)[:3]
    totals = {a["x_mm"]:0.0 for a in axles}
    for p in contacts:
        if p.x_mm not in totals:
            raise ValueError("Prime-mover contacts must use x stations 0,3200,4570 mm")
        totals[p.x_mm] += p.force_N
    for a in axles:
        if abs(totals[a["x_mm"]]-a["load_N"])>1e-8*max(1,a["load_N"]):
            raise ValueError("Prime-mover per-axle tyre resultant does not match Fig.6")
    return translate_patches(contacts+bridge_patches("SV_TRAILER",tonne_force_N=tonne_force_N),dy_mm=eccentricity_mm)


def summary() -> dict[str,Any]:
    return {"version":__version__,"sources":tuple(SOURCE_FILES),
            "provisions":len(PROVISIONS),"catalogue_figures":len(CATALOGUES),
            "exact_catalogue_sections":len(CATALOGUES)*len(_TRAFFIC_POINTS),
            "native_units":"N, mm, MPa, k MPa/m, delta T C",
            "solver_exports":"N, m, Pa, k N/m^3",
            "scope":"input data, checks and load geometry; no automatic design certification"}


def grading_envelope(key: str, grade: str | int | None = None,
                     *, sand: str = "crushed_sand") -> dict[float,Any]:
    """Select raw grading limits. None/dash means unspecified, never zero.

    Supported keys: 49.materials, 15.dlc_grading, 15.fine_grading,
    15.pqc_grading, 15.gsb_grading, 19.aggregate_grading, 19.screenings.
    """
    d = get(key).data
    if key == "49.materials":
        return d["aggregate_grading_mm_to_percent"]
    if key == "15.dlc_grading":
        return d
    if key == "19.aggregate_grading":
        return d[grade]["sieves"]
    if key == "19.screenings":
        if grade not in ("A","B"):
            raise ValueError("Screening grade must be A or B")
        return d[grade]
    if key in ("15.fine_grading","15.pqc_grading","15.gsb_grading"):
        if grade not in d or grade in ("sieves_mm",):
            raise ValueError("Select a valid table grading")
        result = dict(zip(d["sieves_mm"],d[grade]))
        if key == "15.pqc_grading":
            if sand not in d["wet_75um_max_percent"]:
                raise ValueError("sand must be crushed_sand or natural_sand")
            result[0.075] = (0,d["wet_75um_max_percent"][sand])
        return result
    raise ValueError("This provision is not a supported grading table")


def check_grading(key: str, measured_percent_passing: Mapping[float,float],
                  grade: str | int | None = None, *, sand: str = "crushed_sand") -> tuple[Check,...]:
    """Compare all specified sieves with RAW table limits; absent tests need input.

    For IRC:15 fine sand, special permitted tolerances and crushed-sand
    exceptions need project review: a raw-envelope fail is not automatically
    a final material rejection. Extra measured sieves do not create limits.
    """
    limits = grading_envelope(key,grade,sand=sand)
    results = []
    for sieve,bounds in limits.items():
        if bounds is None:
            continue
        name = f"{sieve:g} mm percent passing"
        if sieve not in measured_percent_passing:
            results.append(Check(name,"needs_input","No sieve result supplied",PROVISIONS[key].source))
            continue
        value = _number(measured_percent_passing[sieve],name,zero=True)
        if value > 100:
            raise ValueError("Percent passing cannot exceed 100")
        ok = value < float(bounds[1:]) if isinstance(bounds,str) and bounds.startswith("<") else bounds[0] <= value <= bounds[1]
        results.append(_check(name,ok,f"Measured {value:g}%; raw table limit {bounds}",key))
    return tuple(results)


def dlc_qc_plan(daily_area_m2: float) -> dict[str,int]:
    """SP:49 7.10: daily area or part thereof; sample count, not cube count."""
    area = _number(daily_area_m2,"daily DLC area",zero=True)
    return {"strength_samples":3*ceil(area/1000),"density_coverage_units_of_2000m2":ceil(area/2000)}


def tie_bar_options(slab_thickness_mm: float, *, deformed: bool = True) -> tuple[dict[str,int],...]:
    """15 Table8; exact slab rows only, for the stated 3.5m lane."""
    h = _number(slab_thickness_mm,"slab thickness")
    rows = [row for row in _TIE if row[0]==h]
    if not rows:
        raise ValueError("Use a tabulated slab thickness; no automatic tie-bar interpolation")
    return tuple({"diameter_mm":r[1],"max_spacing_mm":r[3 if deformed else 2],
                  "min_length_mm":r[5 if deformed else 4]} for r in rows)


def check_dowel(*, slab_thickness_mm: float, bar_length_mm: float,
                bar_depth_from_top_mm: float, horizontal_rotation_mm: float = 0,
                vertical_rotation_mm: float = 0, longitudinal_shift_mm: float = 0) -> tuple[Check,...]:
    """15 8.3.7-8.3.8; diameter, spacing and connection stiffness still need design."""
    h = _number(slab_thickness_mm,"slab thickness")
    length = _number(bar_length_mm,"dowel length")
    depth = _number(bar_depth_from_top_mm,"dowel depth")
    offsets = (horizontal_rotation_mm,vertical_rotation_mm,longitudinal_shift_mm)
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) for x in offsets):
        raise ValueError("Dowel alignment offsets must be finite numbers")
    return (
        _check("dowel length",length>=500,"Minimum 500 mm","15.dowels"),
        _check("dowel depth",0<depth<h and abs(depth-h/2)<=25,"Mid-depth +/-25 mm","15.dowels"),
        _check("horizontal rotational alignment",abs(horizontal_rotation_mm)<=10,"Absolute offset <=10 mm","15.dowels"),
        _check("vertical rotational alignment",abs(vertical_rotation_mm)<=10,"Absolute offset <=10 mm","15.dowels"),
        _check("longitudinal shift",abs(longitudinal_shift_mm)<=50,"Absolute shift <=50 mm","15.dowels"))


FUNCTION_SOURCES = {
    "rigid_cbr_to_k":("58.cbr_k","15.cbr_k"),
    "rigid_temperature_delta":("58.temperature",),"rigid_top_down_eligible":("58.spacing",),
    "winkler_k_from_plate":("58.winkler",),"subgrade_resilient_modulus":("37.subgrade_MR","37.effective_subgrade"),
    "effective_subgrade_modulus":("37.effective_subgrade",),"granular_resilient_modulus":("37.gsb",),
    "cemented_intact_modulus":("37.ctsb","37.ctb"),"ctb_flexural_strength":("37.ctb_flexural",),
    "bituminous_modulus":("37.bituminous_modulus",),"axle_equivalence":("37.vdf",),
    "vehicle_damage_factor":("37.vdf",),"axle_survey_minimum":("37.survey",),
    "indicative_vdf":("37.indicative_vdf",),"effective_k15":("15.effective_k_granular","15.effective_k_dlc"),
    "flexible_standard_patches":("37.standard_load",),"rigid_axle_group_patches":("58.axles","58.spacing"),
    "bridge_axles":("6.A_train","6.B_train","6.70R_wheeled","6.AA","6.SV"),
    "bridge_patches":("6.A_train","6.B_train","6.70R_wheeled","6.70R_tracked","6.AA","6.SV"),
    "lane_load_cases":("6.lane_combinations",),"class_AB_passing_clearance":("6.A_B_clearances",),
    "critical_locations":("37.analysis",),"combine_sv_contacts":("6.SV",),
    "dlc_qc_plan":("49.qc",),"tie_bar_options":("15.tie_bars",),"check_dowel":("15.dowels",),
}


def _self_test() -> None:
    """Numerical regressions for units, formulas, source tables and load resultants."""
    assert rigid_cbr_to_k(10) == 55
    assert rigid_temperature_delta("IV",300) == 21
    assert rigid_temperature_delta("IV",300,period="night") == -10.5
    assert subgrade_resilient_modulus(5) == 50
    assert subgrade_resilient_modulus(100) == 100
    assert abs(granular_resilient_modulus(450,50)-0.2*450**0.45*50)<1e-9
    assert effective_k15(55,150,"DLC") == 300
    assert effective_k15(55,150,"DLC",raw=True) == 417
    assert effective_k15(48,100,"DLC") == 208
    assert axle_equivalence(80,"single_dual") == 1
    assert axle_equivalence(148,"tandem_dual") == 1
    assert axle_survey_minimum(3000) == 600
    assert axle_survey_minimum(6001) == 900
    assert ctb_flexural_strength(10,"soil_cement") == 0.7
    assert catalogue_profile("a",5,10)["layers_mm"] == (("surface",40),("binder",80),("WMM",250),("GSB",200))
    assert len(CATALOGUES) == 48 and all(len(d["traffic_to_layers_mm"])==6 for d in CATALOGUES.values())
    for p in flexible_standard_patches():
        assert abs(p.pressure_MPa-0.56)<1e-12 and abs(p.force_N-20000)<1e-8
    for name,total in (("A",55.4),("B",33.2),("70R_TRACKED",70),("AA_TRACKED",70),("SV_TRAILER",360)):
        assert abs(sum(p.force_N for p in bridge_patches(name))/TONNE_FORCE_N-total)<1e-9
    for pattern in ("L","M","N"):
        patches = bridge_patches("70R_WHEELED",tyre_pattern=pattern)
        assert abs(sum(p.force_N for p in patches)/TONNE_FORCE_N-100)<1e-9
        assert all(abs(p.pressure_MPa-5.273*KGF_CM2_TO_MPA)<1e-12 for p in patches)
    assert abs(sum(a["load_N"] for a in bridge_axles("SV"))/TONNE_FORCE_N-385)<1e-9
    assert len(bridge_axles("SV")) == 23
    assert any(c["vehicles_left_to_right"]==("A","H") for c in lane_load_cases(9700))
    assert not any("H" in c["vehicles_left_to_right"] for c in lane_load_cases(9600))
    checks = check_wbm(role="base",grading=2,compacted_lift_mm=75,la_percent=45,aiv_percent=25,flakiness_percent=15)
    assert all(c.status=="pass" for c in checks)
    assert Material("sample",30000,0.15).to_SI()["E_Pa"] == 30e9
    assert k_to_SI(55) == 55e6
    assert all(c.status != "fail" for c in check_flexible_stack(catalogue_layers("b",5,30,bituminous_E_MPa=3000),category="b"))
    for fn in (lambda:rigid_cbr_to_k(1),lambda:effective_k15(62,150,"DLC"),
               lambda:catalogue_profile("a",5,12),lambda:bridge_patches("SV"),
               lambda:Material("bad",0,0.35)):
        try:
            fn()
        except (ValueError,TypeError):
            pass
        else:
            raise AssertionError("Expected input rejection")


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true",help="run numerical regression checks")
    parser.add_argument("--summary",action="store_true",help="print source and coverage summary")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        print("IRC library self-tests passed")
    if args.summary or not args.self_test:
        print(json.dumps(summary(),indent=2))
