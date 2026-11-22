"""Sparse stiffness assembly, reusable factorization and HOSNT12 analysis entry points."""

import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import splu

from .boundary import constrained_dofs
from .constants import DOF, W
from .elements import b_matrices, element_geometry
from .loads import assemble_rhs
from .materials import compute_stiffness_and_environment_resultants, reference_flexural_rigidity
from .mesh import MeshData, build_mesh
from .postprocess import sample_response
from .schemas import AnalysisConfig, AnalysisResult, ContactPatch, DeflectionField, LayerProperty, VehicleLoad


@dataclass
class AssembledSystem:
    mesh: MeshData
    layers: list[LayerProperty]
    free: np.ndarray
    K_free: csr_matrix
    rigidity: tuple[float, float]
    foundation: tuple[float, float, float]
    diagnostics: dict


def assemble_system(config: AnalysisConfig) -> AssembledSystem:
    a, b = config.a, config.b
    mesh = build_mesh(a, b, config.m, config.n)
    coords, elements, _ = mesh
    Db, Ds, _, layers = compute_stiffness_and_environment_resultants(
        config.h, config.material_mode, config.E, config.nu, layers=config.layers
    )
    rigidity = reference_flexural_rigidity(config.h, config.material_mode, config.E, config.nu, layers)
    flexural_rigidity = rigidity[0]
    f = config.foundation
    Kw, Kp = f.Kw, f.Kp
    Kp_y = Kp if f.Kp_y is None else f.Kp_y
    K0, J0 = f.K0, f.J0
    if K0 is not None or J0 is not None:
        Kw = (K0 or 0.0) * flexural_rigidity / (a**4)
        Kp = (J0 or 0.0) * flexural_rigidity / (a**2)
        Kp_y = (J0 or 0.0) * flexural_rigidity / (b**2)

    gp3, gw3 = np.polynomial.legendre.leggauss(3)
    gp2, gw2 = np.polynomial.legendre.leggauss(2)

    ndof = coords.shape[0] * DOF
    rows, cols, vals = [], [], []
    local_w_dofs = np.arange(8) * DOF + W

    for el in elements:
        ce = coords[el]
        edofs = (el[:, None] * DOF + np.arange(DOF)).reshape(-1)
        Ke = np.zeros((8 * DOF, 8 * DOF), dtype=float)
        for xi, wx in zip(gp3, gw3):
            for eta, wy in zip(gp3, gw3):
                N, dNx, dNy, detJ = element_geometry(ce, xi, eta)
                Bb, _ = b_matrices(N, dNx, dNy)
                dA = wx * wy * detJ
                Ke += (Bb.T @ Db @ Bb) * dA
                if Kw > 0.0 or Kp > 0.0 or Kp_y > 0.0:
                    Kf = Kw * np.outer(N, N) + Kp * np.outer(dNx, dNx) + Kp_y * np.outer(dNy, dNy)
                    Ke[np.ix_(local_w_dofs, local_w_dofs)] += Kf * dA

        for xi, wx in zip(gp2, gw2):
            for eta, wy in zip(gp2, gw2):
                N, dNx, dNy, detJ = element_geometry(ce, xi, eta)
                _, Bs = b_matrices(N, dNx, dNy)
                Ke += (Bs.T @ Ds @ Bs) * (wx * wy * detJ)

        rr, cc = np.meshgrid(edofs, edofs, indexing="ij")
        rows.append(rr.ravel())
        cols.append(cc.ravel())
        vals.append(Ke.ravel())
    K = coo_matrix(
        (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(ndof, ndof)
    ).tocsr()
    K.sum_duplicates()

    tol = max(a, b, 1.0) * 1e-9
    fixed = constrained_dofs(coords, a, b, choicebc=config.choicebc, tol=tol)
    free = np.setdiff1d(np.arange(ndof), fixed, assume_unique=True)
    K_free = K[free][:, free]
    # Stiffness matrix diagnostics
    diag_K = K.diagonal()
    sym_diff = K - K.T
    max_asym = float(np.max(np.abs(sym_diff.data))) if sym_diff.nnz > 0 else 0.0
    diagnostics = {
        "global_shape": K.shape,
        "reduced_shape": K_free.shape,
        "nnz": int(K.nnz),
        "density_pct": 100.0 * K.nnz / (ndof * ndof),
        "diag_min": float(np.min(diag_K)),
        "diag_max": float(np.max(diag_K)),
        "frobenius_norm": float(np.linalg.norm(K.data)),
        "max_asymmetry": max_asym,
        "Db_norm": float(np.linalg.norm(Db)),
        "Ds_norm": float(np.linalg.norm(Ds)),
        "Db_top_left_4x4": Db[:4, :4],
        "Ds_top_left_2x2": Ds[:2, :2],
    }
    return AssembledSystem(mesh, layers, free, K_free, rigidity, (Kw, Kp, Kp_y), diagnostics)


def factorize_system(K_free):
    """Factor the supplied reduced matrix in CSC storage."""
    return splu(K_free.tocsc())


def _factor_for_solve(system):
    # SuperLU's CSR spsolve path factors the transpose and requests a transposed
    # backsolve. Match its pivot order to preserve archived stress values.
    return factorize_system(system.K_free.T)


def _load_warnings(config, layers):
    warnings = []
    for coeffs, field, label, attrs, iso_value in (
        (config.t_coeffs, "Temperature", "thermal expansion", ("alpha1", "alpha2"), config.alpha),
        (config.c_coeffs, "Moisture", "moisture expansion", ("beta1", "beta2"), config.beta),
    ):
        values = [getattr(ply, attr) for ply in layers for attr in attrs] if layers else [iso_value]
        if coeffs and any(coeffs) and not any(values):
            warnings.append(f"{field} field given but every {label} coefficient is zero; it has no effect.")
    if config.vehicle_load:
        for patch in config.vehicle_load.patches:
            if patch.shape == "circle":
                rx = ry = patch.radius_m
            else:
                rx, ry = patch.length_m / 2, patch.width_m / 2
            if not (rx <= patch.x_m <= config.a - rx and ry <= patch.y_m <= config.b - ry):
                warnings.append(
                    "A wheel patch extends beyond the plate; only the part on the plate is loaded."
                )
    return warnings


def _solve_case(config, system, factor, start, include_field=False):
    mesh = system.mesh
    rhs = assemble_rhs(config, mesh, system.layers)
    uf = np.zeros_like(rhs)
    uf[system.free] = factor.solve(rhs[system.free], trans="T")
    if not np.all(np.isfinite(uf)):
        raise RuntimeError("Non-finite solution; reduced stiffness matrix may be singular.")
    result = AnalysisResult(
        mesh=f"{config.m}x{config.n}",
        m=config.m,
        n=config.n,
        nodes=len(mesh.coords),
        elements=len(mesh.elements),
        ndof=len(uf),
        free_dofs=len(system.free),
        fixed_dofs=len(uf) - len(system.free),
        flexural_rigidity_D_Nm=system.rigidity[0],
        flexural_rigidity_Dy_Nm=system.rigidity[1],
        stiffness_info=system.diagnostics,
        solver_warnings=_load_warnings(config, system.layers),
        time_s=time.perf_counter() - start,
        **sample_response(config, mesh, system.layers, uf, system.rigidity[0]),
    )
    if include_field:
        result.field = DeflectionField(
            coordinates=mesh.coords.tolist(), elements=mesh.elements.tolist(), w_m=uf[W::DOF].tolist()
        )
    return result, uf


def _single(config, include_field=False):
    start = time.perf_counter()
    system = assemble_system(config)
    result, uf = _solve_case(config, system, _factor_for_solve(system), start, include_field)
    return result, uf, system


def solve_hosnt12(config: AnalysisConfig, *, include_field: bool = False) -> AnalysisResult:
    return _single(config, include_field)[0]


_LOAD_FIELDS = {
    "vehicle_load",
    "q0",
    "nonlocal_parameter",
    "load_case",
    "thermal_distribution",
    "alpha",
    "beta",
    "t_coeffs",
    "c_coeffs",
    "query_points",
}


def solve_sweep(
    base_config: AnalysisConfig,
    load_cases: Sequence[AnalysisConfig | VehicleLoad],
    *,
    include_field: bool = False,
) -> list[AnalysisResult]:
    """Solve each full config or vehicle placement on the same mesh, material and supports."""
    if not load_cases:
        return []
    base_stiffness = base_config.model_dump(exclude=_LOAD_FIELDS)
    system = assemble_system(base_config)
    factor = _factor_for_solve(system)
    results = []
    for case in load_cases:
        if isinstance(case, VehicleLoad):
            case = base_config.model_copy(update={"vehicle_load": case})
        elif case.model_dump(exclude=_LOAD_FIELDS) != base_stiffness:
            raise ValueError("Sweep cases must share geometry, material, boundary conditions and foundation.")
        result, _ = _solve_case(case, system, factor, time.perf_counter(), include_field)
        results.append(result)
    return results


def solve_hosnt12_legacy(**kwargs) -> dict:
    """Accept the archived keyword arguments, including its dataclass plies and wheel tuples."""
    foundation = {k: kwargs.pop(k) for k in ("Kw", "Kp", "Kp_y", "K0", "J0") if k in kwargs}
    vehicle = kwargs.get("vehicle_load")
    if vehicle is not None and hasattr(vehicle, "wheel_patches"):
        kwargs["vehicle_load"] = VehicleLoad(
            nodal_loads=vehicle.nodal_loads,
            patches=[
                ContactPatch(x_m=x, y_m=y, length_m=dx, width_m=dy, force_N=f)
                for x, y, dx, dy, f in vehicle.wheel_patches
            ],
        )
    if kwargs.get("layers"):
        kwargs["layers"] = [
            LayerProperty.model_validate(ply, from_attributes=True) for ply in kwargs["layers"]
        ]
    config = AnalysisConfig(foundation=foundation, **kwargs)
    result, uf, system = _single(config)
    inputs = config.model_dump(
        exclude={"vehicle_load", "layers", "query_points", "foundation", "thermal_distribution"}
    )
    inputs.update(config.foundation.model_dump())
    inputs["Kw"], inputs["Kp"], inputs["Kp_y"] = system.foundation
    return {
        **result.model_dump(),
        "stiffness_info": system.diagnostics,
        "coordinates": system.mesh.coords,
        "elements_array": system.mesh.elements,
        "displacements": uf,
        "w_values": uf[W::DOF],
        "inputs": inputs,
    }
