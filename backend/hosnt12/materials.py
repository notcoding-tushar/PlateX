import math
from typing import Literal

import numpy as np

from .constants import PRESET_LAMINATE_PROPERTIES
from .schemas import LayerProperty


def _expansion_vector(v1: float, v2: float, v3: float, c: float, s: float) -> np.ndarray:
    """Rotate principal thermal/moisture expansion coefficients into plate axes (x, y, z, xy)."""
    c2, s2 = c * c, s * s
    return np.array([v1 * c2 + v2 * s2, v1 * s2 + v2 * c2, v3, 2.0 * (v1 - v2) * s * c], dtype=float)


def orthotropic_layer_matrices(layer: LayerProperty) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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

def default_three_layer_laminate(h: float, **properties: float) -> list[LayerProperty]:
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
    LayerProperty.model_validate(lyr.model_dump())



def layer_at_z(layers: list[LayerProperty], zp: float,
               side: Literal["auto", "above", "below"] = "auto") -> LayerProperty:
    """Keep input order for auto, selecting the requested ply at a shared interface."""
    matches = [ply for ply in layers if ply.h_bottom - 1e-12 <= zp <= ply.h_top + 1e-12]
    if not matches:
        raise ValueError(f"No layer contains thickness coordinate {zp}.")
    if side == "above":
        return max(matches, key=lambda ply: ply.h_bottom)
    if side == "below":
        return min(matches, key=lambda ply: ply.h_bottom)
    return matches[0]

def material_at_z(
    material_mode: str,
    E: float | None,
    nu: float | None,
    alpha: float,
    beta: float,
    layer: LayerProperty | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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


def environmental_profile(z: float, h: float, coeffs: tuple[float, float, float] | None) -> float:
    """Through-thickness temperature or moisture-concentration change (Zidi et al. 2014):
    X(z) = x1 + (z/h) x2 + (1/pi) sin(pi z / h) x3, multiplied in-plane by sin(pi x/a) sin(pi y/b)."""
    if coeffs is None:
        return 0.0
    return coeffs[0] + (z / h) * coeffs[1] + math.sin(math.pi * z / h) / math.pi * coeffs[2]


ACTIVE = ((0, 1, 2, 3), (0, 1, 2, 3), (0, 1, 2, 3), (0, 1, 3))
STARTS = (0, 4, 8, 12, 15)


def _thickness_points(h, material_mode, E, nu, alpha, beta, active_layers):
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
            yield z, wz, Cb, Cs, alpha_vec, beta_vec


def environmental_resultants(h, material_mode, E, nu, alpha, beta, layers, t_coeffs, c_coeffs):
    env_resultants = np.zeros(15)
    if t_coeffs is None and c_coeffs is None:
        return env_resultants
    for z, wz, Cb, _, alpha_vec, beta_vec in _thickness_points(h, material_mode, E, nu, alpha, beta, layers):
        eps_env = (alpha_vec * environmental_profile(z, h, t_coeffs)
                   + beta_vec * environmental_profile(z, h, c_coeffs))
        sig_env = Cb @ eps_env
        for order, inds in enumerate(ACTIVE):
            env_resultants[STARTS[order]:STARTS[order + 1]] += wz * (z ** order) * sig_env[list(inds)]

    return env_resultants


def compute_stiffness_and_environment_resultants(
    h: float,
    material_mode: str = "isotropic",
    E: float | None = None,
    nu: float | None = None,
    alpha: float = 0.0,
    beta: float = 0.0,
    layers: list[LayerProperty] | None = None,
    t_coeffs: tuple[float, float, float] | None = None,
    c_coeffs: tuple[float, float, float] | None = None,
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

    for ply in active_layers:
        validate_layer(ply)

    M = [np.zeros((4, 4), dtype=float) for _ in range(7)]
    S = [np.zeros((2, 2), dtype=float) for _ in range(7)]
    env_resultants = environmental_resultants(h, material_mode, E, nu, alpha, beta, active_layers, t_coeffs, c_coeffs)

    for z, wz, Cb, Cs, _, _ in _thickness_points(h, material_mode, E, nu, alpha, beta, active_layers):

        for k in range(7):
            zk = wz * (z ** k)
            M[k] += zk * Cb
            S[k] += zk * Cs

    Db = np.zeros((15, 15), dtype=float)
    for i, inds_i in enumerate(ACTIVE):
        for j, inds_j in enumerate(ACTIVE):
            Db[STARTS[i]:STARTS[i + 1], STARTS[j]:STARTS[j + 1]] = M[i + j][np.ix_(inds_i, inds_j)]

    Ds = np.zeros((8, 8), dtype=float)
    for i in range(4):
        for j in range(4):
            Ds[2 * i:2 * i + 2, 2 * j:2 * j + 2] = S[i + j]

    return Db, Ds, env_resultants, active_layers


def reference_flexural_rigidity(
    h: float,
    material_mode: str,
    E: float | None = None,
    nu: float | None = None,
    layers: list[LayerProperty] | None = None,
) -> tuple[float, float]:
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
