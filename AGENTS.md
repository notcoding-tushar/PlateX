# AGENTS.md — Codex Engineering Rules for HOSNT12 FEA

You are acting as a Senior Scientific Software Engineer and Civil/Structural FEA Specialist refactoring and extending the HOSNT12 plate finite-element solver.

---

## 1. Golden Rules (Read Before Writing Any Code)

1. **Intermediate Simplicity**: Keep modules flat, readable, and Pythonic. Do NOT introduce abstract factory hierarchies, dependency injection containers, ORMs, or premature microservices.
2. **Strict Layer Boundaries**:
   - `backend/hosnt12/` MUST NOT import `fastapi`, `uvicorn`, `streamlit`, or any web framework.
   - `backend/hosnt12/irc/irc_fea_library.py` is **READ-ONLY / VENDORED**. Never edit it. All translation logic belongs in `backend/hosnt12/irc/adapters.py`.
   - `backend/api/` contains ONLY HTTP routing, request/response wiring, and error mapping—zero FEA math.
3. **Type Safety & SI Units**:
   - All internal `hosnt12` physics operate strictly in **SI units**: `m`, `N`, `Pa`, `N/m^3`, `N/m`, `K`, `rad`.
   - All public inputs and outputs use the Pydantic models in `hosnt12/schemas.py`.
4. **No Silent Material Defaults**: Preserve the legacy rule—isotropic mode MUST reject missing `E` or `nu`. Never invent default material properties.

---

## 2. Non-Negotiable Physics & FEA Invariants

Do NOT alter these mathematical behaviors during refactoring:

1. **12-DOF Ordering**: `[U, V, W, T1, T2, T3, US, VS, WS, T1S, T2S, T3S]` (`range(12)`).
2. **Q8 Clockwise Node Ordering**:
   - Node 1: top-left `(i, j+2)` -> Node 2: top-mid `(i+1, j+2)` -> Node 3: top-right `(i+2, j+2)` -> Node 4: right-mid `(i+2, j+1)` -> Node 5: bottom-right `(i+2, j)` -> Node 6: bottom-mid `(i+1, j)` -> Node 7: bottom-left `(i, j)` -> Node 8: left-mid `(i, j+1)`.
3. **Selective Reduced Integration**:
   - Bending/normal stiffness (`Bb.T @ Db @ Bb`), foundation (`Kf`), and mechanical/environmental loads: **3x3 Gauss-Legendre**.
   - Transverse shear stiffness (`Bs.T @ Ds @ Bs`): **2x2 reduced Gauss-Legendre** (prevents shear locking).
4. **Plane-Stress TSDT Kinematics**:
   - `sigma_z = 0` constitutive law.
   - Thickness-stretching DOFs `(T3, WS, T3S)` are constrained to zero at **every** node in `boundary.py`.
   - `E3, nu23, nu13, alpha3, beta3` remain accepted on `LayerProperty` but are mathematically inert.
5. **Superconvergent Transverse Shear Recovery**:
   - `postprocess.py` MUST recover transverse shear strains by bilinear extrapolation from the 2x2 Gauss points (`xi, eta = +/- 1/sqrt(3)`), then multiply by `Cs`.
6. **Normalization Rigidity `D`**:
   - Isotropic: `D = E * h**3 / (12 * (1 - nu**2))`
   - Laminate: `D = D11 = sum_k Q11_bar_k * (z_top**3 - z_bot**3) / 3` (full stack, NOT first-ply).
7. **Patch Load Conservation**:
   - Rectangular patches integrate over the exact `[lx0, lx1] x [ly0, ly1]` element overlap (3x3 Gauss).
   - Circular patches integrate over the element-circle intersection (mapped quadrature or fine sub-cell Gauss over the overlap) so total applied force equals `F` when fully inside the plate, and **never rescales** when clipped by a plate edge.

---

## 3. Phase 1 Refactoring Map (`Higher Validated 5-11-26.py` -> `backend/hosnt12/`)

| Source Section in `Higher Validated 5-11-26.py` | Target Module | Notes |
|---|---|---|
| `DOF`, `U..T3S`, `BOUNDARY_CONDITIONS`, `PRESET_LAMINATE_PROPERTIES` | `hosnt12/constants.py` | Already scaffolded in starter kit |
| `LayerProperty`, `VehicleLoad`, solver args & return dict | `hosnt12/schemas.py` | Already scaffolded as Pydantic v2 models |
| `build_mesh` | `hosnt12/mesh.py` | Return a clean `MeshData` dataclass/NamedTuple |
| `_expansion_vector`, `orthotropic_layer_matrices`, `default_three_layer_laminate`, `validate_layer`, `layer_at_z`, `material_at_z`, `environmental_profile`, `compute_stiffness_and_environment_resultants`, `reference_flexural_rigidity` | `hosnt12/materials.py` | Add `side: Literal["auto", "above", "below"]` support to `layer_at_z` |
| `shape_q8`, `shape_q8_second`, `element_geometry`, `b_matrices` | `hosnt12/elements.py` | Pure NumPy element math |
| `patch_load_vector` + pressure/nonlocal/environmental RHS assembly | `hosnt12/loads.py` | Support both `rectangle` and `circle` `ContactPatch`, plus `thermal_distribution` (`sinusoidal` vs `uniform`) |
| `constrained_dofs` | `hosnt12/boundary.py` | Keep all 6 BCs + global `(T3, WS, T3S)` constraint |
| `solve_hosnt12` assembly & linear solve | `hosnt12/solver.py` | Split into `assemble_system()`, `factorize_system()` (`splu`), `solve_hosnt12()`, and `solve_sweep()` |
| `find_elements_at`, `natural_coordinates`, `element_strains`, `recovered_shear_strain`, `evaluate_point`, normalization | `hosnt12/postprocess.py` | Extract out of solver closure; support custom `QueryPoint` lists |
| `PAPER_*`, `solve_paper_case`, `run_paper_validation`, `run_convergence_study`, `run_self_tests` | `hosnt12/validation.py` | Keep exact benchmark constants |
| `plot_deflection`, `export_results_csv` | `hosnt12/io_utils.py` | Lazy-import `matplotlib` inside plotting function |
| `collect_terminal_inputs`, `print_results`, `main` | `hosnt12/cli.py` | Wire `--selftest`, `--validate`, `--convergence`, and interactive mode |

---

## 4. Phase 1 Definition of Done (Verification Commands)

Phase 1 is ONLY complete when ALL of the following pass with zero errors:

```bash
# 1. Run pytest suite (including baseline parity against Higher Validated 5-11-26.py)
pytest -v

# 2. Run migrated CLI regression & paper validation checks
python -m hosnt12.cli --selftest
python -m hosnt12.cli --validate 10

# 3. Verify vendored IRC library self-test still passes untouched
python backend/hosnt12/irc/irc_fea_library.py --self-test

# 4. Lint check
ruff check backend/
```

**Numerical Parity Tolerance**: Every normalized and dimensional benchmark value from `Higher Validated 5-11-26.py` MUST match within `1e-12` relative error.
