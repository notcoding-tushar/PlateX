"""Translate vendored IRC footprints and provisions into SI workbench contracts."""

from ..schemas import (
    AnalysisConfig,
    CatalogueOptions,
    Citation,
    ContactPatch,
    DepthPoint,
    ElasticLayer,
    FoundationConfig,
    IRCCheck,
    IRCClimateOptions,
    IRCClimateRequest,
    IRCClimateResult,
    IRCClimateZone,
    IRCComplianceRequest,
    IRCComplianceResult,
    IRCFlexibleRequest,
    IRCFoundationLookup,
    IRCOption,
    IRCPlacement,
    IRCPrepared,
    IRCPreview,
    IRCRigidRequest,
    LayeredElasticRequest,
    LayeredElasticResult,
    LayerProperty,
    QueryPoint,
    VehicleLoad,
)
from ..solver import solve_sweep
from . import irc_fea_library as irc
from .layered_elastic import solve_layered_elastic

# Menu identifiers select library operations. All numerical provisions stay in the vendor.
_CASES = {
    "dual": ("flexible", "Standard dual wheels", "37.standard_load"),
    "dual_ctb": ("flexible", "CTB fatigue dual wheels", "37.standard_load"),
    **{g: ("rigid", f"{g.title()} axle group", "58.axles") for g in ("single", "tandem", "tridem")},
    "A": ("bridge", "Class A train", "6.A_train"),
    "B": ("bridge", "Class B train", "6.B_train"),
    "70R_TRACKED": ("bridge", "70R tracked", "6.70R_tracked"),
    "70R_WHEELED": ("bridge", "70R wheeled", "6.70R_wheeled"),
    "AA_TRACKED": ("bridge", "Class AA tracked", "6.AA"),
    "AA_WHEELED": ("bridge", "Class AA wheeled", "6.AA"),
    "SV_TRAILER": ("bridge", "SV trailer", "6.SV"),
}


def options() -> list[IRCOption]:
    return [IRCOption(case=k, mode=m, label=l) for k, (m, l, _) in _CASES.items()]


def _citation(key):
    return Citation.model_validate(irc.get(key).source, from_attributes=True)


def climate_options() -> IRCClimateOptions:
    provision = irc.get("58.temperature")
    return IRCClimateOptions(
        zones=[IRCClimateZone(zone=zone, region=region)
               for zone, region in provision.data["regions"].items()],
        source=_citation("58.temperature"),
        notes=["Select the zone for the actual site: states may include multiple regions, hills or coastal areas.",
               "Table values are fallback maximum slab differentials; use site measurements where available."],
    )


def climate_temperature(req: IRCClimateRequest) -> IRCClimateResult:
    delta = irc.rigid_temperature_delta(req.zone, req.thickness_m * 1000,
                                        period=req.period, interpolate=req.interpolate)
    return IRCClimateResult(
        delta_T_K=delta, source=_citation("58.temperature"),
        notes=["Temperature is top minus bottom; the daytime profile is nonlinear and night is approximately -0.5 times day.",
               "A linear through-depth profile is an approximation and does not include permanent curl."],
    )


def _contact(patch):
    data = patch.to_SI()
    del data["pressure_Pa"]
    return ContactPatch(**data)


def _native_patch(patch):
    return irc.Patch(
        x_mm=patch.x_m * 1000, y_mm=patch.y_m * 1000, force_N=patch.force_N,
        shape=patch.shape, length_mm=patch.length_m * 1000 if patch.length_m else None,
        width_mm=patch.width_m * 1000 if patch.width_m else None,
        radius_mm=patch.radius_m * 1000 if patch.radius_m else None, label=patch.label,
    )


