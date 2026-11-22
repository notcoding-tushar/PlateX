"""HOSNT12 terminal-driven finite-element solver for plate analysis.

Formulation:
- 8-node Serendipity quadrilateral element (Q8) with 12 degrees of freedom per node:
  [u0, v0, w0, theta1, theta2, theta3, u0*, v0*, w0*, theta1*, theta2*, theta3*]
- Plane-stress constitutive law (sigma_z = 0) with the transverse displacement constant through the
  thickness (theta3, w0*, theta3* = 0), i.e. the third-order shear deformation (TSDT) kinematics of the
  reference (Zidi et al. 2014). This is what makes w_bar agree with the paper (see constrained_dofs).
- Supports Isotropic and Multilayer Orthotropic Laminate material models. The laminate is a layerwise
  plane-stress (sigma_z = 0) model with no thickness stretching, NOT a full 3D orthotropic analysis:
    active   : E1, E2, nu12, G12 (in-plane), G13, G23 (transverse shear), ply angle, alpha1, alpha2,
               beta1, beta2 (in-plane expansion);
    inactive : E3, nu23, nu13, alpha3, beta3 (accepted as inputs but have no effect, because sigma_z is
               eliminated and eps_z is not part of the kinematics; checked in --selftest).
  No transverse-normal stress or strain, and no through-thickness thermal/moisture expansion, is computed.
- Normalization (w_bar, K0, J0) uses D = E*h^3/[12(1-nu^2)] for an isotropic plate and the laminate bending
  stiffness D11 = sum_k Q11_k (z_k+1^3 - z_k^3)/3 of the whole stack for a laminate (a stated convention:
  a laminate has no unique flexural rigidity). Dimensional results do not depend on it.
- Supports 6 boundary-condition configurations.
- Supports mechanical pressure, optional thermal loading (t1, t2, t3), optional moisture loading
  (c1, c2, c3, beta), Winkler/Pasternak elastic foundations, and discrete nodal or patch Vehicle loads.
- Outputs dimensional displacements/stresses, normalized parameters, and stiffness matrix diagnostics.
- `--validate [mesh]` prints the comparison with the paper (Table 2 and Table 3, ceramic);
  `--selftest` runs the regression checks. Neither is part of the interactive flow.
"""
from __future__ import annotations

import csv
import math
import os
import sys
import time
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import MatrixRankWarning, spsolve

# ============================================================================
# 1. CONSTANTS & DATA STRUCTURES
# ============================================================================
DOF = 12
U, V, W, T1, T2, T3, US, VS, WS, T1S, T2S, T3S = range(12)

BOUNDARY_CONDITIONS: Dict[int, str] = {
    1: "Simply supported on all four sides (SSSS)",
    2: "Clamped on all four sides (CCCC)",
    3: "Simply supported at x=0,a; Free at y=0,b (SFSF)",
    4: "Simply supported at y=0,b; Free at x=0,a (FSFS)",
    5: "Simply supported at x=0,a; Clamped at y=0,b (SCSC)",
    6: "Simply supported at y=0,b; Clamped at x=0,a (CSCS)",
}


@dataclass
class LayerProperty:
    """Single layer material and thickness definition (all properties supplied by the user).

    E1, E2, nu12, G12, G13, G23, alpha1, alpha2, beta1, beta2 enter the plane-stress (sigma_z = 0) laminate
    model. E3, nu23, nu13, alpha3 and beta3 complete the 3D orthotropic description but are mathematically
    inert here: eliminating sigma_z leaves the in-plane stiffness independent of them, and eps_z is not
    part of the kinematics. They are kept as inputs for completeness."""
    h_bottom: float
    h_top: float
    E1: float
    E2: float
    E3: float
    nu12: float
    nu23: float
    nu13: float
    G12: float
    G13: float
    G23: float
    theta_rad: float = 0.0
    alpha1: float = 0.0
    alpha2: float = 0.0
    alpha3: float = 0.0
    beta1: float = 0.0
    beta2: float = 0.0
    beta3: float = 0.0


@dataclass
class VehicleLoad:
    """Discrete nodal vertical loads or rectangular wheel patch loads."""
    nodal_loads: List[Tuple[int, float]] = field(default_factory=list)
    wheel_patches: List[Tuple[float, float, float, float, float]] = field(default_factory=list)


