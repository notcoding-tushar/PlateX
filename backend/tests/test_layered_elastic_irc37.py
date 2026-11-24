import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app
from hosnt12.irc import irc_fea_library as irc
from hosnt12.irc.layered_elastic import solve_layered_elastic
from hosnt12.schemas import ContactPatch, DepthPoint, ElasticLayer


def layer(e, h=None, nu=0.3):
    return ElasticLayer(name=f"{e} MPa", E_Pa=e * 1e6, nu=nu, thickness_m=h)


def wheel(x=0, y=0):
    return ContactPatch(
        x_m=x, y_m=y, shape="circle", force_N=20000, radius_m=math.sqrt(20000 / (math.pi * 560000))
    )


def point(z, x=0, y=0, side="below"):
    return DepthPoint(x_m=x, y_m=y, depth_m=z, side=side)


def test_uniform_disk_boussinesq_axis():
    soil, patch = layer(100), wheel()
    a, q, nu = patch.radius_m, patch.pressure_Pa, soil.nu
    # Also exercise Hankel inversion through a fictitious bonded interface.
    for stack in ([soil], [layer(100, 0.12), soil]):
        for z in (0.0, 0.06, 0.12, 0.45):
            (result,) = solve_layered_elastic(stack, [patch], [point(z)])
            distance = math.hypot(a, z)
            u = z / distance
            sz = -q * (1 - u**3)
            sr = -0.5 * q * (1 + 2 * nu - 2 * (1 + nu) * u + u**3)
            w = q * (1 + nu) / soil.E_Pa * (2 * (1 - nu) * (distance - z) + z * (1 - u))
            assert result.w_m == pytest.approx(w, rel=1e-7)
            assert result.sigma_z_Pa == pytest.approx(sz, rel=1e-7)
            assert result.sigma_r_Pa == pytest.approx(sr, rel=1e-7)
            assert result.sigma_theta_Pa == pytest.approx(sr, rel=1e-7)
            assert result.eps_z == pytest.approx((sz - 2 * nu * sr) / soil.E_Pa)
            assert result.tau_rz_Pa == pytest.approx(0.0, abs=1e-8)


def test_surface_traction_inside_rim_outside_and_off_axis_direct_field():
    patch = wheel()
    stack = [layer(2000, 0.1), layer(100)]
    for ratio, pressure in ((0.5, 1.0), (1.0, 0.5), (1.2, 0.0)):
        (row,) = solve_layered_elastic(stack, [patch], [point(0, x=patch.radius_m * ratio)])
        assert row.sigma_z_Pa == pytest.approx(-pressure * patch.pressure_Pa, abs=1e-5)
        assert abs(row.tau_rz_Pa) < 1e-6
    # Compare physical-space disk integration against a direct Hankel inversion.
    queries = [point(0.1, x=0.037), point(0.1, x=0.31)]
    for direct, hankel in zip(
        solve_layered_elastic([layer(100)], [patch], queries),
        solve_layered_elastic([layer(100, 0.04), layer(100)], [patch], queries),
    ):
        for key in ("w_m", "sigma_r_Pa", "sigma_theta_Pa", "sigma_z_Pa", "tau_rz_Pa"):
            assert getattr(direct, key) == pytest.approx(getattr(hankel, key), rel=1e-7)


def test_bonded_interface_and_independent_three_layer_case():
    stack = [layer(2000, 0.1), layer(200, 0.3), layer(75)]
    for z in (0.1, 0.4):
        upper, lower = solve_layered_elastic(
            stack, [wheel()], [point(z, x=0.155, side=side) for side in ("above", "below")]
        )
        for key in ("sigma_z_Pa", "tau_rz_Pa", "w_m", "eps_r", "eps_theta"):
            assert getattr(upper, key) == pytest.approx(getattr(lower, key), rel=1e-7)
        assert upper.eps_z != pytest.approx(lower.eps_z)
    # Recorded single-wheel example in IITPAVE comparison report §2.4.
    # Printed output provides a cross-check, independent of the analytical tests.
    np.testing.assert_allclose(
        [upper.sigma_z_Pa, upper.sigma_theta_Pa, upper.w_m, upper.eps_z, lower.eps_z],
        [-21960, 23410, 0.1962e-3, -0.0001734, -0.0003093],
        rtol=0.003,
    )


def test_seven_layer_interface_from_comparison_report():
    stack = [
        layer(3000, 0.1, 0.45),
        layer(3000, 0.1, 0.45),
        layer(100, 0.1, 0.35),
        layer(5000, 0.2, 0.25),
        layer(600, 0.2, 0.25),
        layer(80, 0.2, 0.35),
        layer(80, None, 0.35),
    ]
    wheels = [
        ContactPatch(
            x_m=x, y_m=0, force_N=20000, shape="circle", radius_m=math.sqrt(20000 / (math.pi * 700000))
        )
        for x in (-0.155, 0.155)
    ]
    # At the suspect depth check the actual bonded conditions, independent of
    # any assumption about how IITPAVE combines the two wheel shear components.
    upper, lower = solve_layered_elastic(
        stack, wheels, [point(0.7, x=0.08, side=side) for side in ("above", "below")]
    )
    for key in ("w_m", "sigma_z_Pa", "tau_rz_Pa", "eps_r", "eps_theta"):
        assert getattr(upper, key) == pytest.approx(getattr(lower, key), rel=1e-7)


