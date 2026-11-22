import csv
import os

import numpy as np


def plot_deflection(r: dict):
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


def export_results_csv(r: dict, filepath: str = "HOSNT12_results.csv"):
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
