"""Deflection and one-sided ply stress recovery for a solved plate."""

import math

import numpy as np

from .constants import DOF, W
from .elements import b_matrices, element_geometry
from .loads import sinusoidal_field
from .materials import environmental_profile, layer_at_z, material_at_z
from .mesh import MeshData
from .schemas import AnalysisConfig, PointResult, QueryPoint


def find_elements_at(mesh: MeshData, xp: float, yp: float):
    """All elements containing the point (several when it lies on a shared edge or node)."""
    candidates = []
    for ei, el in enumerate(mesh.elements):
        ce = mesh.coords[el]
        if (
            ce[:, 0].min() - 1e-9 <= xp <= ce[:, 0].max() + 1e-9
            and ce[:, 1].min() - 1e-9 <= yp <= ce[:, 1].max() + 1e-9
        ):
            candidates.append((ei, el, ce))
    if not candidates:
        raise ValueError(f"No element contains point {(xp, yp)}.")
    return candidates


def natural_coordinates(ce: np.ndarray, xp: float, yp: float) -> tuple[float, float]:
    xmin, xmax = ce[:, 0].min(), ce[:, 0].max()
    ymin, ymax = ce[:, 1].min(), ce[:, 1].max()
    xi = 2.0 * (xp - xmin) / (xmax - xmin) - 1.0
    eta = 2.0 * (yp - ymin) / (ymax - ymin) - 1.0
    return float(xi), float(eta)


def element_strains(ce: np.ndarray, ue: np.ndarray, xi: float, eta: float, zp: float):
    """In-plane/normal strains (4) and transverse shear strains (2) at (xi, eta, z) of one element."""
    N, dNx, dNy, _ = element_geometry(ce, xi, eta)
    Bb, Bs = b_matrices(N, dNx, dNy)
    gp = Bb @ ue
    strain4 = np.array(
        [
            gp[0] + zp * gp[4] + (zp**2) * gp[8] + (zp**3) * gp[12],
            gp[1] + zp * gp[5] + (zp**2) * gp[9] + (zp**3) * gp[13],
            gp[2] + zp * gp[6] + (zp**2) * gp[10],
            gp[3] + zp * gp[7] + (zp**2) * gp[11] + (zp**3) * gp[14],
        ],
        dtype=float,
    )
    sh = Bs @ ue
    shear_strain = np.array(
        [
            sh[0] + zp * sh[2] + (zp**2) * sh[4] + (zp**3) * sh[6],
            sh[1] + zp * sh[3] + (zp**2) * sh[5] + (zp**3) * sh[7],
        ],
        dtype=float,
    )
    return N, strain4, shear_strain


gauss_sp = 1.0 / math.sqrt(3.0)


def recovered_shear_strain(ce: np.ndarray, ue: np.ndarray, xi: float, eta: float, zp: float):
    """Transverse shear strain extrapolated (bilinear) from the 2x2 Gauss points, where the
    reduced-integrated shear field of the Q8 element is most accurate."""
    s, t = xi / gauss_sp, eta / gauss_sp
    out = np.zeros(2, dtype=float)
    for sx, sy in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)):
        wgt = 0.25 * (1.0 + sx * s) * (1.0 + sy * t)
        out += wgt * element_strains(ce, ue, sx * gauss_sp, sy * gauss_sp, zp)[2]
    return out


def evaluate_point(
    config: AnalysisConfig, mesh: MeshData, layers, uf: np.ndarray, point: QueryPoint
) -> PointResult:
    xp, yp, zp = point.x_m, point.y_m, point.z_m
    if not (0 <= xp <= config.a and 0 <= yp <= config.b and abs(zp) <= config.h / 2):
        raise ValueError(f"Query point {point.label!r} lies outside the plate.")
    layer = layer_at_z(layers, zp, point.layer_side) if layers else None
    Cb, Cs, alpha_vec, beta_vec = material_at_z(
        config.material_mode, config.E, config.nu, config.alpha, config.beta, layer
    )
    spatial = (
        1.0 if config.thermal_distribution == "uniform" else sinusoidal_field(xp, yp, config.a, config.b)
    )
    temp_pt = environmental_profile(zp, config.h, config.t_coeffs) * spatial
    conc_pt = environmental_profile(zp, config.h, config.c_coeffs) * spatial
    eps_env = alpha_vec * temp_pt + beta_vec * conc_pt

    cands = find_elements_at(mesh, xp, yp)
    w0_val = 0.0
    stress4 = np.zeros(4, dtype=float)
    shear2 = np.zeros(2, dtype=float)
    for _, el, ce in cands:
        xi, eta = natural_coordinates(ce, xp, yp)
        ue = uf[(el[:, None] * DOF + np.arange(DOF)).reshape(-1)]
        N, strain4, _ = element_strains(ce, ue, xi, eta, zp)
        stress4 += Cb @ (strain4 - eps_env)
        shear2 += Cs @ recovered_shear_strain(ce, ue, xi, eta, zp)
        w0_val += float(N @ ue[W::DOF])
    nc = float(len(cands))
    return PointResult(
        label=point.label,
        x_m=xp,
        y_m=yp,
        z_m=zp,
        w_m=w0_val / nc,
        sigma_x_pa=stress4[0] / nc,
        sigma_y_pa=stress4[1] / nc,
        tau_xy_pa=stress4[3] / nc,
        tau_xz_pa=shear2[0] / nc,
        tau_yz_pa=shear2[1] / nc,
    )


def sample_response(config, mesh, layers, uf, flexural_rigidity):
    a, b, h, q0 = config.a, config.b, config.h, config.q0
    stress_sample_locations = {
        "sigma_x": {"x_m": a / 2.0, "y_m": b / 2.0, "z_m": h / 2.0},
        "tau_xy": {"x_m": 0.0, "y_m": 0.0, "z_m": -h / 3.0},
        "tau_xz": {"x_m": 0.0, "y_m": b / 2.0, "z_m": 0.0},
    }
    center, corner, edge = [
        evaluate_point(config, mesh, layers, uf, QueryPoint(label=label, **position))
        for label, position in stress_sample_locations.items()
    ]
    w_center, sigma_x_pa = center.w_m, center.sigma_x_pa
    tau_xy_pa, tau_xz_pa = corner.tau_xy_pa, edge.tau_xz_pa
    if q0 > 0.0:
        w_bar = 100.0 * flexural_rigidity * w_center / (q0 * (a**4))
        sigma_x_bar = (h**2 / (q0 * (a**2))) * sigma_x_pa
        tau_xy_bar = (h / (q0 * a)) * tau_xy_pa
        tau_xz_bar = -(h / (q0 * a)) * tau_xz_pa
    else:
        w_bar = sigma_x_bar = tau_xy_bar = tau_xz_bar = None

    return {
        "w_center_m": w_center,
        "max_abs_deflection_m": float(np.max(np.abs(uf[W::DOF]))),
        "min_deflection_m": float(np.min(uf[W::DOF])),
        "max_deflection_m": float(np.max(uf[W::DOF])),
        "sigma_x_pa": sigma_x_pa,
        "tau_xy_pa": tau_xy_pa,
        "tau_xz_pa": tau_xz_pa,
        "w_bar": w_bar,
        "sigma_x_bar": sigma_x_bar,
        "tau_xy_bar": tau_xy_bar,
        "tau_xz_bar": tau_xz_bar,
        "stress_sample_locations": stress_sample_locations,
        "point_results": [evaluate_point(config, mesh, layers, uf, p) for p in config.query_points],
    }
