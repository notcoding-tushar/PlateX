
import numpy as np

from .constants import DOF, T1, T1S, T2, T2S, T3, T3S, US, VS, WS, U, V, W


def shape_q8(xi: float, eta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


def shape_q8_second(xi: float, eta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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

def b_matrices(N: np.ndarray, dNdx: np.ndarray, dNdy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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