def _placement(req):
    if req.case not in _CASES:
        raise ValueError("Unknown IRC load case.")
    mode, _, key = _CASES[req.case]
    keys, notes = [key], []
    if mode == "flexible":
        patches = irc.flexible_standard_patches(ctb_fatigue=req.case == "dual_ctb")
        notes.append(
            "The pair represents one side of the standard axle. HOSNT12 uses a finite plane-stress plate; subgrade vertical strain requires a layered-elastic analysis."
        )
    elif mode == "rigid":
        patches = irc.rigid_axle_group_patches(
            req.group_load_kN,
            req.case,
            wheel_offsets_y_mm=[v * 1000 for v in req.wheel_offsets_m],
            axle_spacing_mm=req.spacing_m * 1000,
        )
        keys.append("58.spacing")
        notes.append(
            "Circular contacts share the group load equally. Verify tyre offsets against the project vehicle."
        )
    else:
        patches = irc.bridge_patches(
            req.case, tyre_pattern=req.tyre_pattern,
            aa_wheel_offsets_y_mm=req.aa_wheel_offsets_y_mm,
        )
        if req.prime_mover_contacts is not None:
            if req.case != "SV_TRAILER":
                raise ValueError("Prime-mover contacts are only applicable to SV_TRAILER.")
            patches = irc.combine_sv_contacts(
                [_native_patch(p) for p in req.prime_mover_contacts],
                eccentricity_mm=req.sv_eccentricity_mm,
            )
        elif req.sv_eccentricity_mm:
            raise ValueError("SV eccentricity requires explicit prime-mover contacts.")
        notes.append("Static vehicle contacts exclude impact and partial load factors.")
    placed = irc.translate_patches(patches, dx_mm=req.x_m * 1000, dy_mm=req.y_m * 1000)
    return placed, keys, notes


def preview_loads(req: IRCPlacement) -> IRCPreview:
    patches, keys, notes = _placement(req)
    contacts = [_contact(patch) for patch in patches]
    return IRCPreview(
        vehicle_load=VehicleLoad(patches=contacts),
        sources=[_citation(k) for k in keys],
        inside_plate=irc.check_patch_domain(patches, length_mm=req.a * 1000, width_mm=req.b * 1000),
        notes=notes,
    )


def check(req: IRCPlacement) -> list[IRCCheck]:
    patches, keys, _ = _placement(req)
    mode = _CASES[req.case][0]
    length, width = req.a * 1000, req.b * 1000
    inside = irc.check_patch_domain(patches, length_mm=length, width_mm=width)
    checks = [
        IRCCheck(
            name="Footprint containment",
            status="pass" if inside else "fail",
            message="All footprints lie on the plate."
            if inside
            else "Overhanging pressure is clipped at the plate edge.",
            source=_citation(keys[0]),
        )
    ]
    if mode == "bridge" and req.case in ("A", "B", "70R_WHEELED", "70R_TRACKED"):
        key, field = (
            ("6.A_B_clearances", "kerb_min_mm")
            if req.case in ("A", "B")
            else ("6.positioning", "70R_kerb_clearance_mm")
        )
        gap = irc.get(key).data[field]
        ok = irc.check_patch_domain(
            patches,
            length_mm=length,
            width_mm=width,
            lateral_edge_clearance_mm=gap,
            allow_longitudinal_overhang=True,
        )
        checks.append(
            IRCCheck(
                name="Lateral kerb clearance",
                status="pass" if ok else "fail",
                message=f"Required clearance to each kerb: {gap:g} mm. Plate width represents carriageway width.",
                source=_citation(key),
            )
        )
    if mode == "rigid":
        if req.flexural_strength_MPa is None or req.water_cm is None:
            for key in ("58.pqc_strength", "15.mix"):
                checks.append(
                    IRCCheck(
                        name="PQC mix inputs",
                        status="needs_input",
                        message="Enter measured 28-day flexural strength and free water/cementitious ratio for the PQC checks.",
                        source=_citation(key),
                    )
                )
        else:
            for item in irc.check_pqc(
                flexural_strength_28d_MPa=req.flexural_strength_MPa, water_cementitious_ratio=req.water_cm
            ):
                checks.append(
                    IRCCheck(
                        name=item.name,
                        status=item.status,
                        message=item.message,
                        source=Citation.model_validate(item.source, from_attributes=True),
                    )
                )
    return checks


