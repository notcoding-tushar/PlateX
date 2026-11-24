"""Streamlit entry point for the existing PlateX calculation engines."""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from hosnt12.irc import adapters  # noqa: E402
from hosnt12.schemas import AnalysisConfig, LayeredElasticRequest  # noqa: E402
from hosnt12.solver import solve_hosnt12  # noqa: E402

st.set_page_config(page_title="PlateX", layout="wide")
st.title("PlateX")
st.caption("Finite plate analysis and IRC:37 layered-elastic response · SI units")

@st.cache_data
def catalogue_options():
    return adapters.catalogue_options().model_dump(mode="json")

page = st.sidebar.radio("Analysis", ["HOSNT12 plate", "IRC:37 layered elastic"])
if page == "HOSNT12 plate":
    st.subheader("HOSNT12 Q8 finite plate")
    st.info("Plane-stress higher-order plate model: σz and thickness stretching are constrained. A finite plate or subgrade ply is not a layered-elastic half-space. Check mesh and boundary sensitivity.")
    st.write("Provide an AnalysisConfig in SI units. E and nu are required for isotropic material; the values below are an editable example, not material recommendations.")
    example = {"a": 1.0, "b": 1.0, "h": 0.1, "m": 4, "n": 4,
               "material_mode": "isotropic", "E": 30000000000.0, "nu": 0.2,
               "choicebc": 1, "load_case": "uniform", "q0": 1000.0}
    with st.form("plate"):
        raw = st.text_area("Analysis configuration (JSON)", json.dumps(example, indent=2), height=340)
        submit = st.form_submit_button("Solve plate")
    if submit:
        try:
            config = AnalysisConfig.model_validate_json(raw)
            with st.spinner("Solving plate…"):
                result = solve_hosnt12(config, include_field=True)
            st.json(result.model_dump(mode="json"), expanded=False)
        except (ValueError, ArithmeticError, RuntimeError) as exc:
            st.error(str(exc))
else:
    st.subheader("IRC:37 layered-elastic response")
    st.info("Horizontally extended isotropic layers over a half-space with perfectly bonded interfaces and circular loads. Results do not establish complete IRC design compliance or IITPAVE equivalence.")
    options = catalogue_options()
    st.write("Available catalogue options:", options)
    st.write("Provide a LayeredElasticRequest in SI units (bituminous modulus is in MPa). Values below are an editable example.")
    example = {"category": "a", "cbr": 5, "traffic_msa": 10,
               "bituminous_E_MPa": 2000, "wheels": "single", "points": []}
    with st.form("layered"):
        raw = st.text_area("Layered-elastic configuration (JSON)", json.dumps(example, indent=2), height=260)
        submit = st.form_submit_button("Solve layered response")
    if submit:
        try:
            request = LayeredElasticRequest.model_validate_json(raw)
            with st.spinner("Solving layered response…"):
                result = adapters.solve_flexible_layered(request)
            st.json(result.model_dump(mode="json"), expanded=False)
        except (ValueError, ArithmeticError, RuntimeError) as exc:
            st.error(str(exc))
