import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from hosnt12.irc import irc_fea_library as irc
from hosnt12.schemas import AnalysisConfig
from hosnt12.solver import solve_hosnt12

client = TestClient(create_app())
BASE = {"E": 117e9, "nu": 1 / 3, "m": 3, "n": 2}
PLACEMENT = {"case": "dual", "a": 4, "b": 3, "x_m": 2, "y_m": 1.5}


def test_solve_matches_engine_and_serializes_field():
    response = client.post("/api/solve", json=BASE)
    assert response.status_code == 200
    result = response.json()
    assert result["w_bar"] == solve_hosnt12(AnalysisConfig(**BASE)).w_bar
    assert len(result["field"]["w_m"]) == len(result["field"]["coordinates"]) == result["nodes"]
    assert len(result["field"]["elements"]) == 6
    assert max(map(abs, result["field"]["w_m"])) == result["max_abs_deflection_m"]
    assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("thermal,reference", [(False, 0.85891), (True, 1.80712)])
def test_live_benchmark(thermal, reference):
    response = client.get("/api/validation", params={"hygrothermal": thermal})
    assert response.status_code == 200
    report = response.json()
    assert report["reference"]["w_bar"] == reference
    assert report["computed"]["w_bar"] == pytest.approx(reference, rel=1e-3)



def test_validation_suite_returns_comparisons():
    response = client.post("/api/validation/suite", json={"tolerance_pct": 2})
    assert response.status_code == 200
    report = response.json()
    assert len(report["comparisons"]) == 32
    assert set(report["passed_cases"] + report["failed_cases"]) == {
        "M1", "M2", "M3", "M4", "H1", "H2", "H3", "H4"
    }
    assert "H2" in report["failed_cases"]


def test_sweep_and_errors():
    patch = client.post("/api/irc/preview-loads", json={**PLACEMENT, "x_m": 0.4}).json()["vehicle_load"]
    cases = [patch, {**BASE, "q0": 0}]
    response = client.post("/api/solve-sweep", json={"base_config": BASE, "load_cases": cases})
    assert response.status_code == 200
    first, second = response.json()
    assert first["w_center_m"] > 0
    assert second["w_center_m"] == 0 and second["w_bar"] is None

    assert client.post("/api/solve", json={"m": 2}).status_code == 422
    assert (
        client.post(
            "/api/solve-sweep", json={"base_config": BASE, "load_cases": [{**BASE, "m": 5}]}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "case", ["dual", "dual_ctb", "single", "tandem", "tridem", "A", "B", "70R_TRACKED", "70R_WHEELED"]
)
def test_irc_options_and_footprints(case):
    assert case in {o["case"] for o in client.get("/api/irc/options").json()}
    req = {**PLACEMENT, "case": case, "wheel_offsets_m": [-0.6, 0.6]}
    response = client.post("/api/irc/preview-loads", json=req)
    assert response.status_code == 200
    preview = response.json()
    assert all(p["force_N"] > 0 for p in preview["vehicle_load"]["patches"])
    if case == "dual":
        patch = preview["vehicle_load"]["patches"][0]
        source = irc.get("37.standard_load").source
        assert patch["radius_m"] == irc.flexible_standard_patches()[0].radius_mm / 1000
        assert preview["sources"][0]["pdf_pages"] == list(source.pdf_pages)
    assert client.post("/api/irc/check", json=req).status_code == 200


def test_irc_checks_and_invalid_geometry():
    req = {**PLACEMENT, "case": "single", "wheel_offsets_m": [-0.5, 0.5]}
    missing = client.post("/api/irc/check", json=req).json()
    assert {x["status"] for x in missing} == {"pass", "needs_input"}
    checks = client.post("/api/irc/check", json={**req, "flexural_strength_MPa": 3, "water_cm": 0.35}).json()
    assert [entry["status"] for entry in checks] == ["pass", "fail", "pass"]
    assert checks[1]["source"]["location"] == irc.get("58.pqc_strength").source.location
    assert client.post("/api/irc/preview-loads", json={**req, "wheel_offsets_m": []}).status_code == 422
    assert client.post("/api/irc/check", json={**PLACEMENT, "case": "unknown"}).status_code == 422