def prepare_rigid(req: IRCRigidRequest) -> IRCPrepared:
    if req.support == "effective" and (req.explicit_dlc or req.base_config.material_mode == "laminate"):
        raise ValueError("Effective subbase k requires a single slab; explicit layers would double-count support.")
    if req.raw and req.support == "effective":
        raise ValueError("Raw effective k is for audit only and cannot be used in an analysis.")
    if req.explicit_dlc and req.temperature_zone is not None:
        raise ValueError("IRC slab temperature differential cannot be applied across an explicit multi-layer stack; specify a project-specific through-depth profile instead.")
    soil_k = irc.rigid_cbr_to_k(req.cbr_percent, interpolate=req.interpolate, code=req.cbr_code)
    k = soil_k
    sources = [_citation("58.cbr_k" if req.cbr_code == "IRC:58-2015" else "15.cbr_k")]
    if req.support == "effective":
        if req.subbase_thickness_mm is None:
            raise ValueError("Supply subbase_thickness_mm for effective k.")
        k = irc.effective_k15(soil_k, req.subbase_thickness_mm, req.subbase,
                              interpolate=req.interpolate, raw=req.raw)
        sources.append(_citation("15.effective_k_dlc" if req.subbase == "DLC" else "15.effective_k_granular"))
    data = req.base_config.model_dump()
    if not req.explicit_dlc:
        material = irc.irc_material("PQC").to_SI()
        data.update(material_mode="isotropic", layers=None, E=material["E_Pa"],
                    nu=material["nu"], alpha=material["alpha_per_C"])
        sources.extend([_citation("58.pqc_elastic"), _citation("58.pqc_alpha")])
    elif req.base_config.material_mode != "laminate" or not req.base_config.layers:
        raise ValueError("Explicit DLC requires an explicitly supplied laminate stack.")
    data["foundation"] = FoundationConfig(Kw=irc.k_to_SI(k)).model_dump()
    notes = ["Foundation uses raw subgrade k." if req.support == "raw" else
             "Effective foundation k includes the selected subbase; no explicit subbase is modeled."]
    if req.temperature_zone is not None:
        delta = irc.rigid_temperature_delta(req.temperature_zone, req.base_config.h * 1000,
                                           period=req.temperature_period, interpolate=req.interpolate)
        data.update(t_coeffs=(0, delta, 0), thermal_distribution="uniform")
        sources.append(_citation("58.temperature"))
        notes.append("The through-depth linear profile is an approximation: IRC daytime profiles are nonlinear; night is approximately -0.5 times day. The table gives only the top-minus-bottom difference.")
    return IRCPrepared(config=AnalysisConfig.model_validate(data), sources=sources,
                       modeling_notes=notes, details={"subgrade_k_MPa_per_m": soil_k, "k_MPa_per_m": k})


def foundation_lookup(req: IRCFoundationLookup) -> dict:
    soil = irc.rigid_cbr_to_k(req.cbr_percent, interpolate=req.interpolate, code=req.cbr_code)
    effective = irc.effective_k15(soil, req.subbase_thickness_mm, req.subbase,
                                   interpolate=req.interpolate, raw=req.raw)
    return {"subgrade_k_MPa_per_m": soil, "effective_k_MPa_per_m": effective,
            "effective_k_N_per_m3": irc.k_to_SI(effective), "raw_audit_only": req.raw,
            "sources": [_citation("58.cbr_k" if req.cbr_code == "IRC:58-2015" else "15.cbr_k"),
                        _citation("15.effective_k_dlc" if req.subbase == "DLC" else "15.effective_k_granular")]}


