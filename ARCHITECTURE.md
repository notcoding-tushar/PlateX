# HOSNT12 FEA Platform — Intermediate Architecture Blueprint

## 1. Architectural Strategy
This repository uses a **pragmatic, intermediate monorepo** designed for:
1. **Clean Phase 1 refactoring** of the validated monolith (`Higher Validated 5-11-26.py`) into testable, flat Python modules without enterprise boilerplate.
2. **Seamless IRC integration** via the vendored, zero-dependency `irc_fea_library.py` (IRC:58, IRC:37, IRC:SP:49, IRC:15, IRC:19, IRC:6) behind a thin adapter layer.
3. **Web deployment** with a thin FastAPI backend and a React + TypeScript + Google Material UI (`@mui/material`) frontend.

---

## 2. Repository Directory Structure

```text
hosnt12-fea-web/
├── ARCHITECTURE.md                 # System design & module boundaries
├── AGENTS.md                       # Codex build rules, invariants & phase gates
├── CODEX_PHASE1_PROMPT.md          # Ready-to-use kickoff prompt for Phase 1
├── .gitignore
├── archive/                        # Untouched reference originals (read-only)
│   ├── Higher Validated 5-11-26.py
│   └── IRC_FEA_LIBRARY_GUIDE.md
│
├── backend/
│   ├── pyproject.toml              # Python 3.10+ dependencies & pytest/ruff config
│   ├── hosnt12/                    # Core FEA engine (zero web/UI dependencies)
│   │   ├── __init__.py             # Public facade exports
│   │   ├── constants.py            # DOF indices, BC map, laminate presets
│   │   ├── schemas.py              # Pydantic models: inputs, patches, queries, results
│   │   ├── mesh.py                 # Structured Q8 mesh generator
│   │   ├── materials.py            # Isotropic & orthotropic constitutive matrices, Db/Ds, D11
│   │   ├── elements.py             # Q8 shape functions, derivatives, Jacobian, Bb/Bs
│   │   ├── loads.py                # Pressure, thermal/moisture, nodal, rect & circle patches
│   │   ├── boundary.py             # 6 BCs + TSDT kinematics (T3, WS, T3S = 0)
│   │   ├── solver.py               # Sparse assembly, reusable splu factorization, single & sweep solve
│   │   ├── postprocess.py          # Point/interface stress recovery, superconvergent shear, normalization
│   │   ├── validation.py           # Zidi et al. (2014) Tables 2 & 3, convergence study, selftest
│   │   ├── io_utils.py             # CSV export & Matplotlib plotting (optional CLI use)
│   │   ├── cli.py                  # Terminal entrypoint (--validate, --convergence, --selftest)
│   │   └── irc/                    # IRC domain boundary (Phase 4)
│   │       ├── __init__.py
│   │       ├── irc_fea_library.py  # Vendored UNTOUCHED from project library
│   │       └── adapters.py         # Translates IRC Material/Layer/Patch/k -> hosnt12 schemas
│   │
│   ├── api/                        # Thin FastAPI layer (Phase 2)
│   │   ├── __init__.py
│   │   ├── main.py                 # App factory, CORS, health check
│   │   ├── routes_solve.py         # POST /api/solve, POST /api/solve-sweep
│   │   └── routes_irc.py           # GET /api/irc/options, POST /api/irc/preview-loads, POST /api/irc/check
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_baseline_regression.py   # Bit-for-bit parity vs Higher Validated 5-11-26.py
│       ├── test_mesh_elements.py         # Q8 shape sum=1, Jacobian, patch force conservation
│       ├── test_materials.py             # Isotropic/laminate equivalence, D11, inert 3D params
│       ├── test_solver_sweeps.py         # splu reuse parity with spsolve, moving-load sweeps
│       └── test_irc_adapters.py          # Phase 4 IRC adapter & guardrail tests
│
└── frontend/                       # React + TypeScript + Google Material UI (Phase 3)
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── theme.ts                # MUI theme configuration
        ├── api/client.ts           # Typed FastAPI client
        ├── components/             # Input forms, 2D tyre/slab preview, 3D/contour plots, IRC compliance drawer
        └── pages/                  # Plate Workbench, IRC Pavement/Bridge Modes, Validation Dashboard
```

---

