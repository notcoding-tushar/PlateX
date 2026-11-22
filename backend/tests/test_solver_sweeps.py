from unittest.mock import patch

import numpy as np
import pytest
from scipy.sparse.linalg import spsolve

from hosnt12 import solver
from hosnt12.constants import DOF, U, W
from hosnt12.loads import assemble_rhs
from hosnt12.postprocess import evaluate_point
from hosnt12.schemas import AnalysisConfig, ContactPatch, QueryPoint, VehicleLoad


def test_moving_wheels_reuse_one_lu():
    config = AnalysisConfig(m=4, n=3, E=30e9, nu=0.2, q0=0)
    vehicles = [
        VehicleLoad(patches=[ContactPatch(x_m=x, y_m=1, force_N=1200, shape="circle", radius_m=0.12)])
        for x in (0.15, 0.52)
    ]
    with (
        patch.object(solver, "splu", wraps=solver.splu) as lu,
        patch.object(solver, "assemble_system", wraps=solver.assemble_system) as assemble,
    ):
        results = solver.solve_sweep(config, vehicles)
        assert lu.call_count == assemble.call_count == 1
    assert results[0].w_center_m != results[1].w_center_m
    for vehicle, result in zip(vehicles, results):
        case = config.model_copy(update={"vehicle_load": vehicle})
        single = solver.solve_hosnt12(case)
        assert result.model_dump(exclude={"time_s"}) == single.model_dump(exclude={"time_s"})
        system = solver.assemble_system(case)
        rhs = assemble_rhs(case, system.mesh, system.layers)
        u = np.zeros_like(rhs)
        u[system.free] = spsolve(system.K_free, rhs[system.free])
        assert result.max_abs_deflection_m == pytest.approx(abs(u[W::DOF]).max(), rel=1e-12, abs=0)


def test_uniform_field_rhs_and_point_stress():
    config = AnalysisConfig(a=2, b=3, m=2, n=3, E=30e9, nu=0.2, q0=0, alpha=1e-5, t_coeffs=(5, 0, 0))
    uniform = config.model_copy(update={"thermal_distribution": "uniform"})
    system = solver.assemble_system(config)
    expected = config.E * config.alpha * 5 / (1 - config.nu)
    for case, factor in [(uniform, 1), (config, 4 / np.pi**2)]:
        rhs = assemble_rhs(case, system.mesh, system.layers)
        work = system.mesh.coords[:, 0] @ rhs[U::DOF]
        # Virtual work of unit constant axial strain.
        assert work == pytest.approx(expected * case.a * case.b * case.h * factor, rel=1e-5)
        edge = QueryPoint(x_m=0, y_m=1, z_m=0.025)
        point = evaluate_point(case, system.mesh, system.layers, np.zeros_like(rhs), edge)
        assert point.sigma_x_pa == pytest.approx(-expected if case is uniform else 0)
    results = solver.solve_sweep(config, [config, uniform])
    assert results[0].point_results == []
    assert results[0].sigma_x_pa != results[1].sigma_x_pa


def test_queries_and_incompatible_sweep():
    points = [
        QueryPoint(label=side, x_m=0.41, y_m=0.75, z_m=0.017, layer_side=side) for side in ("above", "below")
    ]
    config = AnalysisConfig(m=3, n=2, material_mode="laminate", query_points=points)
    above, below = solver.solve_hosnt12(config).point_results
    assert above.w_m == below.w_m
    assert above.sigma_x_pa != below.sigma_x_pa
    assert [above.label, below.label] == ["above", "below"]
    with pytest.raises(ValueError, match="share geometry"):
        solver.solve_sweep(config, [config.model_copy(update={"m": 2})])