def prepare_flexible(req: IRCFlexibleRequest) -> IRCPrepared:
    if any(abs(v) > 0 for coeffs in (req.base_config.t_coeffs, req.base_config.c_coeffs)
           for v in (coeffs or ())):
        raise ValueError("Clear thermal and moisture loading before preparing a flexible catalogue: layer expansion properties are not supplied by the catalogue.")
    profile = irc.catalogue_profile(req.category, req.cbr, req.traffic_msa)
    stack = irc.catalogue_layers(req.category, req.cbr, req.traffic_msa,
                                 bituminous_E_MPa=req.bituminous_E_MPa)
    heights = [layer.to_SI()["thickness_m"] or req.subgrade_thickness_m for layer in stack]
    h = sum(heights)
    top = h / 2
    layers = []
    for layer, thickness in zip(stack, heights):
        mat = layer.to_SI()["material"]
        e, nu = mat["E_Pa"], mat["nu"]
        shear = e / (2 * (1 + nu))
        layers.append(LayerProperty(h_bottom=top-thickness, h_top=top, E1=e, E2=e, E3=e,
                                    nu12=nu, nu23=nu, nu13=nu, G12=shear, G13=shear, G23=shear,
                                    alpha1=mat["alpha_per_C"] or 0, alpha2=mat["alpha_per_C"] or 0))
        top -= thickness
    locations = irc.critical_locations(stack)
    queries = [QueryPoint(label=f"{loc['layer']}: {loc['response']}", x_m=req.x_m, y_m=req.y_m,
                          z_m=h/2-loc["depth_mm"]/1000,
                          layer_side="below" if loc["side"] == "just_inside_subgrade" else "above")
               for loc in locations]
    patches = irc.translate_patches(irc.flexible_standard_patches(ctb_fatigue=req.ctb_fatigue),
                                    dx_mm=req.x_m*1000, dy_mm=req.y_m*1000)
    data = req.base_config.model_dump()
    data.update(h=h, material_mode="laminate", layers=[p.model_dump() for p in reversed(layers)],
                E=None, nu=None, q0=0, vehicle_load=VehicleLoad(patches=[_contact(p) for p in patches]).model_dump(),
                query_points=[q.model_dump() for q in queries])
    notes = ["HOSNT12 enforces eps_z = 0 on a finite plate; it does not replace semi-infinite layered-elastic Burmister subgrade strain checks. The subgrade thickness is a user-selected finite approximation."]
    source = Citation.model_validate(profile.pop("source"), from_attributes=True)
    return IRCPrepared(config=AnalysisConfig.model_validate(data), sources=[source, _citation("37.analysis"),
                       _citation("37.standard_load")], modeling_notes=notes,
                       details={"profile": profile, "critical_locations": locations})


def catalogue_options() -> CatalogueOptions:
    scope = irc.get("37.catalogue_scope").data
    return CatalogueOptions(categories=sorted(irc.FLEXIBLE_CATEGORIES),
                            cbr=scope["CBR_percent"], traffic_msa=scope["traffic_msa"])


