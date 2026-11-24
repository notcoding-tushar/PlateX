"""Static, fully bonded isotropic half-space under vertical circular pressures.

Depth and displacement are positive downwards, normal stress is tensile positive.
Each Fourier wave is a plane-strain problem; angular inversion gives J0, J1,
and J2 kernels. There are no finite edges, mesh, or subgrade truncation.
"""

import math

import numpy as np
from scipy.integrate import quad_vec
from scipy.special import j0, j1, jv, roots_legendre

from ..schemas import ContactPatch, DepthPoint, ElasticLayer, ElasticResponse


def _basis(k, depth, layer):
    """F and its first three derivatives in t=k*z. F solves (D²-1)²F=0.

    Anchor each exponential at its decaying end to avoid exp(+k*h).
    Only the two downward-decaying modes are admissible in the half-space.
    """
    ends = [(k * depth, -1)]
    if layer.thickness_m is not None:
        ends.append((k * (layer.thickness_m - depth), 1))
    columns = []
    for distance, sign in ends:
        decay = np.exp(-distance)
        columns.extend(
            [
                np.stack([sign**n * decay for n in range(4)], axis=1),
                np.stack([sign**n * (distance - n) * decay for n in range(4)], axis=1),
            ]
        )
    return np.stack(columns, axis=-1)


def _state(basis, nu, ratio):
    f, d1, d2, d3 = basis.transpose(1, 0, 2)
    # Normal/shear traction, horizontal strain amplitude, and k*w.
    # Displacement rows are scaled by one common reference shear modulus.
    return np.stack(
        [f, d1, ratio * ((1 - nu) * d2 + nu * f), ratio * ((1 - nu) * d3 + (nu - 2) * d1)], axis=1
    )


def _spectrum(k, layers, index, local_z):
    size = 4 * len(layers) - 2
    matrix = np.zeros((len(k), size, size))
    rhs = np.zeros((len(k), size, 1))
    rhs[:, 0] = 1  # unit compressive pressure, zero shear
    reference = layers[-1].E_Pa / (1 + layers[-1].nu)
    for i, layer in enumerate(layers):
        cols = slice(4 * i, 4 * i + (2 if layer.thickness_m is None else 4))
        ratio = reference * (1 + layer.nu) / layer.E_Pa
        top = _state(_basis(k, 0, layer), layer.nu, ratio)
        if i == 0:
            matrix[:, :2, cols] = top[:, :2]
        else:
            matrix[:, 4 * i - 2 : 4 * i + 2, cols] = -top
        if layer.thickness_m is not None:
            matrix[:, 4 * i + 2 : 4 * i + 6, cols] = _state(
                _basis(k, layer.thickness_m, layer), layer.nu, ratio
            )
    try:
        coefficients = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Ill-conditioned layered-elastic interface system.") from exc
    basis = _basis(k, local_z, layers[index])
    start = 4 * index
    return (basis @ coefficients[:, start : start + basis.shape[2]])[:, :, 0].T


