import math

import numpy as np
import pytest

from hosnt12.boundary import constrained_dofs
from hosnt12.constants import DOF, T3, T3S, WS
from hosnt12.elements import element_geometry, shape_q8
from hosnt12.loads import patch_load_vector
from hosnt12.mesh import build_mesh
from hosnt12.schemas import ContactPatch


def test_clockwise_q8_and_jacobian():
    mesh = build_mesh(2, 3, 2, 1)
    ce = mesh.coords[mesh.elements[0]]
    np.testing.assert_array_equal(
        ce, [[0, 3], [0.5, 3], [1, 3], [1, 1.5], [1, 0], [0.5, 0], [0, 0], [0, 1.5]]
    )
    for i, (x, y) in enumerate(ce):
        np.testing.assert_array_equal(shape_q8(2 * x - 1, 2 * y / 3 - 1)[0], np.eye(8)[i])
    N, dx, dy, jacobian = element_geometry(ce, 0.31, -0.25)
    np.testing.assert_allclose([N.sum(), dx.sum(), dy.sum(), jacobian], [1, 0, 0, 0.75], atol=1e-15)


@pytest.mark.parametrize("bc", range(1, 7))
def test_thickness_constraints_at_every_node(bc):
    mesh = build_mesh(1, 2, 2, 2)
    fixed = constrained_dofs(mesh.coords, 1, 2, bc)
    assert np.isin(np.arange(len(mesh.coords))[:, None] * DOF + [T3, WS, T3S], fixed).all()


@pytest.mark.parametrize(
    "geometry", [{"shape": "circle", "radius_m": 0.23}, {"length_m": 0.46, "width_m": 0.3}]
)
@pytest.mark.parametrize("x,y,fraction", [(0.44, 0.47, 1), (0, 0.5, 0.5), (0, 0, 0.25), (-0.5, 0.5, 0)])
def test_patch_overlap(geometry, x, y, fraction):
    mesh = build_mesh(1, 1, 5, 3)
    patch = ContactPatch(x_m=x, y_m=y, force_N=143, **geometry)
    total = sum(patch_load_vector(mesh.coords[el], [patch]).sum() for el in mesh.elements)
    assert total == pytest.approx(143 * fraction, rel=1e-12, abs=0)


def test_circle_clipped_segment_area():
    mesh = build_mesh(1, 1, 4, 6)
    radius, offset = 0.2, 0.07
    patch = ContactPatch(x_m=-offset, y_m=0.37, shape="circle", radius_m=radius, force_N=39)
    area = radius**2 * math.acos(offset / radius) - offset * math.sqrt(radius**2 - offset**2)
    total = sum(patch_load_vector(mesh.coords[el], [patch]).sum() for el in mesh.elements)
    assert total == pytest.approx(area * patch.pressure_Pa, rel=1e-12)
