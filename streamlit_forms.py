"""Streamlit interface to the existing PlateX analysis engines."""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from hosnt12.constants import BOUNDARY_CONDITIONS, PRESET_LAMINATE_PROPERTIES  # noqa: E402
from hosnt12.irc import adapters  # noqa: E402
from hosnt12.schemas import AnalysisConfig, LayeredElasticRequest  # noqa: E402
from hosnt12.solver import solve_hosnt12  # noqa: E402

@st.cache_data
def catalogue_options():
    return adapters.catalogue_options().model_dump(mode="json")


def show_notes(result):
    for message in result.modeling_notes:
        st.info(message)
    for message in getattr(result, "solver_warnings", []):
        st.warning(message)
    with st.expander("Full result and sources"):
        st.json(result.model_dump(mode="json"), expanded=False)


def plate_results(result):
    st.subheader("Plate results")
    a, b, c = st.columns(3)
    a.metric("Centre deflection (m)", f"{result.w_center_m:.6g}")
    b.metric("Maximum absolute deflection (m)", f"{result.max_abs_deflection_m:.6g}")
    c.metric("Reference rigidity D (N m)", f"{result.flexural_rigidity_D_Nm:.6g}")
    st.caption(f"{result.nodes} nodes · {result.elements} elements · {result.free_dofs} free DOFs")
    st.write("Solver stress samples (Pa)")
    st.dataframe(pd.DataFrame([{"σx": result.sigma_x_pa, "τxy": result.tau_xy_pa,
                                "τxz": result.tau_xz_pa}]), hide_index=True)
    if result.point_results:
        st.write("Query point responses")
        st.dataframe(pd.DataFrame([p.model_dump() for p in result.point_results]), hide_index=True)
    if result.field:
        coords = np.asarray(result.field.coordinates)
        values = np.asarray(result.field.w_m)
        fig, ax = plt.subplots()
        try:
            contour = ax.tricontourf(coords[:, 0], coords[:, 1], values, levels=16, cmap="viridis")
            fig.colorbar(contour, ax=ax, label="w (m)")
            ax.set(xlabel="x (m)", ylabel="y (m)", title="Nodal deflection")
            ax.set_aspect("equal")
            st.pyplot(fig)
        finally:
            plt.close(fig)
        st.caption("Contours interpolate returned nodal values for display; they are not extra solver evaluations.")
    show_notes(result)


def layered_results(result):
    st.subheader("Layered-elastic results")
    a, b, c = st.columns(3)
    a.metric("Layers", len(result.layers))
    b.metric("Wheels", len(result.patches))
    c.metric("Contact pressure (Pa)", f"{result.pressure_Pa:.6g}")
    st.write("Resolved catalogue stack (SI units)")
    st.dataframe(pd.DataFrame([x.model_dump() for x in result.layers]), hide_index=True)
    st.write("Critical interface responses")
    st.dataframe(pd.DataFrame([x.model_dump() for x in result.critical]), hide_index=True)
    if result.points:
        st.write("Custom point responses")
        st.dataframe(pd.DataFrame([x.model_dump() for x in result.points]), hide_index=True)
    responses = result.critical + result.points
    if responses:
        fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
        try:
            # Unconnected points avoid suggesting that different locations form a depth profile.
            axes[0].scatter([p.sigma_z_Pa for p in responses], [p.depth_m for p in responses])
            axes[1].scatter([p.eps_z for p in responses], [p.depth_m for p in responses])
            axes[0].set(xlabel="σz (Pa)", ylabel="Depth (m)", title="Vertical stress")
            axes[1].set(xlabel="εz (dimensionless)", title="Vertical strain")
            axes[0].invert_yaxis()
            fig.tight_layout()
            st.pyplot(fig)
        finally:
            plt.close(fig)
        st.caption("Points may have different horizontal locations and interface sides; see the tables for coordinates.")
    if result.checks:
        st.write("Catalogue checks")
        st.dataframe(pd.DataFrame([{"name": x.name, "status": x.status, "message": x.message}
                                   for x in result.checks]), hide_index=True)
    show_notes(result)


