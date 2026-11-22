# Phase 1 Kickoff Prompt for Codex

Copy and paste the prompt below directly into Codex once you have placed `Higher Validated 5-11-26.py` into `archive/` and `irc_fea_library.py` into `backend/hosnt12/irc/`.

---

```text
Read ARCHITECTURE.md and AGENTS.md carefully before editing any files.

Execute Phase 1 (Core FEA Refactoring) of the HOSNT12 project:
1. Refactor `archive/Higher Validated 5-11-26.py` into the modular `backend/hosnt12/` package using the exact module map in AGENTS.md and the pre-defined models in `backend/hosnt12/constants.py` and `backend/hosnt12/schemas.py`.
2. Preserve EVERY physics and FEA invariant listed in AGENTS.md Section 2 (Q8 clockwise ordering, 3x3/2x2 selective reduced integration, TSDT constraints T3=WS=T3S=0, superconvergent 2x2 shear recovery, D11 laminate normalization, and exact Zidi et al. 2014 benchmarks).
3. Implement these Phase 1 upgrades cleanly:
   - `hosnt12/loads.py`: Support both rectangular and circular `ContactPatch` overlap integration (no rescaling when clipped by plate edges) and `thermal_distribution` ("sinusoidal" default for benchmarks, "uniform" for IRC:58 curling).
   - `hosnt12/solver.py`: Decouple global stiffness assembly and `scipy.sparse.linalg.splu(K_free.tocsc())` factorization from RHS load-vector assembly, and expose both `solve_hosnt12(config: AnalysisConfig) -> AnalysisResult` and `solve_sweep(base_config, load_cases) -> list[AnalysisResult]`.
   - `hosnt12/postprocess.py`: Extract point evaluation out of the solver closure so it supports arbitrary `QueryPoint(x_m, y_m, z_m, layer_side)` queries alongside the default benchmark points.
   - Keep a backwards-compatible wrapper function `solve_hosnt12_legacy(**kwargs) -> dict` in `hosnt12/solver.py` so existing scripts and regression tests can compare outputs directly against `archive/Higher Validated 5-11-26.py`.
4. Do NOT touch `backend/hosnt12/irc/irc_fea_library.py`, and do NOT start Phase 2 (FastAPI) or Phase 3 (Frontend) yet.
5. Complete the pytest suite in `backend/tests/` (`test_baseline_regression.py`, `test_mesh_elements.py`, `test_materials.py`, `test_solver_sweeps.py`) and run:
   - `pytest -v`
   - `python -m hosnt12.cli --selftest`
   - `python -m hosnt12.cli --validate 10`
   - `ruff check backend/`
Report the test results and confirm <= 1e-12 relative parity with the legacy monolith.
```
