"""Launch the shared PlateX workbench inside Streamlit."""
import asyncio
import sys
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
from api.main import app as analysis_api  # noqa: E402

st.set_page_config(page_title="PlateX · Analysis workbench", layout="wide", initial_sidebar_state="collapsed")
view = st.sidebar.radio("Interface", ["Analysis workbench", "Structured forms"])
if view == "Structured forms":
    from streamlit_forms import render_forms
    render_forms()
    st.stop()

st.markdown("""
<style>
.stMainBlockContainer {max-width: 1520px; padding: 3.5rem 0 0;}
</style>
""", unsafe_allow_html=True)
workbench = components.declare_component("platex_workbench", path=str(ROOT / "streamlit_workbench"))

# Only the same local routes exposed by the React client may be requested.
GET = {"irc/options", "irc/climate-options", "irc/flexible/catalogue-options",
       "validation?hygrothermal=true", "validation?hygrothermal=false"}
POST = {"solve", "solve-sweep", "irc/preview-loads", "irc/check", "irc/rigid",
        "irc/flexible", "irc/climate-temperature", "irc/compliance", "irc/flexible/layered-elastic"}


async def dispatch(message):
    path = message["path"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=analysis_api),
                                 base_url="http://platex.local") as client:
        if path in GET:
            response = await client.get("/api/" + path)
        elif path in POST:
            response = await client.post("/api/" + path, json=message["body"])
        else:
            raise ValueError("Unknown workbench action.")
    payload = response.json()
    if response.is_error:
        detail = payload.get("detail", response.reason_phrase)
        if isinstance(detail, list):
            detail = "; ".join(f"{'.'.join(map(str, item['loc'][1:]))}: {item['msg']}" for item in detail)
        raise ValueError(detail)
    return payload


reply = st.session_state.get("workbench_reply", {})
message = workbench(reply=reply, key="workbench")
if message and message["id"] != reply.get("id"):
    try:
        reply = {"id": message["id"], "result": asyncio.run(dispatch(message))}
    except (ValueError, RuntimeError, ArithmeticError, KeyError) as exc:
        reply = {"id": message["id"], "error": str(exc)}
    st.session_state.workbench_reply = reply
    st.rerun()
