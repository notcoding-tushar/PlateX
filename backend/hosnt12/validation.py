import math

import numpy as np

from .loads import patch_load_vector
from .materials import (
    compute_stiffness_and_environment_resultants,
    default_three_layer_laminate,
    reference_flexural_rigidity,
)
from .mesh import build_mesh
from .schemas import (
    ContactPatch,
    H2MeshResult,
    H2Refinement,
    PaperComparison,
    PaperValidationReport,
    PaperValidationRequest,
    VehicleLoad,
)
from .solver import solve_hosnt12_legacy as solve_hosnt12

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


def solve_paper_case(K0, J0, mesh, hygrothermal=False, m=None, n=None) -> dict:
    """One ceramic benchmark case of the paper, SI units."""
    kw = {"m": m or mesh, "n": n or mesh, "material_mode": "isotropic", "E": PAPER_E, "nu": PAPER_NU, "K0": K0, "J0": J0}
    if hygrothermal:
        return solve_hosnt12(q0=PAPER_Q0_TABLE_3, alpha=PAPER_ALPHA, beta=0.0,
                             t_coeffs=(0, 10, 0), c_coeffs=(0, 100, 0), **kw)
    return solve_hosnt12(q0=PAPER_Q0_TABLE_2, alpha=PAPER_ALPHA, beta=0.0,
                         t_coeffs=(0, 0, 0), c_coeffs=(0, 0, 0), **kw)


def paper_validation_report(request: PaperValidationRequest) -> PaperValidationReport:
    """Compare eight independent 10 x 10 TSDT solves using unrounded values."""
    comparisons = []
    passed_cases, failed_cases = [], []
    for table, prefix, references in ((2, "M", PAPER_TABLE_2_TSDT), (3, "H", PAPER_TABLE_3_TSDT)):
        for index, ((k0, j0), reference_row) in enumerate(references.items(), 1):
            case = f"{prefix}{index}"
            solved = solve_paper_case(k0, j0, 10, hygrothermal=(table == 3))
            rows = []
            for parameter, reference in zip(_NORMALISED, reference_row, strict=True):
                computed = solved[parameter]
                absolute_error = abs(computed - reference)
                error_pct = 100 * absolute_error / abs(reference)
                rows.append(PaperComparison(
                    case=case, table=table, K0=k0, J0=j0, parameter=parameter, reference=reference,
                    computed=computed, absolute_error=absolute_error, error_pct=error_pct,
                    passed=error_pct <= request.tolerance_pct,
                ))
            comparisons.extend(rows)
            if all(row.passed for row in rows):
                passed_cases.append(case)
            else:
                failed_cases.append(case)
    return PaperValidationReport(
        tolerance_pct=request.tolerance_pct, comparisons=comparisons,
        passed_cases=passed_cases, failed_cases=failed_cases,
        mean_error_pct=math.fsum(row.error_pct for row in comparisons) / len(comparisons),
        worst=max(comparisons, key=lambda row: row.error_pct),
    )


