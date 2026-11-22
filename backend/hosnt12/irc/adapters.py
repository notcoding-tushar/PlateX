"""Translate vendored IRC footprints and provisions into SI workbench contracts."""

from ..schemas import Citation, ContactPatch, IRCCheck, IRCOption, IRCPlacement, IRCPreview, VehicleLoad
from . import irc_fea_library as irc

# Menu identifiers select library operations. All numerical provisions stay in the vendor.
_CASES = {
    "dual": ("flexible", "Standard dual wheels", "37.standard_load"),
    "dual_ctb": ("flexible", "CTB fatigue dual wheels", "37.standard_load"),
    **{g: ("rigid", f"{g.title()} axle group", "58.axles") for g in ("single", "tandem", "tridem")},
    "A": ("bridge", "Class A train", "6.A_train"),
    "B": ("bridge", "Class B train", "6.B_train"),
    "70R_TRACKED": ("bridge", "70R tracked", "6.70R_tracked"),
    "70R_WHEELED": ("bridge", "70R wheeled", "6.70R_wheeled"),
}


def options() -> list[IRCOption]:
    return [IRCOption(case=k, mode=m, label=l) for k, (m, l, _) in _CASES.items()]


def _citation(key):
    return Citation.model_validate(irc.get(key).source, from_attributes=True)


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
        patches = irc.bridge_patches(req.case, tyre_pattern=req.tyre_pattern)
        notes.append("Static vehicle contacts exclude impact and partial load factors.")
    placed = irc.translate_patches(patches, dx_mm=req.x_m * 1000, dy_mm=req.y_m * 1000)
    return placed, keys, notes


def preview_loads(req: IRCPlacement) -> IRCPreview:
    patches, keys, notes = _placement(req)
    contacts = []
    for patch in patches:
        data = patch.to_SI()
        del data["pressure_Pa"]
        contacts.append(ContactPatch(**data))
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
    if mode == "bridge":
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
