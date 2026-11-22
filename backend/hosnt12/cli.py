import sys

from .constants import BOUNDARY_CONDITIONS, PRESET_LAMINATE_PROPERTIES
from .io_utils import export_results_csv, plot_deflection
from .materials import default_three_layer_laminate
from .schemas import ContactPatch, VehicleLoad
from .solver import solve_hosnt12_legacy as solve_hosnt12
from .validation import run_convergence_study, run_paper_validation, run_self_tests


def _read_value(prompt: str, default: str, cast):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return cast(default)
        try:
            return cast(raw)
        except (TypeError, ValueError):
            print("  [INPUT ERROR] Enter a valid number or press Enter for default.")


def _read_choice(prompt: str, choices: tuple[int, ...], default: int) -> int:
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


def collect_terminal_inputs() -> dict:
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
    lam_props: dict[str, float] = {}
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
        vehicle_load = VehicleLoad(patches=[ContactPatch(x_m=a/2, y_m=b/2, length_m=patch_size, width_m=patch_size, force_N=wheel_force)])
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


def print_results(r: dict):
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

def interactive():
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
        except (ValueError, RuntimeError, OSError, ImportError) as exc:
            print(f"\n[ERROR] {exc}")

        print("\n" + "-" * 68)
        again = input("Run another analysis? (y/n) [y]: ").strip().lower()
        if again in ("n", "no"):
            print("Shutting down HOSNT12 solver. Goodbye!")
            break


def main():
    if "--selftest" in sys.argv[1:]:
        sys.exit(0 if run_self_tests() else 1)
    if "--convergence" in sys.argv[1:]:
        run_convergence_study()
        sys.exit(0)
    if "--validate" in sys.argv[1:]:
        extra = [x for x in sys.argv[1:] if x.isdigit()]
        run_paper_validation(int(extra[0]) if extra else 10)
        sys.exit(0)
    interactive()

if __name__ == "__main__":
    main()