def run_paper_validation(mesh: int = 10) -> None:
    """Print the paper-vs-Python comparison for Table 2 (mechanical) and Table 3 (hygrothermal), ceramic rows.

    The ceramic has beta = 0, so Table 3 checks the thermal path only; moisture expansion is tested
    separately (--selftest) because the paper's ceramic cannot exercise it."""
    line = "=" * 82
    print("\n" + line)
    print(f"  VALIDATION AGAINST ZIDI ET AL. (2014) | homogeneous ceramic, SSSS | mesh {mesh}x{mesh}")
    print("  a = 1 m, b = 3 m, h = 0.1 m, E = 117 GPa, nu = 1/3, sinusoidal q0")
    print("  NOTE: the load scale of Table 3 is ambiguous in the paper (q0 = 100 GPa with alpha = 7.11e-6 gives")
    print(f"  E*alpha*t2/q0 = 8.3e-5, but the table needs 83.2). q0 = {PAPER_Q0_TABLE_3:g} Pa with alpha as printed is an")
    print("  ASSUMPTION that reproduces Table 3, not a confirmed reading of the paper (see PAPER_Q0_TABLE_3).")
    print(line)
    tables = (
        (f"Table 2 (TSDT) | q0 = {PAPER_Q0_TABLE_2:g} Pa, no thermal/moisture", PAPER_TABLE_2_TSDT, False),
        ("Table 2 (FSDT) | same inputs", PAPER_TABLE_2_FSDT, False),
        ((f"Table 3 (TSDT) | q0 = {PAPER_Q0_TABLE_3:g} Pa, alpha = {PAPER_ALPHA:g}, beta = 0, "
         "t = (0, 10, 0), c = (0, 100, 0)"), PAPER_TABLE_3_TSDT, True),
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


def h2_stress_refinement() -> H2Refinement:
    """Sample the same top-centre stress on three even meshes and estimate its mesh limit."""
    meshes = (10, 14, 20)
    rows = []
    for mesh in meshes:
        result = solve_paper_case(100, 0, mesh, hygrothermal=True)
        rows.append(H2MeshResult(mesh=mesh, w_bar=result["w_bar"], sigma_x_bar=result["sigma_x_bar"]))
    coarse, medium, fine = rows
    order = _observed_order(coarse.sigma_x_bar, medium.sigma_x_bar, fine.sigma_x_bar, *meshes)
    estimate = None
    if math.isfinite(order):
        estimate = fine.sigma_x_bar + (fine.sigma_x_bar - medium.sigma_x_bar) / (
            (fine.mesh / medium.mesh) ** order - 1.0
        )
    return H2Refinement(meshes=rows, stress_reference=PAPER_TABLE_3_TSDT[100, 0][1],
                        observed_order=order if estimate is not None else None, stress_limit_estimate=estimate)


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
        history: list[tuple[int, list[float]]] = []
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
            extrap = [v3[k] + (v3[k] - v2[k]) / ((n3 / n2) ** o - 1.0) if math.isfinite(o) else float("nan")
                      for k, o in enumerate(orders)]
            print(f"  observed order ({n1},{n2},{n3}) : " + " | ".join(f"{n} {o:.2f}" for n, o in zip(_NORMALISED, orders)))
            print("  Richardson extrapolation : " + " | ".join(f"{n} {v:+.5f}" for n, v in zip(_NORMALISED, extrap)))
    print("\n" + line)


def run_self_tests() -> bool:
    """Regression and functional checks; returns True when every check passes."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, info: str = ""):
        results.append((name, bool(cond), info))

    def same(x, y, tol=1e-9):
        return abs(x - y) <= tol * max(abs(y), 1e-300)

    iso = {"material_mode": "isotropic", "E": PAPER_E, "nu": PAPER_NU}
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
    steel = {"material_mode": "isotropic", "E": 200e9, "nu": 0.3}
    alum = {"material_mode": "isotropic", "E": 70e9, "nu": 0.3}
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
    sq = {"a": 1.0, "b": 1.0, "m": 6, "n": 6, "q0": 1e3, "material_mode": "laminate"}
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
    D11_ref = sum(ply.E1 / (1 - ply.nu12 ** 2 * ply.E2 / ply.E1) * (ply.h_top ** 3 - ply.h_bottom ** 3) / 3.0 if ply.theta_rad == 0.0
                  else ply.E2 / (1 - ply.nu12 ** 2 * ply.E2 / ply.E1) * (ply.h_top ** 3 - ply.h_bottom ** 3) / 3.0 for ply in stack)
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
    kj = {"m": 6, "n": 6, "q0": 5e3, "K0": 100, "J0": 100}
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
    kw = {"a": 1.0, "b": 3.0, "m": 6, "n": 6, "q0": 1e5, "material_mode": "laminate"}
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
        pert = solve_hosnt12(layers=default_three_layer_laminate(0.1, **{"alpha1": 2e-6, "alpha2": 20e-6, "beta1": 0.01, "beta2": 0.3, key: val}),
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
        tot = sum(patch_load_vector(coords[el], [ContactPatch(x_m=a_/2, y_m=b_/2, length_m=ps, width_m=ps, force_N=1000)]).sum() for el in els)
        ok_patch &= same(tot, 1000.0, 1e-12)
    check("vehicle patch load totals the requested force on every mesh", ok_patch)
    veh = solve_hosnt12(m=6, n=6, q0=0.0, vehicle_load=VehicleLoad(patches=[ContactPatch(x_m=0.5, y_m=1.5, length_m=0.2, width_m=0.2, force_N=1000)],
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
