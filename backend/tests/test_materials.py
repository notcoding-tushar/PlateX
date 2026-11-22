import numpy as np
import pytest

from hosnt12.materials import (
    compute_stiffness_and_environment_resultants,
    default_three_layer_laminate,
    layer_at_z,
    reference_flexural_rigidity,
)
from hosnt12.schemas import AnalysisConfig


@pytest.mark.parametrize("inputs", [{}, {"E": 3e9}, {"nu": 0.3}])
def test_missing_isotropic_inputs(inputs):
    with pytest.raises(ValueError, match="requires E and nu"):
        AnalysisConfig(**inputs)


def test_iso_equivalent_stack():
    E, nu, h = 35e9, 0.2, 0.25
    G = E / (2 * (1 + nu))
    stack = default_three_layer_laminate(h, E1=E, E2=E, nu12=nu, G12=G, G13=G, G23=G)
    expected = E * h**3 / (12 * (1 - nu**2))
    assert reference_flexural_rigidity(h, "laminate", layers=stack) == pytest.approx(
        (expected, expected), rel=1e-14
    )


def test_interface_d11_and_inert_properties():
    stack = default_three_layer_laminate(0.1)
    top, core, _ = stack
    assert layer_at_z(stack, top.h_bottom, "below") is core
    assert layer_at_z(stack[::-1], top.h_bottom, "above") is top
    kw = {"h": 0.1, "material_mode": "laminate", "t_coeffs": (1, 4, 2), "c_coeffs": (0, 3, 1)}
    Db, Ds, env, _ = compute_stiffness_and_environment_resultants(layers=stack, **kw)
    assert reference_flexural_rigidity(0.1, "laminate", layers=stack)[0] == pytest.approx(Db[4, 4], rel=1e-12)
    inert = default_three_layer_laminate(0.1, E3=3e9, nu23=0.4, nu13=0.1, alpha3=0.05, beta3=0.8)
    for old, new in zip((Db, Ds, env), compute_stiffness_and_environment_resultants(layers=inert, **kw)):
        np.testing.assert_array_equal(old, new)
