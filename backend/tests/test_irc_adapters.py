import pytest
from fastapi.testclient import TestClient

from api.main import app
from hosnt12.irc import adapters
from hosnt12.schemas import (
    AnalysisConfig,
    IRCFlexibleRequest,
    IRCFoundationLookup,
    IRCPlacement,
    IRCRigidRequest,
)


@pytest.fixture
def base():
    return AnalysisConfig(a=4, b=4, h=0.3, m=2, n=2, E=30e9, nu=0.15, q0=0)


def test_rigid_si_and_double_count_guard(base):
    result = adapters.prepare_rigid(IRCRigidRequest(base_config=base, cbr_percent=10,
                                                    temperature_zone="IV"))
    assert result.config.foundation.Kw == 55e6
    assert result.config.E == 30e9
    assert result.config.t_coeffs == (0, 21, 0)
    assert result.config.thermal_distribution == "uniform"
    assert any("nonlinear" in n for n in result.modeling_notes)
    with pytest.raises(ValueError, match="double-count"):
        adapters.prepare_rigid(IRCRigidRequest(base_config=base, cbr_percent=10,
                                               support="effective", explicit_dlc=True))
    with pytest.raises(ValueError, match="audit"):
        adapters.prepare_rigid(IRCRigidRequest(base_config=base, cbr_percent=10,
                                               support="effective", raw=True))


def test_flexible_stack_and_queries(base):
    result = adapters.prepare_flexible(IRCFlexibleRequest(base_config=base, category="a", cbr=5,
        traffic_msa=10, bituminous_E_MPa=2000, subgrade_thickness_m=1, x_m=2, y_m=2))
    assert result.config.material_mode == "laminate"
    assert result.config.layers[0].h_bottom == pytest.approx(-result.config.h / 2)
    assert sum(p.force_N for p in result.config.vehicle_load.patches) == 40000
    assert any("eps_z = 0" in note for note in result.modeling_notes)
    assert result.config.query_points


def test_foundation_audit_and_missing_cells():
    audit = adapters.foundation_lookup(IRCFoundationLookup(cbr_percent=10, subbase_thickness_mm=150,
                                                            interpolate=True, raw=True))
    assert audit["raw_audit_only"]
    assert audit["effective_k_N_per_m3"] == audit["effective_k_MPa_per_m"] * 1e6
    with pytest.raises(ValueError):
        adapters.foundation_lookup(IRCFoundationLookup(cbr_percent=100, subbase_thickness_mm=150))


def test_bridge_cases_and_api(base):
    client = TestClient(app)
    assert {"AA_WHEELED", "AA_TRACKED", "SV_TRAILER"} <= {o["case"] for o in client.get("/api/irc/options").json()}
    body = IRCPlacement(case="AA_WHEELED", a=4, b=4, x_m=0, y_m=2).model_dump()
    assert client.post("/api/irc/preview-loads", json=body).status_code == 422
    body["case"] = "A"
    preview = client.post("/api/irc/preview-loads", json=body)
    assert preview.status_code == 200
    assert not preview.json()["inside_plate"]
    compliance = client.post("/api/irc/compliance", json={"kind": "pqc", "arguments": {
        "flexural_strength_28d_MPa": 5, "water_cementitious_ratio": 0.4}})
    assert compliance.status_code == 200
    assert compliance.json()["checks"][0]["source"]["code"] == "IRC:58-2015"


def test_sweep_retains_clipped_load(base):
    placement = IRCPlacement(case="dual", a=4, b=4, x_m=0, y_m=2)
    result = adapters.solve_placements(base, [placement])
    assert len(result) == 1
    assert result[0].modeling_notes


def test_climate_options_and_day_night_api():
    client = TestClient(app)
    options = client.get("/api/irc/climate-options").json()
    assert options["source"]["code"] == "IRC:58-2015"
    assert len(options["zones"]) == 7
    assert "Maharashtra" in next(z["region"] for z in options["zones"] if z["zone"] == "IV")
    payload = {"zone": "IV", "thickness_m": 0.3}
    day = client.post("/api/irc/climate-temperature", json={**payload, "period": "day"})
    night = client.post("/api/irc/climate-temperature", json={**payload, "period": "night"})
    assert day.json()["delta_T_K"] == 21
    assert night.json()["delta_T_K"] == -10.5
    assert client.post("/api/irc/climate-temperature", json={**payload, "thickness_m": 0.401}).status_code == 422


def test_layer_validation_and_multilayer_thermal_guard(base):
    flexible = adapters.prepare_flexible(IRCFlexibleRequest(base_config=base, category="a", cbr=5,
        traffic_msa=10, bituminous_E_MPa=2000, subgrade_thickness_m=1, x_m=2, y_m=2))
    data = flexible.config.model_dump()
    data["layers"][0]["h_top"] -= 0.01
    with pytest.raises(ValueError, match="contiguous"):
        AnalysisConfig.model_validate(data)
    with pytest.raises(ValueError, match="slab temperature differential"):
        adapters.prepare_rigid(IRCRigidRequest(base_config=flexible.config, cbr_percent=10,
                                               explicit_dlc=True, temperature_zone="IV"))
    heated = base.model_copy(update={"t_coeffs": (0, 10, 0)})
    with pytest.raises(ValueError, match="expansion properties"):
        adapters.prepare_flexible(IRCFlexibleRequest(base_config=heated, category="a", cbr=5,
            traffic_msa=10, bituminous_E_MPa=2000, subgrade_thickness_m=1, x_m=2, y_m=2))