## 3. Core Design Adjustments for `irc_fea_library.py`

1. **Vendored IRC Library (`irc_fea_library.py`)**: Kept completely unmodified inside `backend/hosnt12/irc/` so its built-in `--self-test` and 117 source citations remain intact. `adapters.py` handles all unit/schema translation.
2. **Unified Contact Patches (Rectangle + Circle)**: `loads.py` supports both rectangular patches (IRC:6 bridge wheels/tracks) and circular patches (IRC:37 dual wheels, IRC:58 rigid axle groups). Clipped patches overhanging plate edges integrate strictly over the overlap without rescaling total force.
3. **Configurable In-Plane Thermal Distribution**: `schemas.py` and `loads.py` support `thermal_distribution: Literal["sinusoidal", "uniform"]`. `"sinusoidal"` preserves the Zidi et al. (2014) benchmark; `"uniform"` supports IRC:58 slab curling differentials (`delta_T`).
4. **Reusable Sparse LU Factorization (`splu`)**: `solver.py` separates stiffness assembly + `scipy.sparse.linalg.splu(K_free.tocsc())` from RHS load-vector assembly. Moving bridge trains (IRC:6) and multi-position axle checks (IRC:58) factorize `K_free` once and back-substitute for every load position.
5. **General Point & One-Sided Interface Post-Processing**: `postprocess.py` extracts `evaluate_point(x, y, z, layer_side)` out of the solver closure so callers can query arbitrary coordinates (e.g., IRC:58 bottom/top tension under tyres or IRC:37 interface queries `just_above_interface` / `just_below_interface`).
6. **Civil Engineering Guardrails in `adapters.py`**:
   - **No DLC Double-Counting**: Rigid pavement mode enforces a mutually exclusive choice between a single PQC slab on lumped `effective_k15(..., "DLC")` vs. explicit multi-layer modeling on raw subgrade `rigid_cbr_to_k()`.
   - **IRC:37 Kinematics Disclosure**: Running an IRC:37 stack through HOSNT12 (`eps_z = 0`, finite plate) automatically attaches a `modeling_notes` warning clarifying that it does not replace Burmister semi-infinite layered-elastic subgrade strain checks.

---

## IRC:37 layered-elastic response

The IRC:37 workspace also has a dedicated response engine in
`backend/hosnt12/irc/layered_elastic.py`. It accepts SI isotropic layers, a final
half-space, circular contacts and depth queries. It matches displacements and
tractions at perfectly bonded interfaces using decaying Fourier modes, then
integrates the circular loading spectrum with Bessel kernels. Near the surface
it integrates the direct Boussinesq disk field separately to resolve the
contact traction discontinuity. Single-wheel tensors are rotated into a common
frame before addition. The classical bonded-layer transform formulation is
described in [Layered Systems Under Normal Surface Loads](https://onlinepubs.trb.org/onlinepubs/hrr/1968/228/228-004.pdf).

The adapter resolves catalogue inputs, checks, critical query depths and
provenance. FastAPI exposes this workflow through
`POST /api/irc/flexible/layered-elastic`. The result declares
`layered_elastic_irc37`. Finite-plate solves declare `hosnt12_plate_q8`.

## 4. Phased Delivery Roadmap

| Phase | Scope | Exit Gate |
|---|---|---|
| **Phase 1 (Current)** | Refactor `Higher Validated 5-11-26.py` into `backend/hosnt12/` + `splu` solver + circular patches + `postprocess.py` + `pytest` suite | 100% parity with legacy `--selftest` and Zidi et al. (2014) Table 2 & 3 (`< 1e-12` diff) |
| **Phase 2** | Build FastAPI layer (`backend/api/`) with `/api/solve`, `/api/solve-sweep`, OpenAPI schema | `pytest` API integration tests green; OpenAPI JSON clean |
| **Phase 3** | Build React + TypeScript + MUI frontend (`frontend/`) with interactive workbench, 2D load preview, deflection plots | End-to-end solve in browser matches CLI results |
| **Phase 4** | Wire `irc_fea_library.py` via `adapters.py` + `/api/irc/*` endpoints + MUI IRC Pavement/Bridge & Compliance Drawer | `irc_fea_library.py --self-test` + `test_irc_adapters.py` green |
