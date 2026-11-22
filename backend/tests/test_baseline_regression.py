"""Bit-for-bit parity tests against archive/Higher Validated 5-11-26.py.

Codex: ensure all tests in this file pass at <= 1e-12 relative error before closing Phase 1.
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("K0,J0", [(0, 0), (100, 0), (0, 100), (100, 100)])
def test_table2_parity_with_legacy(legacy_solver_module, K0, J0):
    from hosnt12.solver import solve_hosnt12_legacy

    kwargs = dict(
        a=1.0,
        b=3.0,
        h=0.1,
        m=6,
        n=6,
        material_mode="isotropic",
        E=117e9,
        nu=1.0 / 3.0,
        q0=100.0,
        K0=K0,
        J0=J0,
    )
    ref = legacy_solver_module.solve_hosnt12(**kwargs)
    new = solve_hosnt12_legacy(**kwargs)

    for key in ("w_center_m", "sigma_x_pa", "tau_xy_pa", "tau_xz_pa", "w_bar", "sigma_x_bar", "tau_xy_bar", "tau_xz_bar"):
        assert new[key] == pytest.approx(ref[key], rel=1e-12, abs=1e-15), f"Mismatch in {key}"


def test_laminate_hygrothermal_parity_with_legacy(legacy_solver_module):
    from hosnt12.solver import solve_hosnt12_legacy

    kwargs = dict(
        a=1.0,
        b=3.0,
        h=0.1,
        m=6,
        n=6,
        material_mode="laminate",
        q0=1e5,
        t_coeffs=(1.0, 10.0, 2.0),
        c_coeffs=(0.5, 50.0, 4.0),
        K0=60,
        J0=25,
    )
    ref = legacy_solver_module.solve_hosnt12(**kwargs)
    new = solve_hosnt12_legacy(**kwargs)

    for key in ("w_center_m", "sigma_x_pa", "tau_xy_pa", "tau_xz_pa", "flexural_rigidity_D_Nm"):
        assert new[key] == pytest.approx(ref[key], rel=1e-12, abs=1e-15), f"Mismatch in {key}"