def solve_flexible_layered(req: LayeredElasticRequest) -> LayeredElasticResult:
    profile = irc.catalogue_profile(req.category, req.cbr, req.traffic_msa)
    stack = irc.catalogue_layers(req.category, req.cbr, req.traffic_msa,
                                 bituminous_E_MPa=req.bituminous_E_MPa)
    checks = irc.check_flexible_stack(stack, category=req.category)
    layers = []
    for row in stack:
        si = row.to_SI()
        layers.append(ElasticLayer(name=row.name, thickness_m=si["thickness_m"],
                                   E_Pa=si["material"]["E_Pa"], nu=si["material"]["nu"]))
    standard = irc.flexible_standard_patches(ctb_fatigue=req.ctb_fatigue)
    ref = standard[0].to_SI()
    notes = ["Depth and displacement are positive down. Tensile stress and strain are positive.",
             "Radial components refer to the line from the wheel-set centre to the point, with +x at the centre.",
             "Interface responses are sampled at the stated positions. A spatial maximum and fatigue or rutting life require separate evaluation."]
    if req.wheels == "single" and req.spacing_m is not None:
        raise ValueError("Spacing applies to a dual pair only.")
    offsets = [0.]
    if req.wheels == "dual":
        spacing = req.spacing_m or abs(standard[1].y_mm-standard[0].y_mm)/1000
        offsets = [-spacing/2, spacing/2]
    if req.wheels == "single" or any(v is not None for v in (req.wheel_force_N, req.pressure_Pa, req.spacing_m)):
        notes.append("This wheel case is a user-selected variation of the IRC standard pair.")
    wheels = [_contact(irc.circular_patch(req.wheel_force_N or ref["force_N"],
                                          (req.pressure_Pa or ref["pressure_Pa"])/1e6,
                                          y_mm=y*1000, label=f"Wheel {i+1}"))
              for i, y in enumerate(offsets)]
    targets = []
    positions = [("Wheel centre", offsets[-1])]
    if req.wheels == "dual":
        positions.append(("Pair midpoint", 0.))
    for loc in irc.critical_locations(stack):
        for name, y in positions:
            targets.append(DepthPoint(label=f"{name} · {loc['response']}", x_m=0, y_m=y,
                                      depth_m=loc["depth_mm"]/1000,
                                      side="below" if loc["side"] == "just_inside_subgrade" else "above"))
    responses = solve_layered_elastic(layers, wheels, targets + req.points)
    if layers[0].E_Pa < req.bituminous_E_MPa*1e6:
        notes.append(f"Catalogue cap applied. Effective bituminous modulus is {layers[0].E_Pa/1e6:g} MPa.")
    sources = list(dict.fromkeys([profile.pop("source"), irc.get("37.standard_load").source,
                                  irc.get("37.catalogue_scope").source,
                                  irc.get("37.analysis").source, *(row.material.source for row in stack),
                                  *(check.source for check in checks)]))
    if profile.get("nonstructural_interface") and irc.get("37.crack_relief").source not in sources:
        sources.append(irc.get("37.crack_relief").source)
    for provision in irc.PROVISIONS.values():
        if provision.source in sources and provision.notes and provision.notes not in notes:
            notes.append(provision.notes)
    return LayeredElasticResult(profile=profile, layers=layers, patches=wheels, pressure_Pa=wheels[0].pressure_Pa,
                                critical=responses[:len(targets)], points=responses[len(targets):],
                                checks=[IRCCheck.model_validate(c, from_attributes=True) for c in checks],
                                sources=[Citation.model_validate(s, from_attributes=True) for s in sources],
                                modeling_notes=notes)


def compliance(req: IRCComplianceRequest) -> IRCComplianceResult:
    functions = {"pqc": irc.check_pqc, "dlc": irc.check_dlc, "wbm": irc.check_wbm,
                 "dowel": irc.check_dowel, "grading": irc.check_grading}
    args = dict(req.arguments)
    if req.kind == "tie_bars":
        return IRCComplianceResult(options=list(irc.tie_bar_options(**args)), sources=[_citation("15.tie_bars")])
    if req.kind == "grading" and "measured_percent_passing" in args:
        args["measured_percent_passing"] = {float(k): v for k, v in args["measured_percent_passing"].items()}
    try:
        checks = functions[req.kind](**args)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    return IRCComplianceResult(checks=[IRCCheck.model_validate(c, from_attributes=True) for c in checks])


def bridge_guidance(width_m: float, vehicle: str = "A") -> dict:
    return {"passing_clearance_m": irc.class_AB_passing_clearance(width_m * 1000, vehicle) / 1000,
            "lane_load_cases": irc.lane_load_cases(width_m * 1000),
            "sources": [_citation("6.A_B_clearances"), _citation("6.lane_combinations")]}


def solve_placements(base_config, placements):
    if any(p.a != base_config.a or p.b != base_config.b for p in placements):
        raise ValueError("All placement dimensions must match the analysis plate.")
    previews = [preview_loads(p) for p in placements]
    results = solve_sweep(base_config, [p.vehicle_load for p in previews], include_field=True)
    for result, preview in zip(results, previews):
        result.modeling_notes.extend(preview.notes)
        result.sources.extend(preview.sources)
    return results