def _homogeneous(r, z, a, layer):
    """Unit disk pressure integrated in physical space for the shallow direct field.

    Integrate Boussinesq point loads along rays from the observation point.
    Radial antiderivatives leave one finite angular integral. At the traction
    discontinuity use the mean surface trace. Returns w, zz, rr, tt, rz.
    """
    nu = layer.nu
    twice_g = layer.E_Pa / (1 + nu)
    angle = math.asin(min(1.0, a / r)) if r >= a else math.pi

    def ray(phi):
        c, s = math.cos(phi), math.sin(phi)
        chord = math.sqrt(max(0.0, (a - r * s) * (a + r * s)))
        far = r * c + chord
        # The observation point lies inside the disk when r<a. At r=a the
        # entry is exactly zero, including for very shallow depth queries.
        near = (r - a) * (r + a) / far if r > a else 0.0
        if r < a and c < 0:
            far = (a - r) * (a + r) / (chord - r * c)
        if z == 0:
            return 2 * (1 - nu) * (far - near) / a
        lo, hi = math.hypot(near, z), math.hypot(far, z)
        u, v = z / lo, z / hi
        # Evaluate endpoint differences without subtracting nearly equal radii
        # at large depths. Scale w by 2G/a during the angular error estimate.
        distance_change = (far - near) * ((far + near) / (hi + lo))
        du = u * (distance_change / hi)
        vertical = -du * (u * u + u * v + v * v)
        log_ratio = math.log1p(distance_change / (lo + z))
        radial = -3 * du - vertical + (1 - 2 * nu) * log_ratio
        hoop = (1 - 2 * nu) * (du - log_ratio)
        w = (2 * (1 - nu) * distance_change + z * du) / a
        sin_far, sin_near = far / hi, near / lo
        ds = du * (u + v) / (sin_far + sin_near) if sin_far + sin_near else 0.0
        return np.array(
            [
                w,
                vertical,
                radial * c * c + hoop * s * s,
                radial * s * s + hoop * c * c,
                -c * ds * (sin_far**2 + sin_far * sin_near + sin_near**2),
            ]
        )

    integral, _, info = quad_vec(ray, 0, angle, epsabs=1e-13, epsrel=1e-10, full_output=True)
    if not info.success:
        raise ValueError("Direct disk quadrature did not converge at the requested point.")
    integral /= math.pi
    if z:
        integral[0] *= a / twice_g
        return integral
    inside = 0.5 if math.isclose(r, a, rel_tol=1e-14) else float(r < a)
    hoop_weight = 0.5 if r <= a else 0.5 * (a / r) ** 2
    return np.array(
        [
            integral * a / twice_g,
            -inside,
            -inside + (1 - 2 * nu) * hoop_weight,
            -2 * nu * inside - (1 - 2 * nu) * hoop_weight,
            0.0,
        ]
    )


def _disk_response(layers, index, local_z, z, r, a):
    layer = layers[index]
    if len(layers) == 1:
        return _homogeneous(r, z, a, layer)
    # Subtract the known direct half-space field in layer one. The remaining
    # high-frequency spectrum decays exponentially even at the loaded surface.
    direct = _homogeneous(r, z, a, layer) if index == 0 else np.zeros(5)
    decay_depth = max(z, layers[0].thickness_m)
    stack_depth = sum(item.thickness_m or 0 for item in layers)
    twice_g = layer.E_Pa / (1 + layer.nu)

    def integrate(order, cut):
        limit = cut / decay_depth
        # Resolve long-wave interface effects and the fastest Bessel oscillation.
        width = 2 * math.pi / (a + r)
        if limit / width > 6000:
            raise ValueError("Requested offset exceeds the resolved Hankel integration range.")
        edges = [0.0]
        while edges[-1] < limit:
            step = min(width, max(0.05 / stack_depth, edges[-1]))
            edges.append(min(limit, edges[-1] + step))
        edges = np.asarray(edges)
        nodes, weights = roots_legendre(order)
        total = np.zeros(5)
        for start in range(0, len(edges) - 1, 32):
            panel = edges[start : start + 33]
            half = 0.5 * np.diff(panel)[:, None]
            k = (panel[:-1, None] + half * (1 + nodes)).ravel()
            measure = (half * weights).ravel() * a * j1(k * a)
            f, d1, d2, d3 = _spectrum(k, layers, index, local_z)
            if index == 0:
                t = k * z
                exponential = np.exp(-t)
                f -= (1 + t) * exponential
                d1 += t * exponential
                d2 -= (t - 1) * exponential
                d3 -= (2 - t) * exponential
            b0, b2 = j0(k * r), jv(2, k * r)
            # For one wave the Airy function gives stresses (-F, F'', nu*(F''-F))
            # in vertical, parallel, and transverse directions respectively.
            transverse = layer.nu * (d2 - f)
            mean = 0.5 * (d2 + transverse) * b0
            difference = 0.5 * (d2 - transverse) * b2
            kw = ((1 - layer.nu) * d3 + (layer.nu - 2) * d1) / twice_g
            kernels = np.array([kw * b0 / k, -f * b0, mean - difference, mean + difference, d1 * j1(k * r)])
            total += kernels @ measure
        return direct + total

    coarse = integrate(8, 32)
    fine = integrate(16, 48)
    absolute = 1e-9 * np.array([a / twice_g, 1, 1, 1, 1])
    if not np.allclose(coarse, fine, atol=absolute, rtol=2e-6):
        refined = integrate(32, 64)
        if not np.allclose(refined, fine, atol=absolute, rtol=2e-6):
            raise ValueError("Hankel quadrature did not converge for this stack and location.")
        return refined
    return fine


