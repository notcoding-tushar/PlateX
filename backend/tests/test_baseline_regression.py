"""Bit-for-bit parity tests against archive/Higher Validated 5-11-26.py.

Codex: ensure all tests in this file pass at <= 1e-12 relative error before closing Phase 1.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("K0,J0", [(0, 0), (100, 0), (0, 100), (100, 100)])
def test_table2_parity_with_legacy(legacy_solver_module, K0, J0):
    from hosnt12.solver import solve_hosnt12_legacy

    kwargs = {
        "a": 1.0,
        "b": 3.0,
        "h": 0.1,
        "m": 6,
        "n": 6,
        "material_mode": "isotropic",
        "E": 117e9,
        "nu": 1.0 / 3.0,
        "q0": 100.0,
        "K0": K0,
        "J0": J0,
    }
    ref = legacy_solver_module.solve_hosnt12(**kwargs)
    new = solve_hosnt12_legacy(**kwargs)

    for key in (
        "w_center_m",
        "sigma_x_pa",
        "tau_xy_pa",
        "tau_xz_pa",
        "w_bar",
        "sigma_x_bar",
        "tau_xy_bar",
        "tau_xz_bar",
    ):
        assert new[key] == pytest.approx(ref[key], rel=1e-12, abs=0), f"Mismatch in {key}"


def test_laminate_hygrothermal_parity_with_legacy(legacy_solver_module):
    from hosnt12.solver import solve_hosnt12_legacy

    kwargs = {
        "a": 1.0,
        "b": 3.0,
        "h": 0.1,
        "m": 6,
        "n": 6,
        "material_mode": "laminate",
        "q0": 1e5,
        "t_coeffs": (1.0, 10.0, 2.0),
        "c_coeffs": (0.5, 50.0, 4.0),
        "K0": 60,
        "J0": 25,
    }
    ref = legacy_solver_module.solve_hosnt12(**kwargs)
    new = solve_hosnt12_legacy(**kwargs)

    for key in ("w_center_m", "sigma_x_pa", "tau_xy_pa", "tau_xz_pa", "flexural_rigidity_D_Nm"):
        assert new[key] == pytest.approx(ref[key], rel=1e-12, abs=0), f"Mismatch in {key}"


@pytest.mark.parametrize("K0,J0", [(0, 0), (100, 0), (0, 100), (100, 100)])
@pytest.mark.parametrize("hygrothermal", [False, True], ids=["table2", "table3"])
def test_all_benchmark_quantities(legacy_solver_module, K0, J0, hygrothermal):
    from hosnt12.validation import solve_paper_case

    ref = legacy_solver_module.solve_paper_case(K0, J0, 10, hygrothermal)
    new = solve_paper_case(K0, J0, 10, hygrothermal)
    for key in (
        "w_center_m",
        "min_deflection_m",
        "max_deflection_m",
        "max_abs_deflection_m",
        "sigma_x_pa",
        "tau_xy_pa",
        "tau_xz_pa",
        "w_bar",
        "sigma_x_bar",
        "tau_xy_bar",
        "tau_xz_bar",
        "flexural_rigidity_D_Nm",
        "flexural_rigidity_Dy_Nm",
    ):
        assert new[key] == pytest.approx(ref[key], rel=1e-12, abs=0), key


def test_legacy_dataclasses_and_nodal_arrays(legacy_solver_module):
    import numpy as np

    from hosnt12.solver import solve_hosnt12_legacy

    args = {
        "m": 3,
        "n": 2,
        "material_mode": "laminate",
        "load_case": "uniform",
        "layers": legacy_solver_module.default_three_layer_laminate(0.1),
        "nonlocal_parameter": 0.001,
        "vehicle_load": legacy_solver_module.VehicleLoad(
            nodal_loads=[(10, 12)], wheel_patches=[(0.4, 0.5, 0.3, 0.2, 58)]
        ),
    }
    ref = legacy_solver_module.solve_hosnt12(**args)
    new = solve_hosnt12_legacy(**args)
    for key in ("coordinates", "elements_array", "displacements", "w_values"):
        np.testing.assert_allclose(new[key], ref[key], rtol=1e-12, atol=0)
