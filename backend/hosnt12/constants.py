"""Core constants and DOF mappings for the HOSNT12 Q8 plate element."""
from __future__ import annotations

from typing import Dict

# 12 degrees of freedom per node:
# [u0, v0, w0, theta1, theta2, theta3, u0*, v0*, w0*, theta1*, theta2*, theta3*]
DOF: int = 12
U, V, W, T1, T2, T3, US, VS, WS, T1S, T2S, T3S = range(DOF)

BOUNDARY_CONDITIONS: Dict[int, str] = {
    1: "Simply supported on all four sides (SSSS)",
    2: "Clamped on all four sides (CCCC)",
    3: "Simply supported at x=0,a; Free at y=0,b (SFSF)",
    4: "Simply supported at y=0,b; Free at x=0,a (FSFS)",
    5: "Simply supported at x=0,a; Clamped at y=0,b (SCSC)",
    6: "Simply supported at y=0,b; Clamped at x=0,a (CSCS)",
}

PRESET_LAMINATE_PROPERTIES: Dict[str, float] = {
    "E1": 181e9,
    "E2": 10.3e9,
    "E3": 10.3e9,
    "nu12": 0.28,
    "nu23": 0.28,
    "nu13": 0.28,
    "G12": 7.17e9,
    "G13": 7.17e9,
    "G23": 2.39e9,
    "alpha1": 0.0,
    "alpha2": 0.006,
    "alpha3": 0.0,
    "beta1": 0.0,
    "beta2": 0.0,
    "beta3": 0.0,
}