def solve_layered_elastic(
    layers: list[ElasticLayer], patches: list[ContactPatch], points: list[DepthPoint]
) -> list[ElasticResponse]:
    """Superpose wheel tensors in one frame. r points from the contact centroid
    to the query, with +x at the centroid. theta is perpendicular in plan.
    """
    if (
        not layers
        or layers[-1].thickness_m is not None
        or any(layer.thickness_m is None for layer in layers[:-1])
    ):
        raise ValueError("Supply finite upper layers followed by one semi-infinite layer.")
    if len(patches) not in (1, 2) or any(p.shape != "circle" for p in patches):
        raise ValueError("Supply one or two circular wheel loads.")
    boundaries = np.cumsum([layer.thickness_m for layer in layers[:-1]])
    centre = np.mean([[p.x_m, p.y_m] for p in patches], axis=0)
    cache = {}
    results = []
    for point in points:
        z = point.depth_m
        # Snap roundoff only, so an exact catalogue depth selects its named side.
        matches = boundaries[np.isclose(boundaries, z, rtol=2e-15, atol=0)]
        if len(matches):
            z = matches[0]
        index = np.searchsorted(boundaries, z, side="left" if point.side == "above" else "right")
        local_z = z - (boundaries[index - 1] if index else 0.0)
        layer = layers[index]
        pos = np.array([point.x_m, point.y_m])
        angle = math.atan2(point.y_m - centre[1], point.x_m - centre[0])
        w = zz = rr = tt = rz = rt = 0.0
        for patch in patches:
            dx, dy = pos - [patch.x_m, patch.y_m]
            r = math.hypot(dx, dy)
            key = index, z, r, patch.radius_m
            if key not in cache:
                cache[key] = _disk_response(layers, index, local_z, z, r, patch.radius_m)
            disp, vertical, radial, hoop, shear = patch.pressure_Pa * cache[key]
            delta = math.atan2(dy, dx) - angle
            c, s = math.cos(delta), math.sin(delta)
            w += disp
            zz += vertical
            rr += radial * c * c + hoop * s * s
            tt += radial * s * s + hoop * c * c
            rt += (radial - hoop) * s * c
            rz += shear * c
        e, nu = layer.E_Pa, layer.nu
        principal = 0.5 * (rr + tt) + math.hypot(0.5 * (rr - tt), rt)
        results.append(
            ElasticResponse(
                **point.model_dump(),
                layer=layer.name,
                w_m=w,
                sigma_z_Pa=zz,
                sigma_r_Pa=rr,
                sigma_theta_Pa=tt,
                tau_rz_Pa=rz,
                eps_z=(zz - nu * (rr + tt)) / e,
                eps_r=(rr - nu * (tt + zz)) / e,
                eps_theta=(tt - nu * (rr + zz)) / e,
                max_horizontal_stress_Pa=principal,
                max_horizontal_strain=((1 + nu) * principal - nu * (rr + tt + zz)) / e,
            )
        )
    return results