def render_forms():
    st.title("PlateX")
    page = st.sidebar.radio("Analysis", ["HOSNT12 plate", "IRC:37 layered elastic"])
    if page == "HOSNT12 plate":
        st.subheader("HOSNT12 Q8 finite plate")
        st.info("Plane-stress plate: σz and thickness stretching are constrained. A finite plate is not a layered-elastic half-space. Check mesh and boundary sensitivity.")
        st.caption("Example values are editable, not material recommendations. Isotropic E and ν must be supplied.")
        with st.form("plate"):
            geometry, material, loading, advanced = st.tabs(["Geometry & supports", "Material & layup", "Loads & foundation", "Advanced JSON"])
            with geometry:
                x, y, z = st.columns(3)
                a = x.number_input("Length a (m)", min_value=1e-9, value=1.0)
                b = y.number_input("Width b (m)", min_value=1e-9, value=1.0)
                h = z.number_input("Thickness h (m)", min_value=1e-9, value=0.1, format="%.6f")
                x, y = st.columns(2)
                m = x.number_input("Elements along a (m)", min_value=1, value=4, step=1)
                n = y.number_input("Elements along b (n)", min_value=1, value=4, step=1)
                bc = st.selectbox("Boundary condition", list(BOUNDARY_CONDITIONS), format_func=lambda k: BOUNDARY_CONDITIONS[k])
            with material:
                mode = st.selectbox("Material mode", ["isotropic", "laminate"])
                x, y = st.columns(2)
                E = x.number_input("Isotropic E (Pa)", min_value=0.0, value=None, placeholder="Required for isotropic")
                nu = y.number_input("Isotropic ν", value=None, placeholder="Required for isotropic", format="%.5f")
                alpha = x.number_input("Isotropic thermal expansion α (1/K)", value=0.0, format="%.8g")
                beta = y.number_input("Isotropic moisture expansion β", value=0.0, format="%.8g")
                st.caption("For laminate mode, edit all ply rows. Bottom/top coordinates must cover −h/2 to +h/2. E3, ν23, ν13, α3 and β3 are accepted but inert in this plane-stress formulation.")
                example_ply = {"h_bottom": -0.05, "h_top": 0.05, **PRESET_LAMINATE_PROPERTIES, "theta_rad": 0.0}
                layers = st.data_editor(pd.DataFrame([example_ply]), num_rows="dynamic", key="ply_editor", hide_index=True)
            with loading:
                x, y = st.columns(2)
                load_case = x.selectbox("Distributed load", ["uniform", "sinusoidal"])
                q0 = y.number_input("Pressure q0 (Pa)", min_value=0.0, value=1000.0)
                st.markdown("**Optional contact patch**")
                patch_shape = st.selectbox("Patch", ["none", "circle", "rectangle"])
                x, y, z = st.columns(3)
                px = x.number_input("Patch centre x (m)", value=0.5)
                py = y.number_input("Patch centre y (m)", value=0.5)
                force = z.number_input("Patch force (N)", min_value=0.0, value=1000.0)
                x, y, z = st.columns(3)
                radius = x.number_input("Circle radius (m)", min_value=0.0, value=0.1)
                length = y.number_input("Rectangle length (m)", min_value=0.0, value=0.2)
                width = z.number_input("Rectangle width (m)", min_value=0.0, value=0.2)
                st.markdown("**Foundation and thermal loading**")
                x, y, z = st.columns(3)
                kw = x.number_input("Winkler Kw (N/m³)", min_value=0.0, value=0.0)
                kp = y.number_input("Pasternak Kp (N/m)", min_value=0.0, value=0.0)
                kpy = z.number_input("Pasternak Kp_y (N/m, optional)", min_value=0.0, value=None)
                thermal = st.checkbox("Apply thermal coefficients")
                t1, t2, t3 = st.columns(3)
                coeffs = [t1.number_input("T coefficient 1", value=0.0), t2.number_input("T coefficient 2", value=0.0), t3.number_input("T coefficient 3", value=0.0)]
                distribution = st.selectbox("Thermal in-plane distribution", ["sinusoidal", "uniform"])
                st.caption("Through-thickness coefficient definitions follow the solver's environmental profile.")
            with advanced:
                override = st.checkbox("Use Advanced JSON instead of structured plate inputs")
                raw = st.text_area("Complete AnalysisConfig JSON", value="{}", height=180)
                st.caption("JSON replaces all structured inputs for this solve; use it for nodal loads, multiple patches, query points and other schema options.")
            submit = st.form_submit_button("Solve plate", type="primary")
        if submit:
            try:
                if override:
                    config = AnalysisConfig.model_validate_json(raw)
                else:
                    data = {"a": a, "b": b, "h": h, "m": m, "n": n, "choicebc": bc,
                            "material_mode": mode, "E": E, "nu": nu, "alpha": alpha, "beta": beta,
                            "load_case": load_case, "q0": q0, "foundation": {"Kw": kw, "Kp": kp, "Kp_y": kpy},
                            "t_coeffs": coeffs if thermal else None, "thermal_distribution": distribution}
                    if mode == "laminate":
                        data["layers"] = layers.to_dict("records")
                        if not data["layers"]:
                            raise ValueError("Add at least one laminate layer.")
                    if patch_shape != "none":
                        patch = {"shape": patch_shape, "x_m": px, "y_m": py, "force_N": force}
                        patch.update({"radius_m": radius} if patch_shape == "circle" else {"length_m": length, "width_m": width})
                        data["vehicle_load"] = {"patches": [patch]}
                    config = AnalysisConfig.model_validate(data)
                with st.spinner("Solving plate…"):
                    st.session_state["plate_result"] = solve_hosnt12(config, include_field=True)
            except (ValueError, ArithmeticError, RuntimeError) as exc:
                st.error(str(exc))
        if "plate_result" in st.session_state:
            st.caption("Showing the last successful plate solve; edit inputs and submit to update it.")
            plate_results(st.session_state["plate_result"])
    else:
        st.subheader("IRC:37 layered elastic")
        st.info("Horizontally extended isotropic layers, bonded interfaces, half-space and circular contacts. Results do not establish complete IRC compliance or IITPAVE equivalence.")
        options = catalogue_options()
        with st.form("layered"):
            catalogue, wheel_tab, points_tab, advanced = st.tabs(["Catalogue", "Wheel loading", "Depth queries", "Advanced JSON"])
            with catalogue:
                x, y, z = st.columns(3)
                category = x.selectbox("Stack category", options["categories"])
                cbr = y.selectbox("Subgrade CBR (%)", options["cbr"], index=options["cbr"].index(5.0))
                traffic = z.selectbox("Traffic (MSA)", options["traffic_msa"], index=options["traffic_msa"].index(10.0))
                bitumen = st.number_input("Bituminous modulus (MPa)", min_value=0.0, value=2000.0)
                st.caption("The catalogue resolves layer thicknesses and materials; applicable modulus caps are reported with the results.")
            with wheel_tab:
                wheels = st.selectbox("Wheel arrangement", ["single", "dual"], index=1)
                ctb = st.checkbox("CTB fatigue standard contact")
                st.caption("Leave optional values blank to use the existing IRC standard contact. Force is per wheel; spacing applies only to dual wheels.")
                x, y, z = st.columns(3)
                wheel_force = x.number_input("Force per wheel (N, optional)", min_value=0.0, value=None)
                pressure = y.number_input("Contact pressure (Pa, optional)", min_value=0.0, value=None)
                spacing = z.number_input("Dual spacing (m, optional)", min_value=0.0, value=None, format="%.4f")
            with points_tab:
                st.caption("Critical interface responses are always calculated at wheel centre and, for dual wheels, pair midpoint. Add up to 64 custom locations; depth is positive down. Choose interface side explicitly.")
                points = st.data_editor(pd.DataFrame({"label": pd.Series(dtype="str"), "x_m": pd.Series(dtype="float64"), "y_m": pd.Series(dtype="float64"), "depth_m": pd.Series(dtype="float64"), "side": pd.Series(dtype="str")}),
                                        num_rows="dynamic", key="depth_editor", hide_index=True,
                                        column_config={"side": st.column_config.SelectboxColumn("side", options=["above", "below"], required=True)})
            with advanced:
                override = st.checkbox("Use Advanced JSON instead of structured IRC inputs")
                raw = st.text_area("Complete LayeredElasticRequest JSON", value="{}", height=180)
            submit = st.form_submit_button("Solve layered response", type="primary")
        if submit:
            try:
                if override:
                    request = LayeredElasticRequest.model_validate_json(raw)
                else:
                    request = LayeredElasticRequest.model_validate({"category": category, "cbr": cbr,
                        "traffic_msa": traffic, "bituminous_E_MPa": bitumen, "wheels": wheels,
                        "ctb_fatigue": ctb, "wheel_force_N": wheel_force, "pressure_Pa": pressure,
                        "spacing_m": spacing, "points": points.to_dict("records")})
                with st.spinner("Solving layered response…"):
                    st.session_state["layered_result"] = adapters.solve_flexible_layered(request)
            except (ValueError, ArithmeticError, RuntimeError) as exc:
                st.error(str(exc))
        if "layered_result" in st.session_state:
            st.caption("Showing the last successful layered-elastic solve; edit inputs and submit to update it.")
            layered_results(st.session_state["layered_result"])