# ============================================================================
# 2. Q8 SHAPE FUNCTIONS & STRAIN-DISPLACEMENT MATRICES
# ============================================================================
def shape_q8(xi: float, eta: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Clockwise 8-node Q8 shape functions and natural derivatives."""
    x, y = xi, eta
    N = np.array([
        0.25 * (1 - x) * (1 + y) * (-x + y - 1),
        0.50 * (1 - x * x) * (1 + y),
        0.25 * (1 + x) * (1 + y) * (x + y - 1),
        0.50 * (1 + x) * (1 - y * y),
        0.25 * (1 + x) * (1 - y) * (x - y - 1),
        0.50 * (1 - x * x) * (1 - y),
        0.25 * (1 - x) * (1 - y) * (-x - y - 1),
        0.50 * (1 - x) * (1 - y * y),
    ], dtype=float)

    dxi = np.array([
        0.25 * (1 + y) * (2 * x - y),
        -x * (1 + y),
        0.25 * (1 + y) * (2 * x + y),
        0.50 * (1 - y * y),
        0.25 * (1 - y) * (2 * x - y),
        -x * (1 - y),
        0.25 * (1 - y) * (2 * x + y),
        -0.50 * (1 - y * y),
    ], dtype=float)

    deta = np.array([
        0.25 * (1 - x) * (2 * y - x),
        0.50 * (1 - x * x),
        0.25 * (1 + x) * (x + 2 * y),
        -(1 + x) * y,
        0.25 * (1 + x) * (2 * y - x),
        -0.50 * (1 - x * x),
        0.25 * (1 - x) * (x + 2 * y),
        -(1 - x) * y,
    ], dtype=float)
    return N, dxi, deta


def shape_q8_second(xi: float, eta: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Second natural-coordinate derivatives of Q8 shape functions."""
    x, y = xi, eta
    dxx = np.array([
        0.5 * (1 + y), -(1 + y), 0.5 * (1 + y), 0.0,
        0.5 * (1 - y), -(1 - y), 0.5 * (1 - y), 0.0,
    ], dtype=float)
    dyy = np.array([
        0.5 * (1 - x), 0.0, 0.5 * (1 + x), -(1 + x),
        0.5 * (1 + x), 0.0, 0.5 * (1 - x), -(1 - x),
    ], dtype=float)
    dxy = np.array([
        0.25 * (2 * x - 2 * y - 1), -x, 0.25 * (2 * x + 2 * y + 1), -y,
        -0.25 * (2 * x - 2 * y + 1), x, -0.25 * (2 * x + 2 * y - 1), y,
    ], dtype=float)
    return dxx, dyy, dxy


def element_geometry(coords_e: np.ndarray, xi: float, eta: float):
    """Evaluate Q8 shape functions, physical derivatives, and Jacobian determinant."""
    N, dxi, deta = shape_q8(xi, eta)
    J = np.array([
        [np.dot(dxi, coords_e[:, 0]), np.dot(dxi, coords_e[:, 1])],
        [np.dot(deta, coords_e[:, 0]), np.dot(deta, coords_e[:, 1])],
    ], dtype=float)
    detJ = abs(float(np.linalg.det(J)))
    if detJ <= 1e-16:
        raise ValueError(f"Invalid element Jacobian: detJ={detJ}")
    invJ = np.linalg.inv(J)
    grads = invJ @ np.vstack((dxi, deta))
    return N, grads[0], grads[1], detJ


def patch_load_vector(ce: np.ndarray, patches) -> np.ndarray:
    """Equivalent nodal vector (8,) of rectangular patch pressures acting on one rectangular Q8 element.

    Each patch (xc, yc, dx, dy, F) carries the uniform pressure F/(dx*dy). The pressure is integrated over the
    exact overlap of the patch with the element (3x3 Gauss on the overlap), so the applied load equals F
    whatever the mesh, including patch edges that cut through elements."""
    gpts, gwts = np.polynomial.legendre.leggauss(3)
    x0, x1 = ce[:, 0].min(), ce[:, 0].max()
    y0, y1 = ce[:, 1].min(), ce[:, 1].max()
    out = np.zeros(8, dtype=float)
    for xc, yc, dx_p, dy_p, F_wheel in patches:
        lx0, lx1 = max(x0, xc - 0.5 * dx_p), min(x1, xc + 0.5 * dx_p)
        ly0, ly1 = max(y0, yc - 0.5 * dy_p), min(y1, yc + 0.5 * dy_p)
        if lx1 <= lx0 or ly1 <= ly0:
            continue
        pressure = F_wheel / (dx_p * dy_p)
        hx, hy = 0.5 * (lx1 - lx0), 0.5 * (ly1 - ly0)
        for u, wu in zip(gpts, gwts):
            for v, wv in zip(gpts, gwts):
                xp, yp = 0.5 * (lx0 + lx1) + hx * u, 0.5 * (ly0 + ly1) + hy * v
                N, _, _ = shape_q8(2.0 * (xp - x0) / (x1 - x0) - 1.0, 2.0 * (yp - y0) / (y1 - y0) - 1.0)
                out += N * pressure * wu * wv * hx * hy
    return out


def b_matrices(N: np.ndarray, dNdx: np.ndarray, dNdy: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Construct HOSNT12 bending/normal (15x96) and transverse shear (8x96) B-matrices."""
    Bb = np.zeros((15, 8 * DOF), dtype=float)
    Bs = np.zeros((8, 8 * DOF), dtype=float)
    for k in range(8):
        c = k * DOF
        # z^0
        Bb[0, c + U] = dNdx[k]
        Bb[1, c + V] = dNdy[k]
        Bb[2, c + T3] = N[k]
        Bb[3, c + U] = dNdy[k]
        Bb[3, c + V] = dNdx[k]
        # z^1
        Bb[4, c + T1] = dNdx[k]
        Bb[5, c + T2] = dNdy[k]
        Bb[6, c + WS] = 2.0 * N[k]
        Bb[7, c + T1] = dNdy[k]
        Bb[7, c + T2] = dNdx[k]
        # z^2
        Bb[8, c + US] = dNdx[k]
        Bb[9, c + VS] = dNdy[k]
        Bb[10, c + T3S] = 3.0 * N[k]
        Bb[11, c + US] = dNdy[k]
        Bb[11, c + VS] = dNdx[k]
        # z^3
        Bb[12, c + T1S] = dNdx[k]
        Bb[13, c + T2S] = dNdy[k]
        Bb[14, c + T1S] = dNdy[k]
        Bb[14, c + T2S] = dNdx[k]

        # Transverse shear z^0..z^3
        Bs[0, c + W] = dNdx[k]
        Bs[0, c + T1] = N[k]
        Bs[1, c + W] = dNdy[k]
        Bs[1, c + T2] = N[k]

        Bs[2, c + T3] = dNdx[k]
        Bs[2, c + US] = 2.0 * N[k]
        Bs[3, c + T3] = dNdy[k]
        Bs[3, c + VS] = 2.0 * N[k]

        Bs[4, c + WS] = dNdx[k]
        Bs[4, c + T1S] = 3.0 * N[k]
        Bs[5, c + WS] = dNdy[k]
        Bs[5, c + T2S] = 3.0 * N[k]

        Bs[6, c + T3S] = dNdx[k]
        Bs[7, c + T3S] = dNdy[k]
    return Bb, Bs


# ============================================================================
# 3. MESH GENERATION
# ============================================================================
def build_mesh(a: float, b: float, m: int, n: int):
    """Generate structured Q8 mesh with bottom-to-top row numbering."""
    xs = np.linspace(0.0, a, 2 * m + 1)
    ys = np.linspace(0.0, b, 2 * n + 1)
    node_map: Dict[Tuple[int, int], int] = {}
    coords = []
    for j in range(2 * n + 1):
        for i in range(2 * m + 1):
            if i % 2 == 1 and j % 2 == 1:
                continue
            node_map[(i, j)] = len(coords)
            coords.append((xs[i], ys[j]))
    coords_arr = np.asarray(coords, dtype=float)

    elements = []
    for ey in range(n):
        for ex in range(m):
            i, j = 2 * ex, 2 * ey
            elements.append([
                node_map[(i, j + 2)],     # Node 1: top-left
                node_map[(i + 1, j + 2)], # Node 2: top-mid
                node_map[(i + 2, j + 2)], # Node 3: top-right
                node_map[(i + 2, j + 1)], # Node 4: right-mid
                node_map[(i + 2, j)],     # Node 5: bottom-right
                node_map[(i + 1, j)],     # Node 6: bottom-mid
                node_map[(i, j)],         # Node 7: bottom-left
                node_map[(i, j + 1)],     # Node 8: left-mid
            ])
    return coords_arr, np.asarray(elements, dtype=int), node_map


# ============================================================================
# 4. CONSTITUTIVE MATRICES & STIFFNESS MOMENTS
# ============================================================================
def _expansion_vector(v1: float, v2: float, v3: float, c: float, s: float) -> np.ndarray:
    """Rotate principal thermal/moisture expansion coefficients into plate axes (x, y, z, xy)."""
    c2, s2 = c * c, s * s
    return np.array([v1 * c2 + v2 * s2, v1 * s2 + v2 * c2, v3, 2.0 * (v1 - v2) * s * c], dtype=float)


def orthotropic_layer_matrices(layer: LayerProperty) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Rotated plane-stress (sigma_z = 0) 4x4 bending/normal matrix, 2x2 shear matrix, thermal and moisture
    expansion vectors of one layer."""
    E1, E2 = layer.E1, layer.E2
    nu12 = layer.nu12
    G12, G13, G23 = layer.G12, layer.G13, layer.G23

    nu21 = nu12 * E2 / E1
    denom = 1.0 - nu12 * nu21
    Q11 = E1 / denom
    Q22 = E2 / denom
    Q12 = nu12 * E2 / denom
    Q13 = Q23 = Q33 = 0.0

    Q44, Q55, Q66 = G12, G13, G23
    c, s = math.cos(layer.theta_rad), math.sin(layer.theta_rad)
    c2, s2 = c * c, s * s
    c4, s4 = c2 * c2, s2 * s2

    Q11r = Q11 * c4 + 2.0 * (Q12 + 2.0 * Q44) * s2 * c2 + Q22 * s4
    Q12r = (Q11 + Q22 - 4.0 * Q44) * s2 * c2 + Q12 * (s4 + c4)
    Q22r = Q11 * s4 + 2.0 * (Q12 + 2.0 * Q44) * s2 * c2 + Q22 * c4
    Q13r = Q13 * c2 + Q23 * s2
    Q23r = Q23 * c2 + Q13 * s2
    Q33r = Q33
    Q14r = (Q11 - Q12 - 2.0 * Q44) * s * (c ** 3) + (Q12 - Q22 + 2.0 * Q44) * (s ** 3) * c
    Q24r = (Q11 - Q12 - 2.0 * Q44) * (s ** 3) * c + (Q12 - Q22 + 2.0 * Q44) * s * (c ** 3)
    Q34r = (Q13 - Q23) * c * s
    Q44r = (Q11 + Q22 - 2.0 * Q12 - 2.0 * Q44) * s2 * c2 + Q44 * (c4 + s4)

    Q55r = Q55 * c2 + Q66 * s2
    Q56r = (Q55 - Q66) * c * s
    Q66r = Q66 * c2 + Q55 * s2

    Cb = np.array([
        [Q11r, Q12r, Q13r, Q14r],
        [Q12r, Q22r, Q23r, Q24r],
        [Q13r, Q23r, Q33r, Q34r],
        [Q14r, Q24r, Q34r, Q44r],
    ], dtype=float)
    Cs = np.array([
        [Q55r, Q56r],
        [Q56r, Q66r],
    ], dtype=float)

    alpha_vec = _expansion_vector(layer.alpha1, layer.alpha2, layer.alpha3, c, s)
    beta_vec = _expansion_vector(layer.beta1, layer.beta2, layer.beta3, c, s)
    return Cb, Cs, alpha_vec, beta_vec


PRESET_LAMINATE_PROPERTIES: Dict[str, float] = dict(
    E1=181e9, E2=10.3e9, E3=10.3e9,
    nu12=0.28, nu23=0.28, nu13=0.28,
    G12=7.17e9, G13=7.17e9, G23=2.39e9,
    alpha1=0.0, alpha2=0.006, alpha3=0.0,
    beta1=0.0, beta2=0.0, beta3=0.0,
)


def default_three_layer_laminate(h: float, **properties: float) -> List[LayerProperty]:
    """3-layer [0 / 90 / 0] orthotropic laminate (outer layers 0.33 h, core 0.34 h).

    The ply properties start from PRESET_LAMINATE_PROPERTIES; any LayerProperty property (E1, E2, E3, nu12,
    nu23, nu13, G12, G13, G23, alpha1-3, beta1-3) may be overridden by keyword."""
    unknown = set(properties) - set(PRESET_LAMINATE_PROPERTIES)
    if unknown:
        raise ValueError(f"Unknown laminate properties: {sorted(unknown)}")
    ply = {**PRESET_LAMINATE_PROPERTIES, **properties}
    interfaces = [
        (0.17 * h, 0.50 * h, 0.0),
        (-0.17 * h, 0.17 * h, math.pi / 2.0),
        (-0.50 * h, -0.17 * h, 0.0),
    ]
    return [LayerProperty(h_bottom=h1, h_top=h2, theta_rad=th, **ply) for h1, h2, th in interfaces]


def validate_layer(lyr: LayerProperty) -> None:
    """Physical admissibility of one orthotropic layer."""
    vals = [lyr.h_bottom, lyr.h_top, lyr.E1, lyr.E2, lyr.E3, lyr.nu12, lyr.nu23, lyr.nu13, lyr.G12, lyr.G13,
            lyr.G23, lyr.theta_rad, lyr.alpha1, lyr.alpha2, lyr.alpha3, lyr.beta1, lyr.beta2, lyr.beta3]
    if not all(np.isfinite(vals)):
        raise ValueError("Layer properties must be finite.")
    if min(lyr.E1, lyr.E2, lyr.E3, lyr.G12, lyr.G13, lyr.G23) <= 0.0:
        raise ValueError("Layer moduli E1, E2, E3, G12, G13, G23 must be positive.")
    if lyr.h_top <= lyr.h_bottom:
        raise ValueError("Layer h_top must exceed h_bottom.")
    if lyr.nu12 ** 2 >= lyr.E1 / lyr.E2:
        raise ValueError("Layer Poisson ratio nu12 violates nu12*nu21 < 1.")


def layer_at_z(layers: List[LayerProperty], zp: float) -> LayerProperty:
    """Layer containing thickness coordinate zp (top layer when zp lies outside every layer)."""
    for cand in layers:
        if cand.h_bottom - 1e-12 <= zp <= cand.h_top + 1e-12:
            return cand
    return layers[-1]


def material_at_z(
    material_mode: str,
    E: Optional[float],
    nu: Optional[float],
    alpha: float,
    beta: float,
    layer: Optional[LayerProperty] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Plane-stress constitutive matrices (Cb, Cs) and thermal/moisture expansion vectors of the material
    (isotropic, or the given laminate layer) at one thickness coordinate."""
    if material_mode == "laminate":
        return orthotropic_layer_matrices(layer)
    mu = E / (2.0 * (1.0 + nu))
    q = E / (1.0 - nu ** 2)
    Cb = np.array([
        [q, nu * q, 0.0, 0.0],
        [nu * q, q, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, mu],
    ], dtype=float)
    Cs = np.array([[mu, 0.0], [0.0, mu]], dtype=float)
    return (Cb, Cs,
            np.array([alpha, alpha, alpha, 0.0], dtype=float),
            np.array([beta, beta, beta, 0.0], dtype=float))


def environmental_profile(z: float, h: float, coeffs: Optional[Tuple[float, float, float]]) -> float:
    """Through-thickness temperature or moisture-concentration change (Zidi et al. 2014):
    X(z) = x1 + (z/h) x2 + (1/pi) sin(pi z / h) x3, multiplied in-plane by sin(pi x/a) sin(pi y/b)."""
    if coeffs is None:
        return 0.0
    return coeffs[0] + (z / h) * coeffs[1] + math.sin(math.pi * z / h) / math.pi * coeffs[2]


def compute_stiffness_and_environment_resultants(
    h: float,
    material_mode: str = "isotropic",
    E: Optional[float] = None,
    nu: Optional[float] = None,
    alpha: float = 0.0,
    beta: float = 0.0,
    layers: Optional[List[LayerProperty]] = None,
    t_coeffs: Optional[Tuple[float, float, float]] = None,
    c_coeffs: Optional[Tuple[float, float, float]] = None,
):
    """Integrate generalized stiffness matrices Db (15x15), Ds (8x8) and the equivalent environmental
    (thermal + hygroscopic) force vector (15,) from sigma = Q (eps - alpha T - beta C).

    The environmental vector carries only the through-thickness integrals; the solver multiplies it by the
    in-plane variation sin(pi x/a) sin(pi y/b)."""
    if material_mode == "laminate":
        active_layers = layers if layers else default_three_layer_laminate(h)
    elif material_mode == "isotropic":
        active_layers = []
    else:
        raise ValueError("material_mode must be 'isotropic' or 'laminate'.")

    active = [[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 3]]
    sizes = [4, 4, 4, 3]
    starts = np.cumsum([0] + sizes)

    M = [np.zeros((4, 4), dtype=float) for _ in range(7)]
    S = [np.zeros((2, 2), dtype=float) for _ in range(7)]
    env_resultants = np.zeros(15, dtype=float)

    zeta, weights = np.polynomial.legendre.leggauss(10)
    if material_mode == "laminate":
        segments = [(0.5 * (lyr.h_top + lyr.h_bottom), 0.5 * (lyr.h_top - lyr.h_bottom), lyr)
                    for lyr in active_layers]
    else:
        segments = [(0.0, 0.5 * h, None)]

    for z_mid, z_half, lyr in segments:
        Cb, Cs, alpha_vec, beta_vec = material_at_z(material_mode, E, nu, alpha, beta, lyr)
        for xi_g, w_g in zip(zeta, weights):
            z = z_mid + z_half * xi_g
            wz = z_half * w_g
            for k in range(7):
                zk = wz * (z ** k)
                M[k] += zk * Cb
                S[k] += zk * Cs
            if t_coeffs is not None or c_coeffs is not None:
                eps_env = (alpha_vec * environmental_profile(z, h, t_coeffs)
                           + beta_vec * environmental_profile(z, h, c_coeffs))
                sig_env = Cb @ eps_env
                for order, inds in enumerate(active):
                    env_resultants[starts[order]:starts[order + 1]] += wz * (z ** order) * sig_env[inds]

    Db = np.zeros((15, 15), dtype=float)
    for i, inds_i in enumerate(active):
        for j, inds_j in enumerate(active):
            Db[starts[i]:starts[i + 1], starts[j]:starts[j + 1]] = M[i + j][np.ix_(inds_i, inds_j)]

    Ds = np.zeros((8, 8), dtype=float)
    for i in range(4):
        for j in range(4):
            Ds[2 * i:2 * i + 2, 2 * j:2 * j + 2] = S[i + j]

    return Db, Ds, env_resultants, active_layers


def reference_flexural_rigidity(
    h: float,
    material_mode: str,
    E: Optional[float] = None,
    nu: Optional[float] = None,
    layers: Optional[List[LayerProperty]] = None,
) -> Tuple[float, float]:
    """Reference flexural rigidities (D_x, D_y) in N*m used for w_bar and for the K0/J0 foundation conversion.

    isotropic : D_x = D_y = E h^3 / [12 (1 - nu^2)]                      (the definition of the reference paper)
    laminate  : D_x = D11 = sum_k Q11_k (z_k+1^3 - z_k^3) / 3 and D_y = D22 likewise, i.e. the classical
                laminate bending stiffnesses of the stacking sequence (rotated plane-stress Q of every ply
                integrated through the thickness). D11 is the bending rigidity for curvature along x (the
                span a). A laminate has no single flexural rigidity, so this is a stated convention; it
                reduces exactly to the isotropic D when every ply is isotropic."""
    if material_mode == "isotropic":
        d = E * h ** 3 / (12.0 * (1.0 - nu ** 2))
        return d, d
    stack = layers if layers else default_three_layer_laminate(h)
    d11 = d22 = 0.0
    for lyr in stack:
        cb = orthotropic_layer_matrices(lyr)[0]
        third = (lyr.h_top ** 3 - lyr.h_bottom ** 3) / 3.0
        d11 += cb[0, 0] * third
        d22 += cb[1, 1] * third
    return d11, d22


# ============================================================================
# 5. BOUNDARY CONDITIONS (12-DOF Mapping)
# ============================================================================
def constrained_dofs(coords: np.ndarray, a: float, b: float, choicebc: int = 1, tol: float = 1e-9) -> np.ndarray:
    """Resolve constrained global DOF indices for the selected boundary condition (1-6)."""
    x0 = np.where(np.abs(coords[:, 0]) <= tol)[0]
    xa = np.where(np.abs(coords[:, 0] - a) <= tol)[0]
    y0 = np.where(np.abs(coords[:, 1]) <= tol)[0]
    yb = np.where(np.abs(coords[:, 1] - b) <= tol)[0]

    x_ss = (V, W, T2, T3, VS, WS, T2S, T3S)
    y_ss = (U, W, T1, T3, US, WS, T1S, T3S)
    all_dofs = tuple(range(DOF))
    fixed = set()

    def add(nodes, dofs):
        for node in nodes:
            base = int(node) * DOF
            fixed.update(base + int(dof) for dof in dofs)

    if choicebc == 1:  # SSSS
        for edge in (x0, xa):
            add(edge, x_ss)
        for edge in (y0, yb):
            add(edge, y_ss)
    elif choicebc == 2:  # CCCC
        for edge in (x0, xa, y0, yb):
            add(edge, all_dofs)
    elif choicebc == 3:  # SFSF
        for edge in (x0, xa):
            add(edge, x_ss)
        bl_corner = int(np.argmin(coords[:, 0] ** 2 + coords[:, 1] ** 2))
        tl_corner = int(np.argmin(coords[:, 0] ** 2 + (coords[:, 1] - b) ** 2))
        add([bl_corner, tl_corner], [U, US])
    elif choicebc == 4:  # FSFS
        for edge in (y0, yb):
            add(edge, y_ss)
        bl_corner = int(np.argmin(coords[:, 0] ** 2 + coords[:, 1] ** 2))
        br_corner = int(np.argmin((coords[:, 0] - a) ** 2 + coords[:, 1] ** 2))
        add([bl_corner, br_corner], [V, VS])
    elif choicebc == 5:  # SCSC
        for edge in (x0, xa):
            add(edge, x_ss)
        for edge in (y0, yb):
            add(edge, all_dofs)
    elif choicebc == 6:  # CSCS
        for edge in (y0, yb):
            add(edge, y_ss)
        for edge in (x0, xa):
            add(edge, all_dofs)
    else:
        raise ValueError("Boundary condition choice must be from 1 to 6.")

    # Plate kinematics of the reference (TSDT, Zidi et al. 2014): w is constant through the thickness
    # (eps_z = 0), so the thickness-stretching DOFs theta3, w0*, theta3* are zero at every node.
    add(range(coords.shape[0]), (T3, WS, T3S))

    return np.array(sorted(fixed), dtype=int)


# ============================================================================
# 6. SOLVER & POST-PROCESSING
# ============================================================================
def solve_hosnt12(
    a: float = 1.0,
    b: float = 3.0,
    h: float = 0.1,
    m: int = 10,
    n: int = 10,
    material_mode: str = "isotropic",
    E: Optional[float] = None,
    nu: Optional[float] = None,
    q0: float = 100.0,
    nonlocal_parameter: float = 0.0,
    load_case: str = "sinusoidal",
    choicebc: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    t_coeffs: Optional[Sequence[float]] = None,
    c_coeffs: Optional[Sequence[float]] = None,
    Kw: float = 0.0,
    Kp: float = 0.0,
    vehicle_load: Optional[VehicleLoad] = None,
    layers: Optional[List[LayerProperty]] = None,
    Kp_y: Optional[float] = None,
    K0: Optional[float] = None,
    J0: Optional[float] = None,
) -> Dict:
    """Assemble and solve the HOSNT12 finite-element system for a single boundary condition.

    Material (no default material is assumed): material_mode='isotropic' needs E, nu and, for environmental
    loading, alpha (thermal) and beta (moisture expansion); material_mode='laminate' takes `layers`
    (LayerProperty list with E1-3, nu12/23/13, G12/13/23 and directional alpha1-3, beta1-3) or the
    default [0/90/0] preset. A zero alpha or beta means no thermal or moisture strain.

    Foundation: dimensional Kw (N/m^3), Kp (N/m) acting on d/dx and Kp_y (N/m) acting on d/dy
    (Kp_y defaults to Kp). Alternatively give the dimensionless parameters K0, J0 used in the
    reference paper (Zidi et al. 2014), which are converted as
        Kw = K0 * D / a^4,   Kp = J0 * D / a^2,   Kp_y = J0 * D / b^2,
    with D = E h^3 / [12 (1 - nu^2)] for an isotropic plate and D = D11 (the laminate bending stiffness
    sum_k Q11_k (z_k+1^3 - z_k^3)/3 of the whole stack, see reference_flexural_rigidity) for a laminate. The
    same D normalizes w_bar. Dimensional outputs never depend on this choice.

    Environmental loading (optional): t_coeffs = (t1, t2, t3) is the temperature change and c_coeffs =
    (c1, c2, c3) the moisture-concentration change,
        X(x, y, z) = [x1 + (z/h) x2 + (1/pi) sin(pi z/h) x3] sin(pi x/a) sin(pi y/b)
    (Zidi et al. 2014, Eq. 25). The thermal and hygroscopic strains are alpha*T and beta*C and enter the
    stress as sigma = Q (eps - alpha T - beta C), both in the load vector and in stress recovery.
    """
    if t_coeffs is not None:
        t_coeffs = tuple(float(v) for v in t_coeffs)
    if c_coeffs is not None:
        c_coeffs = tuple(float(v) for v in c_coeffs)
    for name, coeffs in (("t_coeffs", t_coeffs), ("c_coeffs", c_coeffs)):
        if coeffs is not None and (len(coeffs) != 3 or not all(np.isfinite(coeffs))):
            raise ValueError(f"{name} must be three finite numbers ({name[0]}1, {name[0]}2, {name[0]}3).")
    if K0 is not None or J0 is not None:
        Kw = Kp = 0.0
        Kp_y = None
    if Kp_y is None:
        Kp_y = Kp
    if material_mode == "isotropic":
        if E is None or nu is None:
            raise ValueError("Isotropic material requires E and nu; no default material is assumed.")
        iso_values = [E, nu]
    elif material_mode == "laminate":
        iso_values = []
    else:
        raise ValueError("material_mode must be 'isotropic' or 'laminate'.")
    numeric = [a, b, h, q0, nonlocal_parameter, alpha, beta, Kw, Kp, Kp_y] + iso_values
    if K0 is not None:
        numeric.append(K0)
    if J0 is not None:
        numeric.append(J0)
    if not all(np.isfinite(v) for v in numeric):
        raise ValueError("All numeric inputs must be finite.")
    if min(a, b, h) <= 0 or m < 1 or n < 1:
        raise ValueError("Plate dimensions and mesh counts must be positive.")
    if material_mode == "isotropic":
        if E <= 0:
            raise ValueError("Young's modulus E must be positive.")
        if not (-0.99 < nu < 0.4999):
            raise ValueError("Poisson ratio must satisfy -0.99 < nu < 0.4999.")
    if q0 < 0 or nonlocal_parameter < 0 or Kw < 0 or Kp < 0 or Kp_y < 0:
        raise ValueError("q0, nonlocal_parameter, Kw, and Kp must be non-negative.")
    if (K0 is not None and K0 < 0) or (J0 is not None and J0 < 0):
        raise ValueError("K0 and J0 must be non-negative.")

    coords, elements, _ = build_mesh(a, b, int(m), int(n))
    Db, Ds, env_resultants, active_layers = compute_stiffness_and_environment_resultants(
        h=h, material_mode=material_mode, E=E, nu=nu, alpha=alpha, beta=beta, layers=layers,
        t_coeffs=t_coeffs, c_coeffs=c_coeffs,
    )

    for lyr in active_layers:
        validate_layer(lyr)

    extra_warnings: List[str] = []
    for field_name, coeffs, label, lay_attrs, iso_value in (
            ("Temperature", t_coeffs, "thermal expansion", ("alpha1", "alpha2"), alpha),
            ("Moisture", c_coeffs, "moisture expansion", ("beta1", "beta2"), beta)):
        if coeffs is not None and any(coeffs):
            values = ([getattr(lyr, at) for lyr in active_layers for at in lay_attrs]
                      if material_mode == "laminate" else [iso_value])
            if not any(values):
                extra_warnings.append(f"{field_name} field given but every {label} coefficient is zero; "
                                      f"it has no effect.")
    if vehicle_load and vehicle_load.wheel_patches:
        for xc, yc, dx_p, dy_p, _ in vehicle_load.wheel_patches:
            inside = (max(0.0, min(a, xc + 0.5 * dx_p) - max(0.0, xc - 0.5 * dx_p))
                      * max(0.0, min(b, yc + 0.5 * dy_p) - max(0.0, yc - 0.5 * dy_p)))
            if inside < (1.0 - 1e-9) * dx_p * dy_p:
                extra_warnings.append("A wheel patch extends beyond the plate; only the part on the plate is loaded.")

    # Reference rigidity for w_bar and for K0/J0 -> Kw/Kp: E h^3/[12(1-nu^2)] for an isotropic plate and the
    # laminate bending stiffness D11 of the whole stack for a laminate (no first-ply property is used).
    flexural_rigidity, flexural_rigidity_y = reference_flexural_rigidity(h, material_mode, E, nu, active_layers)

    if K0 is not None or J0 is not None:
        Kw = (K0 or 0.0) * flexural_rigidity / (a ** 4)
        Kp = (J0 or 0.0) * flexural_rigidity / (a ** 2)
        Kp_y = (J0 or 0.0) * flexural_rigidity / (b ** 2)

    gp3, gw3 = np.polynomial.legendre.leggauss(3)
    gp2, gw2 = np.polynomial.legendre.leggauss(2)

    ndof = coords.shape[0] * DOF
    rows, cols, vals = [], [], []
    Fglob = np.zeros(ndof, dtype=float)
    t0 = time.perf_counter()

    local_w_dofs = np.arange(8) * DOF + W

    for el in elements:
        ce = coords[el]
        edofs = (el[:, None] * DOF + np.arange(DOF)).reshape(-1)
        Ke = np.zeros((8 * DOF, 8 * DOF), dtype=float)
        Fe = np.zeros(8 * DOF, dtype=float)
        if vehicle_load and vehicle_load.wheel_patches:
            Fe[local_w_dofs] += patch_load_vector(ce, vehicle_load.wheel_patches)

        for xi, wx in zip(gp3, gw3):
            for eta, wy in zip(gp3, gw3):
                N, dNx, dNy, detJ = element_geometry(ce, xi, eta)
                Bb, _ = b_matrices(N, dNx, dNy)
                dA = wx * wy * detJ
                Ke += (Bb.T @ Db @ Bb) * dA

                xgp = float(N @ ce[:, 0])
                ygp = float(N @ ce[:, 1])
                spatial = math.sin(math.pi * xgp / a) * math.sin(math.pi * ygp / b)

                if q0 > 0.0:
                    pressure = q0 if load_case == "uniform" else q0 * spatial
                    d2xi, d2eta, _ = shape_q8_second(xi, eta)
                    d2Ndx2 = d2xi * (2.0 / (a / m)) ** 2
                    d2Ndy2 = d2eta * (2.0 / (b / n)) ** 2
                    load_shape = N - nonlocal_parameter * (d2Ndx2 + d2Ndy2)
                    Fe[local_w_dofs] += load_shape * pressure * dA

                if np.any(env_resultants):
                    Fe += (Bb.T @ env_resultants) * (spatial * dA)

                if Kw > 0.0 or Kp > 0.0 or Kp_y > 0.0:
                    Kf = Kw * np.outer(N, N) + Kp * np.outer(dNx, dNx) + Kp_y * np.outer(dNy, dNy)
                    Ke[np.ix_(local_w_dofs, local_w_dofs)] += Kf * dA

        for xi, wx in zip(gp2, gw2):
            for eta, wy in zip(gp2, gw2):
                N, dNx, dNy, detJ = element_geometry(ce, xi, eta)
                _, Bs = b_matrices(N, dNx, dNy)
                Ke += (Bs.T @ Ds @ Bs) * (wx * wy * detJ)

        rr, cc = np.meshgrid(edofs, edofs, indexing="ij")
        rows.extend(rr.ravel().tolist())
        cols.extend(cc.ravel().tolist())
        vals.extend(Ke.ravel().tolist())
        np.add.at(Fglob, edofs, Fe)

    if vehicle_load and vehicle_load.nodal_loads:
        for node_1based, f_val in vehicle_load.nodal_loads:
            node_idx = int(node_1based) - 1
            if 0 <= node_idx < coords.shape[0]:
                Fglob[node_idx * DOF + W] += float(f_val)

    K = coo_matrix((vals, (rows, cols)), shape=(ndof, ndof)).tocsr()
    K.sum_duplicates()

    tol = max(a, b, 1.0) * 1e-9
    fixed = constrained_dofs(coords, a, b, choicebc=choicebc, tol=tol)
    free = np.setdiff1d(np.arange(ndof), fixed, assume_unique=True)
    K_free = K[free][:, free]

    with warnings.catch_warnings(record=True) as warns:
        warnings.simplefilter("always", MatrixRankWarning)
        uf = np.zeros(ndof, dtype=float)
        uf[free] = spsolve(K_free, Fglob[free])

    if not np.all(np.isfinite(uf)):
        raise RuntimeError("Non-finite solution; reduced stiffness matrix may be singular.")
    elapsed = time.perf_counter() - t0

    # Stiffness matrix diagnostics
    diag_K = K.diagonal()
    sym_diff = K - K.T
    max_asym = float(np.max(np.abs(sym_diff.data))) if sym_diff.nnz > 0 else 0.0

    def find_elements_at(xp: float, yp: float):
        """All elements containing the point (several when it lies on a shared edge or node)."""
        candidates = []
        for ei, el in enumerate(elements):
            ce = coords[el]
            if (ce[:, 0].min() - 1e-9 <= xp <= ce[:, 0].max() + 1e-9 and
                    ce[:, 1].min() - 1e-9 <= yp <= ce[:, 1].max() + 1e-9):
                candidates.append((ei, el, ce))
        if not candidates:
            raise ValueError(f"No element contains point {(xp, yp)}.")
        return candidates

    def natural_coordinates(ce: np.ndarray, xp: float, yp: float) -> Tuple[float, float]:
        xmin, xmax = ce[:, 0].min(), ce[:, 0].max()
        ymin, ymax = ce[:, 1].min(), ce[:, 1].max()
        xi = 2.0 * (xp - xmin) / (xmax - xmin) - 1.0
        eta = 2.0 * (yp - ymin) / (ymax - ymin) - 1.0
        return float(xi), float(eta)

    def constitutive_at_z(zp: float):
        lyr = layer_at_z(active_layers, zp) if material_mode == "laminate" else None
        return material_at_z(material_mode, E, nu, alpha, beta, lyr)

    def element_strains(ce: np.ndarray, ue: np.ndarray, xi: float, eta: float, zp: float):
        """In-plane/normal strains (4) and transverse shear strains (2) at (xi, eta, z) of one element."""
        N, dNx, dNy, _ = element_geometry(ce, xi, eta)
        Bb, Bs = b_matrices(N, dNx, dNy)
        gp = Bb @ ue
        strain4 = np.array([
            gp[0] + zp * gp[4] + (zp ** 2) * gp[8] + (zp ** 3) * gp[12],
            gp[1] + zp * gp[5] + (zp ** 2) * gp[9] + (zp ** 3) * gp[13],
            gp[2] + zp * gp[6] + (zp ** 2) * gp[10],
            gp[3] + zp * gp[7] + (zp ** 2) * gp[11] + (zp ** 3) * gp[14],
        ], dtype=float)
        sh = Bs @ ue
        shear_strain = np.array([
            sh[0] + zp * sh[2] + (zp ** 2) * sh[4] + (zp ** 3) * sh[6],
            sh[1] + zp * sh[3] + (zp ** 2) * sh[5] + (zp ** 3) * sh[7],
        ], dtype=float)
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

    def evaluate_point(xp: float, yp: float, zp: float):
        Cb, Cs, alpha_vec, beta_vec = constitutive_at_z(zp)
        spatial = math.sin(math.pi * xp / a) * math.sin(math.pi * yp / b)
        temp_pt = environmental_profile(zp, h, t_coeffs) * spatial
        conc_pt = environmental_profile(zp, h, c_coeffs) * spatial
        eps_env = alpha_vec * temp_pt + beta_vec * conc_pt

        cands = find_elements_at(xp, yp)
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
        return w0_val / nc, stress4 / nc, shear2 / nc

    w_center, sig_top_center, _ = evaluate_point(a / 2.0, b / 2.0, h / 2.0)
    _, stress_xy_sample, _ = evaluate_point(0.0, 0.0, -h / 3.0)
    _, _, shear_xz_sample = evaluate_point(0.0, b / 2.0, 0.0)

    sigma_x_pa = float(sig_top_center[0])
    tau_xy_pa = float(stress_xy_sample[3])
    tau_xz_pa = float(shear_xz_sample[0])

    stress_sample_locations = {
        "sigma_x": {"x_m": a / 2.0, "y_m": b / 2.0, "z_m": h / 2.0},
        "tau_xy": {"x_m": 0.0, "y_m": 0.0, "z_m": -h / 3.0},
        "tau_xz": {"x_m": 0.0, "y_m": b / 2.0, "z_m": 0.0},
    }

    if q0 > 0.0:
        w_bar = 100.0 * flexural_rigidity * w_center / (q0 * (a ** 4))
        sigma_x_bar = (h ** 2 / (q0 * (a ** 2))) * sigma_x_pa
        tau_xy_bar = (h / (q0 * a)) * tau_xy_pa
        tau_xz_bar = -(h / (q0 * a)) * tau_xz_pa
    else:
        w_bar = sigma_x_bar = tau_xy_bar = tau_xz_bar = None

    return {
        "mesh": f"{m}x{n}",
        "m": int(m),
        "n": int(n),
        "nodes": len(coords),
        "elements": len(elements),
        "ndof": ndof,
        "free_dofs": len(free),
        "fixed_dofs": len(fixed),
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
        "flexural_rigidity_D_Nm": flexural_rigidity,
        "flexural_rigidity_Dy_Nm": flexural_rigidity_y,
        "stress_sample_locations": stress_sample_locations,
        "stiffness_info": {
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
        },
        "time_s": elapsed,
        "solver_warnings": [str(w.message) for w in warns] + extra_warnings,
        "coordinates": coords,
        "elements_array": elements,
        "displacements": uf,
        "w_values": uf[W::DOF],
        "inputs": {
            "a": a, "b": b, "h": h, "m": int(m), "n": int(n),
            "material_mode": material_mode, "E": E, "nu": nu,
            "q0": q0, "load_case": load_case, "choicebc": choicebc,
            "alpha": alpha, "beta": beta, "t_coeffs": t_coeffs, "c_coeffs": c_coeffs,
            "Kw": Kw, "Kp": Kp, "Kp_y": Kp_y, "K0": K0, "J0": J0,
            "nonlocal_parameter": nonlocal_parameter,
        },
    }


# ============================================================================
# 7. STREAMLINED TERMINAL INPUT & OUTPUT FUNCTIONS
# ============================================================================
def _read_value(prompt: str, default: str, cast):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return cast(default)
        try:
            return cast(raw)
        except (TypeError, ValueError):
            print("  [INPUT ERROR] Enter a valid number or press Enter for default.")


def _read_choice(prompt: str, choices: Tuple[int, ...], default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if val in choices:
                return val
        except ValueError:
            pass
        print(f"  [INPUT ERROR] Choose one of: {', '.join(map(str, choices))}.")


def _read_yes_no(prompt: str, default: str = "N") -> bool:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip().upper() or default
        if raw in ("Y", "YES"):
            return True
        if raw in ("N", "NO"):
            return False
        print("  [INPUT ERROR] Enter Y or N.")


def collect_terminal_inputs() -> Dict:
    """Prompt only for primary geometry, boundary condition, and active load options."""
    print("\n" + "=" * 68)
    print("  1. GEOMETRY, MESH & MATERIAL MODEL")
    print("=" * 68)
    a = _read_value("Plate length a (m)", "1.0", float)
    b = _read_value("Plate width b (m)", "3.0", float)
    h = _read_value("Plate thickness h (m)", "0.1", float)
    m = _read_value("Mesh elements along X (m)", "10", int)
    n = _read_value("Mesh elements along Y (n)", "10", int)

    print("\nMaterial Model: 1 = Homogeneous Isotropic, 2 = 3-Layer Orthotropic Laminate [0/90/0]")
    mat_choice = _read_choice("Select material model (1-2)", (1, 2), 1)
    lam_props: Dict[str, float] = {}
    alpha = 0.0
    if mat_choice == 1:
        material_mode = "isotropic"
        E = _read_value("Young's modulus E (Pa)", "200e9", float)
        nu = _read_value("Poisson's ratio nu", "0.3", float)
    else:
        material_mode = "laminate"
        E = nu = None
        print("  Preset ply: E1 = 181e9, E2 = E3 = 10.3e9 Pa, nu12 = nu23 = nu13 = 0.28, "
              "G12 = G13 = 7.17e9, G23 = 2.39e9 Pa")
        print("  Plane-stress model: E1, E2, nu12, G12, G13, G23 (and alpha1/2, beta1/2) are used;")
        print("  E3, nu23, nu13 (and alpha3, beta3) are accepted but have no effect.")
        if not _read_yes_no("Use the preset ply properties? (Y/N)", "Y"):
            for key, unit in (("E1", "Pa"), ("E2", "Pa"), ("E3", "Pa"), ("nu12", "-"), ("nu23", "-"),
                              ("nu13", "-"), ("G12", "Pa"), ("G13", "Pa"), ("G23", "Pa")):
                lam_props[key] = _read_value(f"Ply property {key} ({unit})",
                                             f"{PRESET_LAMINATE_PROPERTIES[key]:g}", float)

    print("\n" + "=" * 68)
    print("  2. BOUNDARY CONDITION (SINGLE SELECTION)")
    print("=" * 68)
    for k, desc in BOUNDARY_CONDITIONS.items():
        print(f"  {k}: {desc}")
    choicebc = _read_choice("Select boundary condition (1-6)", (1, 2, 3, 4, 5, 6), 1)

    print("\n" + "=" * 68)
    print("  3. MECHANICAL LOADING")
    print("=" * 68)
    print("Load distribution: 1 = Uniform pressure, 2 = Sinusoidal pressure")
    load_choice = _read_choice("Select load distribution (1-2)", (1, 2), 2)
    load_case = "uniform" if load_choice == 1 else "sinusoidal"
    q0 = _read_value("Transverse pressure amplitude q0 (Pa)", "100.0", float)
    nonlocal_parameter = 0.0  # Hardcoded default

    print("\n" + "=" * 68)
    print("  4. OPTIONAL MODULES (THERMAL, MOISTURE, FOUNDATION & VEHICLE LOAD)")
    print("=" * 68)
    t_coeffs = c_coeffs = None
    beta = 0.0
    if _read_yes_no("Enable thermal loading? (Y/N)"):
        if material_mode == "isotropic":
            alpha = _read_value("Thermal expansion coeff alpha (1/K)", "12e-6", float)
        else:
            for key in ("alpha1", "alpha2", "alpha3"):
                lam_props[key] = _read_value(f"Ply thermal expansion coeff {key} (1/K)",
                                             f"{PRESET_LAMINATE_PROPERTIES[key]:g}", float)
        t_coeffs = (_read_value("Temperature coefficient t1 (K)", "0.0", float),
                    _read_value("Temperature coefficient t2 (K)", "10.0", float),
                    _read_value("Temperature coefficient t3 (K)", "0.0", float))
    if _read_yes_no("Enable moisture loading? (Y/N)"):
        if material_mode == "isotropic":
            beta = _read_value("Moisture expansion coeff beta", "0.0", float)
        else:
            for key in ("beta1", "beta2", "beta3"):
                lam_props[key] = _read_value(f"Ply moisture expansion coeff {key}",
                                             f"{PRESET_LAMINATE_PROPERTIES[key]:g}", float)
        c_coeffs = (_read_value("Moisture coefficient c1", "0.0", float),
                    _read_value("Moisture coefficient c2", "100.0", float),
                    _read_value("Moisture coefficient c3", "0.0", float))
    layers = default_three_layer_laminate(h, **lam_props) if material_mode == "laminate" else None

    enable_found = _read_choice("Enable Elastic Foundation? (1=No, 2=Yes)", (1, 2), 1)
    K0 = J0 = None
    if enable_found == 2:
        print("Foundation input: 1 = Dimensional (Kw, Kp), 2 = Dimensionless (K0, J0)")
        print("  K0 = Kw*a^4/D,  J0 = Kp*a^2/D (x) and Kp*b^2/D (y)")
        print("  D = E*h^3/[12*(1-nu^2)] (isotropic) or the laminate bending stiffness D11 (laminate)")
        found_mode = _read_choice("Select foundation input (1-2)", (1, 2), 1)
        if found_mode == 1:
            Kw = _read_value("Winkler foundation modulus Kw (N/m^3)", "0.0", float)
            Kp = _read_value("Pasternak shear modulus Kp (N/m)", "0.0", float)
        else:
            K0 = _read_value("Dimensionless Winkler parameter K0", "0.0", float)
            J0 = _read_value("Dimensionless Pasternak parameter J0", "0.0", float)
            Kw, Kp = 0.0, 0.0
    else:
        Kw, Kp = 0.0, 0.0

    enable_veh = _read_choice("Enable Center Vehicle Wheel Patch Load? (1=No, 2=Yes)", (1, 2), 1)
    if enable_veh == 2:
        wheel_force = _read_value("Total wheel patch load (N)", "1000.0", float)
        patch_size = 0.2 * min(a, b)
        vehicle_load = VehicleLoad(wheel_patches=[(a / 2.0, b / 2.0, patch_size, patch_size, wheel_force)])
    else:
        vehicle_load = None

    print("\n" + "=" * 68)
    print("  5. OUTPUT OPTIONS")
    print("=" * 68)
    show_plots = _read_choice("Generate 3D/Contour deflection plots? (1=Yes, 2=No)", (1, 2), 2) == 1
    save_csv = _read_choice("Export results to CSV? (1=Yes, 2=No)", (1, 2), 2) == 1

    return {
        "a": a, "b": b, "h": h, "m": m, "n": n,
        "material_mode": material_mode, "E": E, "nu": nu, "alpha": alpha,
        "q0": q0, "nonlocal_parameter": nonlocal_parameter, "load_case": load_case,
        "choicebc": choicebc, "beta": beta, "t_coeffs": t_coeffs, "c_coeffs": c_coeffs,
        "Kw": Kw, "Kp": Kp, "K0": K0, "J0": J0, "vehicle_load": vehicle_load, "layers": layers,
        "show_plots": show_plots, "save_csv": save_csv,
    }


def print_results(r: Dict):
    """Display analysis summary, stiffness matrix diagnostics, dimensional and normalized results."""
    p = r["inputs"]
    k_info = r["stiffness_info"]
    line = "=" * 78
    thin = "-" * 78

    print("\n" + line)
    print("                         HOSNT12 FEA ANALYSIS SUMMARY")
    print(line)
    print(f"Plate Geometry    : a = {p['a']:g} m | b = {p['b']:g} m | h = {p['h']:g} m")
    if p["material_mode"] == "isotropic":
        print(f"Material Mode     : ISOTROPIC (E = {p['E']:.4e} Pa, nu = {p['nu']:.4g})")
    else:
        print("Material Mode     : LAMINATE (layer properties; plane-stress, no thickness stretching)")
    print(f"Mesh Discretization: {r['mesh']} Q8 elements | {r['nodes']:,} nodes | {r['ndof']:,} total DOFs")
    print(f"Boundary Condition: BC-{p['choicebc']} — {BOUNDARY_CONDITIONS[p['choicebc']]}")
    print(f"Mechanical Load   : {p['load_case']} pressure, q0 = {p['q0']:g} Pa")
    if p["t_coeffs"] is None:
        print("Thermal Load      : disabled")
    else:
        t_c = p["t_coeffs"]
        alpha_txt = f"{p['alpha']:g} 1/K" if p["material_mode"] == "isotropic" else "layer values"
        print(f"Thermal Load      : t = ({t_c[0]:g}, {t_c[1]:g}, {t_c[2]:g}) K | alpha = {alpha_txt}")
    if p["c_coeffs"] is None:
        print("Moisture Load     : disabled")
    else:
        c_c = p["c_coeffs"]
        beta_txt = f"{p['beta']:g}" if p["material_mode"] == "isotropic" else "layer values"
        print(f"Moisture Load     : c = ({c_c[0]:g}, {c_c[1]:g}, {c_c[2]:g}) | beta = {beta_txt}")
    if p["Kp_y"] == p["Kp"]:
        print(f"Elastic Foundation: Kw = {p['Kw']:g} N/m^3 | Kp = {p['Kp']:g} N/m")
    else:
        print(f"Elastic Foundation: Kw = {p['Kw']:g} N/m^3 | Kp_x = {p['Kp']:g} N/m | Kp_y = {p['Kp_y']:g} N/m")
    if p["K0"] is not None or p["J0"] is not None:
        print(f"Foundation (dimensionless): K0 = {p['K0'] or 0.0:g} | J0 = {p['J0'] or 0.0:g}")

    print("\n" + thin)
    print("                    STIFFNESS MATRIX DIAGNOSTICS")
    print(thin)
    print(f"Global K Matrix Shape          : {k_info['global_shape'][0]} x {k_info['global_shape'][1]}")
    print(f"Reduced Free K Matrix Shape    : {k_info['reduced_shape'][0]} x {k_info['reduced_shape'][1]} "
          f"(Constrained DOFs: {r['fixed_dofs']})")
    print(f"Non-Zero Entries (NNZ)         : {k_info['nnz']:,} ({k_info['density_pct']:.2f}% density)")
    print(f"Global K Diagonal Range        : [{k_info['diag_min']:.4e}, {k_info['diag_max']:.4e}]")
    print(f"Global K Frobenius Norm        : {k_info['frobenius_norm']:.6e}")
    print(f"Symmetry Check max|K - K^T|    : {k_info['max_asymmetry']:.4e}")
    print(f"Constitutive Norms ||Db||,||Ds||: ||Db|| = {k_info['Db_norm']:.4e} | ||Ds|| = {k_info['Ds_norm']:.4e}")
    print("\n Generalized Extensional Stiffness Submatrix A (Db[0:4, 0:4]):")
    for row in k_info["Db_top_left_4x4"]:
        print("   [" + "  ".join(f"{val:12.4e}" for val in row) + "]")

    print("\n" + thin)
    print("                         DIMENSIONAL OUTPUTS")
    print(thin)
    print(f"Center Deflection w(a/2, b/2)  : {r['w_center_m']:+.8e} m")
    print(f"Max Absolute Nodal Deflection  : {r['max_abs_deflection_m']:.8e} m")
    print(f"Min / Max Nodal Deflection     : {r['min_deflection_m']:+.8e} / {r['max_deflection_m']:+.8e} m")
    print(f"Normal Stress sigma_x          : {r['sigma_x_pa']:+.8e} Pa")
    print(f"In-Plane Shear Stress tau_xy   : {r['tau_xy_pa']:+.8e} Pa")
    print(f"Transverse Shear Stress tau_xz : {r['tau_xz_pa']:+.8e} Pa")

    print("\n" + line)
    print("                         NORMALIZED OUTPUTS")
    print(line)
    print(f"{'Quantity':<30} {'Symbol':<15} {'Normalized Value':>22}")
    print(thin)
    if r["w_bar"] is None:
        for label, sym in [
            ("Center Deflection", "w_bar"),
            ("Normal Stress", "sigma_x_bar"),
            ("In-Plane Shear Stress", "tau_xy_bar"),
            ("Transverse Shear Stress", "tau_xz_bar"),
        ]:
            print(f"{label:<30} {sym:<15} {'N/A (q0 = 0)':>22}")
    else:
        for label, sym, val in [
            ("Center Deflection", "w_bar", r["w_bar"]),
            ("Normal Stress", "sigma_x_bar", r["sigma_x_bar"]),
            ("In-Plane Shear Stress", "tau_xy_bar", r["tau_xy_bar"]),
            ("Transverse Shear Stress", "tau_xz_bar", r["tau_xz_bar"]),
        ]:
            print(f"{label:<30} {sym:<15} {val:>22.6f}")

    print("\nNormalization Factors Used:")
    if r["inputs"]["material_mode"] == "isotropic":
        print(f"  Flexural Rigidity D = E*h^3 / [12*(1 - nu^2)] = {r['flexural_rigidity_D_Nm']:.6e} N*m")
    else:
        print(f"  Flexural Rigidity D = D11 of the laminate = sum Q11_k (z_k+1^3 - z_k^3)/3 = "
              f"{r['flexural_rigidity_D_Nm']:.6e} N*m  (D22 = {r['flexural_rigidity_Dy_Nm']:.6e})")
    print("  w_bar               = 100 * D * w(a/2, b/2, 0) / (q0 * a^4)")
    print("  sigma_x_bar         = (h^2 / (q0 * a^2)) * sigma_x(a/2, b/2, +h/2)")
    print("  tau_xy_bar          = (h / (q0 * a)) * tau_xy(0, 0, -h/3)")
    print("  tau_xz_bar          = -(h / (q0 * a)) * tau_xz(0, b/2, 0)")
    print(thin)
    print(f"Solver Execution Time : {r['time_s']:.4f} s")
    if r["solver_warnings"]:
        print("\nSOLVER WARNINGS:")
        for w_msg in r["solver_warnings"]:
            print(f"  - {w_msg}")
    print(line)


def plot_deflection(r: Dict):
    """Render and save 3D surface and 2D contour plots of transverse deflection."""
    import matplotlib
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.interpolate import griddata

    coords = r["coordinates"]
    w = r["w_values"]
    p = r["inputs"]
    gx, gy = np.mgrid[0:p["a"]:100j, 0:p["b"]:100j]
    gz = griddata((coords[:, 0], coords[:, 1]), w, (gx, gy), method="cubic")
    if gz is None or not np.isfinite(gz).all():
        gz = griddata((coords[:, 0], coords[:, 1]), w, (gx, gy), method="linear")

    fig = plt.figure(figsize=(13, 5.5))
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    surf = ax1.plot_surface(gx, gy, gz, cmap="viridis", linewidth=0, antialiased=True)
    ax1.set_title("3D Transverse Deflection w(x, y)")
    ax1.set_xlabel("x (m)")
    ax1.set_ylabel("y (m)")
    ax1.set_zlabel("w (m)")
    fig.colorbar(surf, ax=ax1, shrink=0.6, pad=0.08)

    ax2 = fig.add_subplot(1, 2, 2)
    cf = ax2.contourf(gx, gy, gz, levels=24, cmap="viridis")
    ax2.set_title("Deflection Contours w(x, y)")
    ax2.set_xlabel("x (m)")
    ax2.set_ylabel("y (m)")
    fig.colorbar(cf, ax=ax2)

    fig.suptitle(f"HOSNT12 Plate Analysis — BC-{p['choicebc']} ({r['mesh']} Q8 Mesh)", fontweight="bold")
    fig.tight_layout()
    out = os.path.abspath("HOSNT12_deflection_plots.png")
    fig.savefig(out, dpi=220, bbox_inches="tight")
    print(f"\n[PLOT] Saved deflection plot to: {out}")
    plt.close(fig)


def export_results_csv(r: Dict, filepath: str = "HOSNT12_results.csv"):
    """Export inputs, summary metrics, and nodal deflections to CSV."""
    p = r["inputs"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["record_type", "parameter", "value", "x_m", "y_m", "w_m"])
        for k, v in p.items():
            writer.writerow(["input", k, v, "", "", ""])
        for k in (
            "mesh", "nodes", "elements", "ndof", "w_center_m", "max_abs_deflection_m",
            "sigma_x_pa", "tau_xy_pa", "tau_xz_pa", "w_bar", "sigma_x_bar",
            "tau_xy_bar", "tau_xz_bar", "flexural_rigidity_D_Nm", "time_s"
        ):
            writer.writerow(["result", k, r[k], "", "", ""])
        for idx, ((x, y), w_val) in enumerate(zip(r["coordinates"], r["w_values"])):
            writer.writerow(["node", idx + 1, "", f"{x:.8g}", f"{y:.8g}", f"{w_val:.8e}"])
    print(f"[CSV] Saved analysis data to: {os.path.abspath(filepath)}")


# ============================================================================
# 8. PAPER VALIDATION, CONVERGENCE AND REGRESSION CHECKS
#    command line only: --validate [mesh] | --convergence | --selftest
# ============================================================================
# Zidi et al. (2014), homogeneous ceramic plate, SSSS, a = 1, b = 3a, h = a/10, sinusoidal q0.
# These are benchmark inputs only; the solver itself takes any material.
PAPER_E, PAPER_NU, PAPER_ALPHA = 117e9, 1.0 / 3.0, 7.11e-6
# Rows: (K0, J0) -> (w_bar, sigma_x_bar, tau_xy_bar, tau_xz_bar).
PAPER_TABLE_2_TSDT = {
    (0, 0): (0.85891, 0.51545, 0.72797, -0.42956),
    (100, 0): (0.46206, 0.27620, 0.39162, -0.23109),
    (0, 100): (0.08965, 0.05358, 0.07599, -0.04485),
    (100, 100): (0.08228, 0.04919, 0.06972, -0.04116),
}
PAPER_TABLE_2_FSDT = {
    (0, 0): (0.85892, 0.51065, 0.72949, -0.34377),
    (100, 0): (0.46206, 0.27471, 0.39246, -0.18493),
    (0, 100): (0.08965, 0.05330, 0.07616, -0.03588),
    (100, 100): (0.08228, 0.04890, 0.06986, -0.03293),
}
# Table 3 (TSDT): temperature t = (0, 10, 0), moisture c = (0, 100, 0); the ceramic has beta = 0.
PAPER_TABLE_3_TSDT = {
    (0, 0): (1.80712, 0.47187, 1.55982, -0.42955),
    (100, 0): (0.97216, -0.02740, 0.85211, -0.01197),
    (0, 100): (0.18861, -0.49570, 0.18806, 0.37990),
    (100, 100): (0.17309, -0.50498, 0.17490, 0.38766),
}
# Load scale of Table 3 -- UNRESOLVED AMBIGUITY, handled by an explicit assumption, not a confirmed correction.
# What the paper prints: Tables 2-3 give "q0 = 100" without a unit; the text of Section 4 says "q0 = 100 GPa"
# (in a sentence that also lists t1 = t2 = 0, c1 = c2 = 0, which contradicts the Table 3 caption t2 = 10, c2 = 100,
# so that sentence is not reliable); alpha_C = 7.11e-6 /degC, E_C = 117 GPa. Eqs. (24)-(25) as extracted from
# the PDF are not dimensionally self-consistent (the thermal term of P3 carries an extra factor h and the
# thickness integrals mix z and z/h), so they cannot settle the unit convention either.
# What the physics fixes: the thermal strain is alpha*T, so the response normalised by q0 depends on the
# loads only through the dimensionless group
#     PI = E * alpha * t2 / q0 .
# The literal printed values (q0 = 100 GPa, alpha = 7.11e-6) give PI = 8.3e-5, for which Table 3 would be
# indistinguishable from Table 2; the printed Table 3 values instead correspond to PI = 83.19 (the same value
# from the w_bar shift of all four K0/J0 rows, checked in --selftest). Any (alpha, q0) pair with this PI gives
# identical normalised results, e.g. q0 = 100 kPa with alpha = 7.11e-6 (used below), or q0 = 100 GPa with
# alpha = 7.11 (the 1e-6 dropped), or t2 = 1e7. The data cannot tell these apart; q0 = 100 kPa is only an
# ASSUMPTION that reproduces the table. Nothing here proves it is what the authors used.
PAPER_Q0_TABLE_2 = 100.0
PAPER_Q0_TABLE_3 = 1.0e5
_NORMALISED = ("w_bar", "sigma_x_bar", "tau_xy_bar", "tau_xz_bar")


def solve_paper_case(K0, J0, mesh, hygrothermal=False, m=None, n=None) -> Dict:
    """One ceramic benchmark case of the paper, SI units."""
    kw = dict(m=m or mesh, n=n or mesh, material_mode="isotropic", E=PAPER_E, nu=PAPER_NU, K0=K0, J0=J0)
    if hygrothermal:
        return solve_hosnt12(q0=PAPER_Q0_TABLE_3, alpha=PAPER_ALPHA, beta=0.0,
                             t_coeffs=(0, 10, 0), c_coeffs=(0, 100, 0), **kw)
    return solve_hosnt12(q0=PAPER_Q0_TABLE_2, **kw)


def run_paper_validation(mesh: int = 10) -> None:
    """Print the paper-vs-Python comparison for Table 2 (mechanical) and Table 3 (hygrothermal), ceramic rows.

    The ceramic has beta = 0, so Table 3 checks the thermal path only; moisture expansion is tested
    separately (--selftest) because the paper's ceramic cannot exercise it."""
    line = "=" * 82
    print("\n" + line)
    print(f"  VALIDATION AGAINST ZIDI ET AL. (2014) | homogeneous ceramic, SSSS | mesh {mesh}x{mesh}")
    print(f"  a = 1 m, b = 3 m, h = 0.1 m, E = 117 GPa, nu = 1/3, sinusoidal q0")
    print(f"  NOTE: the load scale of Table 3 is ambiguous in the paper (q0 = 100 GPa with alpha = 7.11e-6 gives")
    print(f"  E*alpha*t2/q0 = 8.3e-5, but the table needs 83.2). q0 = {PAPER_Q0_TABLE_3:g} Pa with alpha as printed is an")
    print(f"  ASSUMPTION that reproduces Table 3, not a confirmed reading of the paper (see PAPER_Q0_TABLE_3).")
    print(line)
    tables = (
        (f"Table 2 (TSDT) | q0 = {PAPER_Q0_TABLE_2:g} Pa, no thermal/moisture", PAPER_TABLE_2_TSDT, False),
        ("Table 2 (FSDT) | same inputs", PAPER_TABLE_2_FSDT, False),
        (f"Table 3 (TSDT) | q0 = {PAPER_Q0_TABLE_3:g} Pa, alpha = {PAPER_ALPHA:g}, beta = 0, "
         "t = (0, 10, 0), c = (0, 100, 0)", PAPER_TABLE_3_TSDT, True),
    )
    for title, rows, hygro in tables:
        print(f"\n{title}\n{'K0':>5}{'J0':>5}  {'Quantity':<13}{'Paper':>11}{'Python':>11}{'Error (%)':>11}")
        print("-" * 58)
        worst = [0.0] * 4
        for (K0, J0), paper in rows.items():
            r = solve_paper_case(K0, J0, mesh, hygro)
            for i, name in enumerate(_NORMALISED):
                err = abs(r[name] - paper[i]) / abs(paper[i]) * 100.0
                worst[i] = max(worst[i], err)
                print(f"{K0:>5}{J0:>5}  {name:<13}{paper[i]:>11.5f}{r[name]:>11.5f}{err:>11.3f}")
        print("-" * 58)
        print("  worst error (%): " + " | ".join(f"{n} {w:.3f}" for n, w in zip(_NORMALISED, worst)))
    print("\n" + line)


def _observed_order(v1: float, v2: float, v3: float, n1: int, n2: int, n3: int) -> float:
    """Convergence order p of v(n) = v_inf + C n^-p from three meshes (bisection); nan if not monotone."""
    d12, d23 = v1 - v2, v2 - v3
    if d12 == 0.0 or d23 == 0.0 or d12 * d23 < 0.0:
        return float("nan")
    ratio = lambda p: (n1 ** -p - n2 ** -p) / (n2 ** -p - n3 ** -p)
    lo, hi = 0.1, 8.0
    if (ratio(lo) - d12 / d23) * (ratio(hi) - d12 / d23) > 0.0:
        return float("nan")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if (ratio(lo) - d12 / d23) * (ratio(mid) - d12 / d23) <= 0.0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def run_convergence_study(meshes=(4, 6, 8, 10, 12, 16, 20, 24, 28, 32)) -> None:
    """Mesh refinement of the central deflection and the three recovered stresses (ceramic benchmark).

    After each table the observed order of convergence and the Richardson-extrapolated value are printed
    from the three finest meshes. For Table 3 (K0 = 100, J0 = 0) the sigma_x_bar error is a second-order
    interpolation error of the in-plane strain that is amplified by cancellation (Q*eps ~ +0.60 against the
    thermal stress Q*alpha*T ~ +0.62, total -0.027), not a recovery, resultant or normalization error."""
    line = "=" * 112
    cases = (("Table 2, K0 = 0, J0 = 0 (mechanical)", 0, 0, False),
             ("Table 3, K0 = 0, J0 = 0 (thermal + mechanical)", 0, 0, True),
             ("Table 3, K0 = 100, J0 = 0 (thermal + mechanical)", 100, 0, True))
    for title, K0, J0, hygro in cases:
        print("\n" + line)
        print(f"  MESH CONVERGENCE | {title}")
        print(line)
        print(f"{'mesh':>7}{'w_centre [m]':>16}{'w_bar':>10}{'sigma_x_bar':>13}{'tau_xy_bar':>12}{'tau_xz_bar':>12}"
              f" |{'d w_bar':>10}{'d sig_x':>10}{'d tau_xy':>10}{'d tau_xz':>10}   (change vs previous mesh, %)")
        prev = None
        history: List[Tuple[int, List[float]]] = []
        for mesh in meshes:
            r = solve_paper_case(K0, J0, mesh, hygro)
            vals = [r[k] for k in _NORMALISED]
            chg = [""] * 4 if prev is None else [f"{(v - p) / abs(p) * 100:.3f}" for v, p in zip(vals, prev)]
            print(f"{mesh:>4}x{mesh:<2}{r['w_center_m']:>16.6e}{vals[0]:>10.5f}{vals[1]:>13.5f}{vals[2]:>12.5f}"
                  f"{vals[3]:>12.5f} |{chg[0]:>10}{chg[1]:>10}{chg[2]:>10}{chg[3]:>10}")
            prev = vals
            history.append((mesh, vals))
        if len(history) >= 3:
            (n1, v1), (n2, v2), (n3, v3) = history[-3:]
            orders = [_observed_order(v1[k], v2[k], v3[k], n1, n2, n3) for k in range(4)]
            extrap = [v3[k] + (v3[k] - v2[k]) / ((n3 / n2) ** o - 1.0) if o == o else float("nan")
                      for k, o in enumerate(orders)]
            print(f"  observed order ({n1},{n2},{n3}) : " + " | ".join(f"{n} {o:.2f}" for n, o in zip(_NORMALISED, orders)))
            print("  Richardson extrapolation : " + " | ".join(f"{n} {v:+.5f}" for n, v in zip(_NORMALISED, extrap)))
    print("\n" + line)


def run_self_tests() -> bool:
    """Regression and functional checks; returns True when every check passes."""
    results: List[Tuple[str, bool, str]] = []

    def check(name: str, cond: bool, info: str = ""):
        results.append((name, bool(cond), info))

    def same(x, y, tol=1e-9):
        return abs(x - y) <= tol * max(abs(y), 1e-300)

    iso = dict(material_mode="isotropic", E=PAPER_E, nu=PAPER_NU)
    # ---- mechanical / environmental regression (explicit material, no defaults) ----
    env = dict(m=6, n=6, q0=1e5, alpha=PAPER_ALPHA, K0=100, J0=100, **iso)
    t_only, c_only = (0, 10, 0), (0, 100, 0)
    beta_eq = PAPER_ALPHA * 10.0 / 100.0                   # beta*c = alpha*t  ->  same strain
    mech = solve_hosnt12(**env)
    off = solve_hosnt12(t_coeffs=(0, 0, 0), c_coeffs=(0, 0, 0), beta=beta_eq, **env)
    check("mechanical-only unchanged when thermal and moisture are disabled/zero",
          all(same(off[k], mech[k]) for k in _NORMALISED))
    bench = solve_hosnt12(m=10, n=10, q0=100.0, **iso)
    check("benchmark w_bar (Table 2, K0 = J0 = 0) within 0.1 % of 0.85891",
          same(bench["w_bar"], 0.85891, 1e-3), f"{bench['w_bar']:.5f}")
    therm = solve_hosnt12(t_coeffs=t_only, **env)
    check("thermal-only loading works", not same(therm["w_bar"], mech["w_bar"], 1e-3))
    moist = solve_hosnt12(c_coeffs=c_only, beta=beta_eq, **env)
    check("moisture-only loading works (beta*c = alpha*t gives the thermal-only solution)",
          not same(moist["w_bar"], mech["w_bar"], 1e-3) and all(same(moist[k], therm[k]) for k in _NORMALISED))
    both = solve_hosnt12(t_coeffs=t_only, c_coeffs=c_only, beta=beta_eq, **env)
    check("combined loading = mechanical + thermal part + moisture part (w_bar, sigma_x_bar)",
          same(both["w_bar"] - mech["w_bar"], (therm["w_bar"] - mech["w_bar"]) + (moist["w_bar"] - mech["w_bar"]), 1e-8)
          and same(both["sigma_x_bar"] - mech["sigma_x_bar"],
                   (therm["sigma_x_bar"] - mech["sigma_x_bar"]) + (moist["sigma_x_bar"] - mech["sigma_x_bar"]), 1e-8))
    zero_c = solve_hosnt12(t_coeffs=t_only, c_coeffs=(0, 0, 0), beta=beta_eq, **env)
    check("zero moisture reproduces the thermal-only solution", all(same(zero_c[k], therm[k]) for k in _NORMALISED))
    zero_t = solve_hosnt12(t_coeffs=(0, 0, 0), c_coeffs=c_only, beta=beta_eq, **env)
    check("zero temperature reproduces the moisture-only solution", all(same(zero_t[k], moist[k]) for k in _NORMALISED))
    warn_b = solve_hosnt12(c_coeffs=c_only, **env)
    check("moisture with beta = 0 is flagged and changes nothing",
          bool(warn_b["solver_warnings"]) and same(warn_b["w_bar"], mech["w_bar"]))
    warn_a = solve_hosnt12(t_coeffs=t_only, **{**env, "alpha": 0.0})
    check("temperature with alpha = 0 is flagged and changes nothing",
          bool(warn_a["solver_warnings"]) and same(warn_a["w_bar"], mech["w_bar"]))
    check("no default material: missing E/nu is rejected",
          _raises(lambda: solve_hosnt12(m=2, n=2)))
    for bc in range(1, 7):
        r = solve_hosnt12(m=4, n=4, choicebc=bc, t_coeffs=t_only, c_coeffs=c_only, alpha=2e-5, beta=0.1, **iso)
        check(f"BC-{bc} runs with thermal + moisture (finite, no warnings)",
              np.isfinite(r["w_center_m"]) and not r["solver_warnings"])
    w = {kj: solve_hosnt12(m=6, n=6, K0=kj[0], J0=kj[1], **iso)["w_bar"] for kj in ((0, 0), (100, 0), (0, 100), (100, 100))}
    check("foundation trends: w_bar falls with K0 and J0, Pasternak stiffer than Winkler",
          w[(0, 0)] > w[(100, 0)] > w[(0, 100)] > w[(100, 100)])
    D = bench["flexural_rigidity_D_Nm"]
    dim = solve_hosnt12(m=6, n=6, Kw=100 * D, Kp=100 * D, Kp_y=100 * D / 9.0, **iso)
    check("K0/J0 equal the converted dimensional Kw/Kp", same(dim["w_bar"], w[(100, 100)], 1e-12))
    again = solve_hosnt12(t_coeffs=t_only, c_coeffs=c_only, beta=beta_eq, **env)
    check("repeated runs are identical", again["w_bar"] == both["w_bar"])
    check("stiffness symmetric, finite solution, no solver warnings",
          bench["stiffness_info"]["max_asymmetry"] < 1e-3 and np.isfinite(bench["w_bar"]) and not bench["solver_warnings"])

    # ---- units: only the group E*alpha*t/q0 matters ----
    scaled = solve_hosnt12(t_coeffs=t_only, **{**env, "alpha": PAPER_ALPHA * 1e6, "q0": 1e5 * 1e6})
    check("normalised thermal response depends only on E*alpha*t/q0 (alpha x1e6 with q0 x1e6)",
          all(same(scaled[k], therm[k], 1e-9) for k in _NORMALISED))

    # ---- different (non-paper) materials: functional checks, not paper validation ----
    steel = dict(material_mode="isotropic", E=200e9, nu=0.3)
    alum = dict(material_mode="isotropic", E=70e9, nu=0.3)
    sm = solve_hosnt12(m=6, n=6, q0=5e3, **steel)
    am = solve_hosnt12(m=6, n=6, q0=5e3, **alum)
    check("stiffness: dimensional w scales as 1/E (steel vs aluminium)", same(sm["w_center_m"] * 200e9, am["w_center_m"] * 70e9, 1e-9))
    check("normalised w_bar is independent of E at fixed nu", same(sm["w_bar"], am["w_bar"], 1e-9))
    th_s = solve_hosnt12(m=6, n=6, q0=0.0, alpha=12e-6, t_coeffs=t_only, **steel)
    th_a = solve_hosnt12(m=6, n=6, q0=0.0, alpha=12e-6, t_coeffs=t_only, **alum)
    th_2 = solve_hosnt12(m=6, n=6, q0=0.0, alpha=24e-6, t_coeffs=t_only, **steel)
    check("thermal deflection of a free-foundation plate is independent of E", same(th_s["w_center_m"], th_a["w_center_m"], 1e-9))
    check("thermal deflection is linear in alpha", same(th_2["w_center_m"], 2 * th_s["w_center_m"], 1e-9))
    mo_1 = solve_hosnt12(m=6, n=6, q0=0.0, beta=0.2, c_coeffs=c_only, **steel)
    mo_2 = solve_hosnt12(m=6, n=6, q0=0.0, beta=0.4, c_coeffs=c_only, **steel)
    check("moisture deflection is linear in beta", same(mo_2["w_center_m"], 2 * mo_1["w_center_m"], 1e-9))
    th_k = solve_hosnt12(m=6, n=6, q0=0.0, alpha=12e-6, t_coeffs=t_only, K0=100, **steel)
    check("an elastic foundation reduces the thermal deflection", abs(th_k["w_center_m"]) < abs(th_s["w_center_m"]))

    iso_lay = default_three_layer_laminate(0.1, E1=200e9, E2=200e9, E3=200e9, nu12=0.3, nu23=0.3, nu13=0.3,
                                           G12=200e9 / 2.6, G13=200e9 / 2.6, G23=200e9 / 2.6,
                                           alpha1=12e-6, alpha2=12e-6, alpha3=12e-6, beta1=0.2, beta2=0.2, beta3=0.2)
    lam_i = solve_hosnt12(m=6, n=6, q0=5e3, material_mode="laminate", layers=iso_lay, t_coeffs=t_only, c_coeffs=c_only)
    iso_i = solve_hosnt12(m=6, n=6, q0=5e3, alpha=12e-6, beta=0.2, t_coeffs=t_only, c_coeffs=c_only, **steel)
    check("orthotropic laminate with isotropic properties reproduces the isotropic solution (w, sigma_x, tau_xz)",
          same(lam_i["w_center_m"], iso_i["w_center_m"], 1e-9) and same(lam_i["sigma_x_pa"], iso_i["sigma_x_pa"], 1e-8)
          and same(lam_i["tau_xz_pa"], iso_i["tau_xz_pa"], 1e-8))
    cross = default_three_layer_laminate(0.1)
    rot = default_three_layer_laminate(0.1)
    for lyr, ang in zip(rot, (math.pi / 2, 0.0, math.pi / 2)):
        lyr.theta_rad = ang
    sq = dict(a=1.0, b=1.0, m=6, n=6, q0=1e3, material_mode="laminate")
    c0 = solve_hosnt12(layers=cross, **sq)
    c90 = solve_hosnt12(layers=rot, **sq)
    check("orthotropy matters: [0/90/0] and [90/0/90] differ in sigma_x but not in w_centre",
          same(c0["w_center_m"], c90["w_center_m"], 1e-9) and not same(c0["sigma_x_pa"], c90["sigma_x_pa"], 1e-3))
    base = solve_hosnt12(layers=default_three_layer_laminate(0.1), **{**sq, "a": 1.0, "b": 3.0})
    inert = solve_hosnt12(layers=default_three_layer_laminate(0.1, E3=5e9, nu23=0.1, nu13=0.4, alpha3=1e-3, beta3=1.0),
                          **{**sq, "a": 1.0, "b": 3.0})
    check("E3, nu23, nu13, alpha3, beta3 are inert in the sigma_z = 0 model", same(inert["w_center_m"], base["w_center_m"], 1e-12))
    a1 = solve_hosnt12(layers=default_three_layer_laminate(0.1, alpha1=1e-5, alpha2=0.0), q0=0.0, t_coeffs=t_only,
                       material_mode="laminate", m=6, n=6)
    a2 = solve_hosnt12(layers=default_three_layer_laminate(0.1, alpha1=0.0, alpha2=1e-5), q0=0.0, t_coeffs=t_only,
                       material_mode="laminate", m=6, n=6)
    a0 = solve_hosnt12(layers=default_three_layer_laminate(0.1, alpha1=0.0, alpha2=0.0), q0=0.0, t_coeffs=t_only,
                       material_mode="laminate", m=6, n=6)
    check("directional alpha1 / alpha2 act differently; zero alpha gives no thermal deflection",
          not same(a1["w_center_m"], a2["w_center_m"], 1e-3) and a0["max_abs_deflection_m"] < 1e-12 and bool(a0["solver_warnings"]))
    check("invalid laminate (nu12*nu21 >= 1) is rejected",
          _raises(lambda: solve_hosnt12(m=2, n=2, material_mode="laminate",
                                        layers=default_three_layer_laminate(0.1, nu12=5.0))))

    # ---- Table 3 load scale: all four rows imply the same PI = E*alpha*t2/q0 (consistency, not a unit proof) ----
    implied = []
    for (k0_, j0_), t3 in PAPER_TABLE_3_TSDT.items():
        w2 = PAPER_TABLE_2_TSDT[(k0_, j0_)][0]
        base_ = dict(m=10, n=10, K0=k0_, J0=j0_, **iso)
        mech_ = solve_hosnt12(q0=PAPER_Q0_TABLE_3, **base_)["w_bar"]
        th_ = solve_hosnt12(q0=PAPER_Q0_TABLE_3, alpha=PAPER_ALPHA, t_coeffs=(0, 10, 0), **base_)["w_bar"]
        pi_unit = PAPER_E * PAPER_ALPHA * 10.0 / PAPER_Q0_TABLE_3
        implied.append(pi_unit * (t3[0] - w2) / (th_ - mech_))
    check("Table 3 minus Table 2 deflection shift implies one load group E*alpha*t2/q0 = 83.2 in all four K0/J0 rows",
          max(implied) - min(implied) < 2e-3 * np.mean(implied) and abs(np.mean(implied) - 83.19) < 0.1,
          "PI = " + ", ".join(f"{x:.2f}" for x in implied))

    # ---- laminate normalization and foundation conversion (D = D11 of the stack) ----
    h_l = 0.1
    stack = default_three_layer_laminate(h_l)
    D11, D22 = reference_flexural_rigidity(h_l, "laminate", layers=stack)
    D11_ref = sum(l.E1 / (1 - l.nu12 ** 2 * l.E2 / l.E1) * (l.h_top ** 3 - l.h_bottom ** 3) / 3.0 if l.theta_rad == 0.0
                  else l.E2 / (1 - l.nu12 ** 2 * l.E2 / l.E1) * (l.h_top ** 3 - l.h_bottom ** 3) / 3.0 for l in stack)
    Db_l = compute_stiffness_and_environment_resultants(h_l, "laminate", layers=stack)[0]
    legacy = stack[0].E1 * h_l ** 3 / (12.0 * (1.0 - stack[0].nu12 ** 2))
    check("laminate D11 equals the independent closed form and the integrated generalized stiffness Db[4,4]",
          same(D11, D11_ref, 1e-12) and same(D11, Db_l[4, 4], 1e-12), f"D11 = {D11:.5e}")
    check("laminate D differs from the first-ply formula E1*h^3/[12(1-nu12^2)] used before (stack matters)",
          abs(D11 - legacy) / legacy > 0.05, f"stack {D11:.4e} vs first-ply {legacy:.4e}")
    stack_r = default_three_layer_laminate(h_l)
    for lyr, ang in zip(stack_r, (math.pi / 2, 0.0, math.pi / 2)):
        lyr.theta_rad = ang
    D11_r, D22_r = reference_flexural_rigidity(h_l, "laminate", layers=stack_r)
    check("[90/0/90] swaps D11 and D22 of [0/90/0] (D follows the stacking sequence)",
          same(D11_r, D22, 1e-12) and same(D22_r, D11, 1e-12) and not same(D11_r, D11, 1e-2))
    iso_D = reference_flexural_rigidity(0.1, "isotropic", E=200e9, nu=0.3)[0]
    check("laminate D reduces exactly to E*h^3/[12(1-nu^2)] when every ply is isotropic",
          same(reference_flexural_rigidity(0.1, "laminate", layers=iso_lay)[0], iso_D, 1e-12))
    kj = dict(m=6, n=6, q0=5e3, K0=100, J0=100)
    lam_f = solve_hosnt12(material_mode="laminate", layers=iso_lay, **kj)
    iso_f = solve_hosnt12(**kj, **steel)
    check("isotropic-equivalent laminate: K0/J0 conversion and normalised w_bar, sigma_x_bar, tau_xz_bar match the isotropic plate",
          same(lam_f["flexural_rigidity_D_Nm"], iso_f["flexural_rigidity_D_Nm"], 1e-12)
          and all(same(lam_f[k], iso_f[k], 1e-8) for k in ("w_bar", "sigma_x_bar", "tau_xz_bar")))
    a_l, b_l = 1.0, 3.0
    lam_d = solve_hosnt12(a=a_l, b=b_l, h=h_l, m=6, n=6, q0=1e5, material_mode="laminate", layers=stack, K0=60, J0=25)
    lam_dim = solve_hosnt12(a=a_l, b=b_l, h=h_l, m=6, n=6, q0=1e5, material_mode="laminate", layers=stack,
                            Kw=60 * D11 / a_l ** 4, Kp=25 * D11 / a_l ** 2, Kp_y=25 * D11 / b_l ** 2)
    check("laminate K0/J0 equal the dimensional Kw = K0*D11/a^4, Kp = J0*D11/a^2, Kp_y = J0*D11/b^2 (same dimensional w)",
          same(lam_d["flexural_rigidity_D_Nm"], D11, 1e-12) and same(lam_d["w_center_m"], lam_dim["w_center_m"], 1e-12)
          and same(lam_d["sigma_x_pa"], lam_dim["sigma_x_pa"], 1e-10)
          and same(lam_d["inputs"]["Kw"], 60 * D11 / a_l ** 4, 1e-12) and same(lam_d["inputs"]["Kp_y"], 25 * D11 / b_l ** 2, 1e-12))
    check("laminate w_bar = 100*D11*w/(q0*a^4); dimensional w does not depend on the normalization",
          same(lam_d["w_bar"], 100 * D11 * lam_d["w_center_m"] / (1e5 * a_l ** 4), 1e-12)
          and same(lam_dim["w_bar"], lam_d["w_bar"], 1e-12))

    # ---- orthotropic property activity under the plane-stress, no-thickness-stretching formulation ----
    kw = dict(a=1.0, b=3.0, m=6, n=6, q0=1e5, material_mode="laminate")
    ref_o = solve_hosnt12(layers=default_three_layer_laminate(0.1, alpha1=2e-6, alpha2=20e-6, beta1=0.01, beta2=0.3),
                          t_coeffs=(1.0, 10.0, 2.0), c_coeffs=(0.5, 50.0, 4.0), **kw)
    inert_o = solve_hosnt12(layers=default_three_layer_laminate(0.1, alpha1=2e-6, alpha2=20e-6, beta1=0.01, beta2=0.3,
                                                                E3=3e9, nu23=0.05, nu13=0.45, alpha3=7e-3, beta3=2.0),
                            t_coeffs=(1.0, 10.0, 2.0), c_coeffs=(0.5, 50.0, 4.0), **kw)
    check("inert properties E3, nu23, nu13, alpha3, beta3 change no output (w, sigma_x, tau_xy, tau_xz) even with thermal + moisture",
          all(same(inert_o[k], ref_o[k], 1e-12) for k in ("w_center_m", "sigma_x_pa", "tau_xy_pa", "tau_xz_pa")))
    active_ok, moved = True, []
    for key, val in (("E1", 1.3 * 181e9), ("E2", 1.3 * 10.3e9), ("nu12", 0.33), ("G12", 1.3 * 7.17e9),
                     ("G13", 1.3 * 7.17e9), ("G23", 1.3 * 2.39e9), ("alpha1", 6e-6), ("alpha2", 30e-6),
                     ("beta1", 0.05), ("beta2", 0.45)):
        pert = solve_hosnt12(layers=default_three_layer_laminate(0.1, **{**dict(alpha1=2e-6, alpha2=20e-6, beta1=0.01, beta2=0.3), key: val}),
                             t_coeffs=(1.0, 10.0, 2.0), c_coeffs=(0.5, 50.0, 4.0), **kw)
        changed = any(not same(pert[k], ref_o[k], 1e-6) for k in ("w_center_m", "sigma_x_pa", "tau_xy_pa", "tau_xz_pa"))
        active_ok &= changed
        if not changed:
            moved.append(key)
    check("active properties E1, E2, nu12, G12, G13, G23, alpha1, alpha2, beta1, beta2 each change the response",
          active_ok, "no effect: " + ", ".join(moved) if moved else "")

    # ---- vehicle patch load: applied total equals the requested force on any mesh ----
    ok_patch = True
    for (a_, b_, m_, n_) in ((1, 3, 4, 4), (1, 3, 10, 10), (1, 3, 7, 5), (1, 1, 6, 6)):
        coords, els, _ = build_mesh(a_, b_, m_, n_)
        ps = 0.2 * min(a_, b_)
        tot = sum(patch_load_vector(coords[el], [(a_ / 2, b_ / 2, ps, ps, 1000.0)]).sum() for el in els)
        ok_patch &= same(tot, 1000.0, 1e-12)
    check("vehicle patch load totals the requested force on every mesh", ok_patch)
    veh = solve_hosnt12(m=6, n=6, q0=0.0, vehicle_load=VehicleLoad(wheel_patches=[(0.5, 1.5, 0.2, 0.2, 1000.0)],
                                                                  nodal_loads=[(1, 0.0)]), **steel)
    check("vehicle patch load produces a downward deflection", veh["w_center_m"] > 0.0)

    print("\n" + "=" * 90)
    print("  HOSNT12 REGRESSION AND FUNCTIONAL CHECKS")
    print("=" * 90)
    for name, passed, info in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({info})" if info else ""))
    n_fail = sum(1 for _, p, _ in results if not p)
    print("-" * 90)
    print(f"  {len(results) - n_fail}/{len(results)} checks passed")
    print("=" * 90)
    return n_fail == 0


def _raises(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def main():
    print("\n" + "#" * 68)
    print("  HOSNT12 HIGHER-ORDER PLATE FINITE-ELEMENT SOLVER")
    print("  Q8 Serendipity Mesh | 12 DOFs/Node | Sparse Direct Solver")
    print("#" * 68)

    while True:
        try:
            args = collect_terminal_inputs()
            show_plots = args.pop("show_plots")
            save_csv = args.pop("save_csv")

            print("\n[SOLVER] Assembling sparse stiffness matrix and solving...")
            results = solve_hosnt12(**args)
            print_results(results)

            if show_plots:
                plot_deflection(results)
            if save_csv:
                export_results_csv(results)

        except KeyboardInterrupt:
            print("\n\nExiting HOSNT12 solver.")
            break
        except Exception as exc:
            print(f"\n[ERROR] {exc}")

        print("\n" + "-" * 68)
        again = input("Run another analysis? (y/n) [y]: ").strip().lower()
        if again in ("n", "no"):
            print("Shutting down HOSNT12 solver. Goodbye!")
            break


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(0 if run_self_tests() else 1)
    if "--convergence" in sys.argv[1:]:
        run_convergence_study()
        sys.exit(0)
    if "--validate" in sys.argv[1:]:
        extra = [x for x in sys.argv[1:] if x.isdigit()]
        run_paper_validation(int(extra[0]) if extra else 10)
        sys.exit(0)
    main()