def test_dual_tensor_superposition_and_midpoint_symmetry():
    wheels = [wheel(y=-0.155), wheel(y=0.155)]
    stack = [layer(1200, 0.12), layer(90)]
    p = point(0.2, x=0.08, y=0.03)
    total, mid = solve_layered_elastic(stack, wheels, [p, point(0.2)])
    radial = hoop = shear = vertical = disp = 0.0
    for patch in wheels:
        (single,) = solve_layered_elastic(stack, [patch], [p])
        angle = math.atan2(p.y_m - patch.y_m, p.x_m) - math.atan2(p.y_m, p.x_m)
        c, s = math.cos(angle), math.sin(angle)
        radial += single.sigma_r_Pa * c * c + single.sigma_theta_Pa * s * s
        hoop += single.sigma_r_Pa * s * s + single.sigma_theta_Pa * c * c
        shear += single.tau_rz_Pa * c
        vertical += single.sigma_z_Pa
        disp += single.w_m
    np.testing.assert_allclose(
        [total.sigma_r_Pa, total.sigma_theta_Pa, total.tau_rz_Pa, total.sigma_z_Pa, total.w_m],
        [radial, hoop, shear, vertical, disp],
    )
    assert abs(mid.tau_rz_Pa) < 1e-8
    # Probe the midpoint along the wheel line as well as the fallback +x axis.
    (rotated,) = solve_layered_elastic(stack, [wheel(x=-0.155), wheel(x=0.155)], [point(0.2)])
    assert abs(rotated.tau_rz_Pa) < 1e-8


@pytest.mark.parametrize("category", list("abcdef"))
def test_catalogue_api(category):
    client = TestClient(app)
    body = {
        "category": category,
        "cbr": 5,
        "traffic_msa": 10,
        "bituminous_E_MPa": 5000,
        "ctb_fatigue": True,
        "points": [point(0.18, x=0.13).model_dump()],
    }
    res = client.post("/api/irc/flexible/layered-elastic", json=body)
    assert res.status_code == 200, res.text
    result = res.json()
    native = irc.catalogue_layers(category, 5, 10, bituminous_E_MPa=5000)
    assert result["engine"] == "layered_elastic_irc37"
    assert [row["E_Pa"] for row in result["layers"]] == [s.material.E_MPa * 1e6 for s in native]
    assert result["layers"][-1]["thickness_m"] is None
    assert len(result["points"]) == 1
    assert len(result["critical"]) == 2 * len(irc.critical_locations(native))
    assert result["critical"][-1]["layer"] == "subgrade"
    assert result["critical"][-1]["eps_z"] < 0
    assert any("cap applied" in n for n in result["modeling_notes"])
    assert result["checks"][-1]["status"] == "needs_input"
    for received, expected in zip(result["checks"], irc.check_flexible_stack(native, category=category)):
        assert received["message"] == expected.message
        assert received["source"]["pdf_pages"] == list(expected.source.pdf_pages)
    for p, ref in zip(result["patches"], irc.flexible_standard_patches(ctb_fatigue=True)):
        assert p["radius_m"] == pytest.approx(ref.to_SI()["radius_m"])
        assert p["y_m"] == pytest.approx(ref.to_SI()["y_m"])


def test_custom_single_and_invalid_inputs():
    client = TestClient(app)
    path = "/api/irc/flexible/layered-elastic"
    body = {
        "category": "a",
        "cbr": 5,
        "traffic_msa": 10,
        "bituminous_E_MPa": 1500,
        "wheels": "single",
        "wheel_force_N": 24000,
        "pressure_Pa": 600000,
    }
    data = client.post(path, json=body).json()
    assert data["patches"][0]["radius_m"] == pytest.approx(math.sqrt(24000 / (math.pi * 600000)))
    assert len(data["patches"]) == 1 and data["patches"][0]["y_m"] == 0
    assert len(data["critical"]) == 2
    pair = client.post(path, json=body | {"wheels": "dual", "spacing_m": 0.44}).json()
    assert [p["y_m"] for p in pair["patches"]] == pytest.approx([-0.22, 0.22])
    assert pair["pressure_Pa"] == pytest.approx(600000)
    for change in ({"cbr": 5.5}, {"spacing_m": 0.5}, {"pressure_Pa": 0}, {"subgrade_thickness_m": 1}):
        assert client.post(path, json=body | change).status_code == 422
    with pytest.raises(ValueError, match="semi-infinite"):
        solve_layered_elastic([layer(100, 0.1)], [wheel()], [point(0)])


def test_flexible_plate_engine_retains_its_provenance_and_warning():
    client = TestClient(app)
    prepared = client.post(
        "/api/irc/flexible",
        json={
            "base_config": {"a": 4, "b": 4, "h": 0.2, "m": 2, "n": 2, "E": 30e9, "nu": 0.15},
            "category": "a",
            "cbr": 5,
            "traffic_msa": 10,
            "bituminous_E_MPa": 2000,
            "subgrade_thickness_m": 1,
            "x_m": 2,
            "y_m": 2,
        },
    ).json()
    res = client.post("/api/irc/solve", json=prepared)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["engine"] == "hosnt12_plate_q8"
    assert data["sources"] == prepared["sources"]
    assert any("eps_z = 0" in note for note in data["modeling_notes"])
