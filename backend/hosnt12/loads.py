"""Consistent element and global load vectors in SI units."""

import itertools
import math
from collections.abc import Sequence

import numpy as np

from .constants import DOF, W
from .elements import b_matrices, element_geometry, shape_q8, shape_q8_second
from .materials import environmental_resultants
from .mesh import MeshData
from .schemas import AnalysisConfig, ContactPatch

GAUSS3, WEIGHTS3 = np.polynomial.legendre.leggauss(3)
ANGLE_POINTS, ANGLE_WEIGHTS = np.polynomial.legendre.leggauss(16)


def sinusoidal_field(x, y, a, b):
    return math.sin(math.pi * x / a) * math.sin(math.pi * y / b)


def _circle_vector(x0, x1, y0, y1, patch):
    """Integrate vertical chords with x = xc + r sin(theta) to smooth the endpoints."""
    xc, yc, radius = patch.x_m, patch.y_m, patch.radius_m
    left, right = max(-1.0, (x0 - xc) / radius), min(1.0, (x1 - xc) / radius)
    out = np.zeros(8)
    if right <= left or y1 <= yc - radius or y0 >= yc + radius:
        return out
    cuts = {left, right}
    for edge in (y0, y1):
        v = (edge - yc) / radius
        if abs(v) < 1:
            crossing = math.sqrt(1 - v * v)
            cuts.update(u for u in (-crossing, crossing) if left < u < right)
    angles = sorted(math.asin(u) for u in cuts)
    for start, end in itertools.pairwise(angles):
        half_angle = (end - start) / 2
        for u, wu in zip(ANGLE_POINTS, ANGLE_WEIGHTS):
            theta = (end + start) / 2 + half_angle * u
            half_chord = radius * math.cos(theta)
            x = xc + radius * math.sin(theta)
            low, high = max(y0, yc - half_chord), min(y1, yc + half_chord)
            if low >= high:
                continue
            half_y = (high - low) / 2
            for v, wv in zip(GAUSS3, WEIGHTS3):
                y = (low + high) / 2 + half_y * v
                N = shape_q8(2 * (x - x0) / (x1 - x0) - 1, 2 * (y - y0) / (y1 - y0) - 1)[0]
                out += N * patch.pressure_Pa * (half_chord * half_angle * wu) * (half_y * wv)
    return out


def patch_load_vector(ce: np.ndarray, patches: Sequence[ContactPatch]) -> np.ndarray:
    """Integrate the original patch pressure over its overlap with this element."""
    gpts, gwts = GAUSS3, WEIGHTS3
    x0, x1 = ce[:, 0].min(), ce[:, 0].max()
    y0, y1 = ce[:, 1].min(), ce[:, 1].max()
    out = np.zeros(8, dtype=float)
    for patch in patches:
        if patch.shape == "circle":
            out += _circle_vector(x0, x1, y0, y1, patch)
            continue
        xc, yc = patch.x_m, patch.y_m
        dx_p, dy_p = patch.length_m, patch.width_m
        lx0, lx1 = max(x0, xc - 0.5 * dx_p), min(x1, xc + 0.5 * dx_p)
        ly0, ly1 = max(y0, yc - 0.5 * dy_p), min(y1, yc + 0.5 * dy_p)
        if lx1 <= lx0 or ly1 <= ly0:
            continue
        pressure = patch.pressure_Pa
        hx, hy = 0.5 * (lx1 - lx0), 0.5 * (ly1 - ly0)
        for u, wu in zip(gpts, gwts):
            for v, wv in zip(gpts, gwts):
                xp, yp = 0.5 * (lx0 + lx1) + hx * u, 0.5 * (ly0 + ly1) + hy * v
                N, _, _ = shape_q8(2.0 * (xp - x0) / (x1 - x0) - 1.0, 2.0 * (yp - y0) / (y1 - y0) - 1.0)
                out += N * pressure * wu * wv * hx * hy
    return out


def assemble_rhs(config: AnalysisConfig, mesh: MeshData, layers) -> np.ndarray:
    coords, elements, _ = mesh
    a, b, m, n = config.a, config.b, config.m, config.n
    q0, vehicle_load = config.q0, config.vehicle_load
    env_resultants = environmental_resultants(
        config.h,
        config.material_mode,
        config.E,
        config.nu,
        config.alpha,
        config.beta,
        layers,
        config.t_coeffs,
        config.c_coeffs,
    )
    has_environment = np.any(env_resultants)
    gp3, gw3 = GAUSS3, WEIGHTS3
    Fglob = np.zeros(len(coords) * DOF)
    local_w_dofs = np.arange(8) * DOF + W

    for el in elements:
        ce = coords[el]
        edofs = (el[:, None] * DOF + np.arange(DOF)).reshape(-1)
        Fe = np.zeros(8 * DOF, dtype=float)
        if vehicle_load and vehicle_load.patches:
            Fe[local_w_dofs] += patch_load_vector(ce, vehicle_load.patches)

        for xi, wx in zip(gp3, gw3):
            for eta, wy in zip(gp3, gw3):
                N, dNx, dNy, detJ = element_geometry(ce, xi, eta)
                dA = wx * wy * detJ
                xgp = float(N @ ce[:, 0])
                ygp = float(N @ ce[:, 1])
                spatial = sinusoidal_field(xgp, ygp, a, b)

                if q0 > 0.0:
                    pressure = q0 if config.load_case == "uniform" else q0 * spatial
                    d2xi, d2eta, _ = shape_q8_second(xi, eta)
                    d2Ndx2 = d2xi * (2.0 / (a / m)) ** 2
                    d2Ndy2 = d2eta * (2.0 / (b / n)) ** 2
                    load_shape = N - config.nonlocal_parameter * (d2Ndx2 + d2Ndy2)
                    Fe[local_w_dofs] += load_shape * pressure * dA

                if has_environment:
                    Bb, _ = b_matrices(N, dNx, dNy)
                    if config.thermal_distribution == "uniform":
                        spatial = 1.0
                    Fe += (Bb.T @ env_resultants) * (spatial * dA)
        np.add.at(Fglob, edofs, Fe)

    if vehicle_load and vehicle_load.nodal_loads:
        for node_1based, f_val in vehicle_load.nodal_loads:
            node_idx = int(node_1based) - 1
            if 0 <= node_idx < coords.shape[0]:
                Fglob[node_idx * DOF + W] += float(f_val)
    return Fglob
