# PlateX work log

This log records implementation and verification through 24 November 2026. Test counts reflect the runs performed at each milestone.

## 1. Refactored and verified the HOSNT12 solver

- Read [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md), then split the archived solver into mesh, element, material, load, boundary, solver, postprocessing, validation, I/O, and CLI modules under [backend/hosnt12](backend/hosnt12).
- Preserved the 12-DOF ordering, clockwise Q8 connectivity, 3×3 bending and load integration, 2×2 transverse shear integration, and the global plane-stress constraints on thickness stretching. Stress recovery still extrapolates transverse shear from the 2×2 Gauss points. Laminate normalization uses the full-stack D11. Isotropic inputs require explicit E and ν.
- Added circular contact patches alongside rectangular patches. The solver integrates the portion of each footprint on the plate at its original pressure. Added uniform thermal and moisture loading alongside the sinusoidal benchmark distribution.
- Separated stiffness assembly, sparse LU factorization, and load assembly. A moving-load sweep reuses one factorization. Factoring the reduced matrix transpose and using a transposed backsolve reproduces the archived CSR solve's pivot order within the required tolerance.
- Moved point recovery out of the solver closure. Added arbitrary query points and one-sided interface stress recovery while retaining the default benchmark points. Added `solve_hosnt12_legacy` for the archived keyword and dictionary interface.
- Migrated the CLI self-checks, Zidi et al. benchmark comparisons, convergence study, interactive prompts, plot generation, and CSV export. Added regression coverage for legacy parity, mesh and integration behavior, materials, and sweeps.
- **Verification:** `pytest -v` passed 38 tests, the CLI self-test passed 44 of 44 checks, the 10×10 validation ran to completion, Ruff passed, and the vendored IRC library passed its own self-test. The archived solver and the refactor matched exactly for 104 checked dimensional and normalized values across eight 10×10 benchmark cases. The archive's Table 3 comparison uses an assumed pressure of 100 kPa. Its largest difference from the published Table 3 values was 18.478% for normalized axial stress at K₀ = 100 and J₀ = 0.

## 2. Built the FastAPI and React workbench

- Added a FastAPI app factory, local CORS, and error mapping in [backend/api](backend/api). The API delegates solver work to HOSNT12. The optional nodal field response gives the frontend coordinates, connectivity, and displacements from the same solve used for the numeric results.
- Added an [IRC adapter](backend/hosnt12/irc/adapters.py) for SI conversion, contact placement, checks, and exact clause, printed-page, and PDF-page citations. The archived solver and vendored IRC library were kept intact.
- Built the React, TypeScript, Vite, and Material UI frontend in [frontend](frontend). Plate Solver supports single analyses and moving-load sweeps, progressive disclosure for model inputs, dimensional and normalized outputs, surface and contour views, SVG export, and CSV downloads. IRC Pavement & Bridge offers nine load cases, a footprint preview and transfer to the solver, and a checks drawer. Matrix & Validation shows stiffness diagnostics and runs comparisons with the zero-foundation rows of Zidi Tables 2 and 3.
- Moving-load sweeps translate every contact along the plate's x axis. IRC transfer retains the current material and supports and sets distributed pressure to zero. Bridge previews use static, unfactored footprints.

| Method and path | Purpose |
|---|---|
| `POST /api/solve` | Run a single plate analysis |
| `POST /api/solve-sweep` | Run multiple load positions |
| `GET /api/irc/options` | List supported IRC load cases |
| `POST /api/irc/preview-loads` | Generate placed contact patches and provenance |
| `POST /api/irc/check` | Return check results and citations |
| `GET /api/validation` | Compare computed and published benchmark values |
| `GET /api/health` | Check API readiness |
| `GET /docs` | Open the interactive OpenAPI documentation |

- **Verification:** `pytest -v` passed 52 tests, including 14 API integration tests and the existing solver regressions. Ruff, TypeScript, and the Vite production build passed. Starlette emitted one deprecation warning for its `httpx` test client. In the browser, a live 10×10 solve returned 341 nodes and a centre deflection of approximately 7.830 × 10⁻⁸ m. The IRC drawer displayed the vendor's clause and page references.

## 3. Added one-command startup

- Added the root [package.json](package.json) and [launcher](scripts/start.mjs). After one-time dependency installation, `npm start` starts FastAPI on port 8000, waits for its health endpoint, and starts Vite. Ctrl+C stops both processes.
- Documented Windows, macOS, and Linux setup in the [frontend README](frontend/README.md). Vite usually serves the app at `http://127.0.0.1:5173` and proxies `/api` to FastAPI.
- **Verification:** Started the project with `npm start`, loaded the workbench, and completed a 2×2 solve through the Vite proxy. Confirmed both ports closed after shutdown.

## 4. Installed and applied the Unslop skill

- Installed the [Unslop skill](https://github.com/heydamir/unslop/tree/main/skills/unslop) in the local Codex skills directory from the requested GitHub path. Unslop is by Damir Sokolovsky and is licensed under CC BY 4.0.
- Audited the three tabs and the IRC checks drawer in the browser. Applied the approved structural drawing direction by simplifying navigation and headings, tightening spacing, and bringing the solved field and key metrics into the first desktop view.
- Clarified plot orientation, added dimension lines to the IRC preview, and split clause and page details into readable lines in the drawer. Gave the benchmark comparison more room, aligned figures, and distinguished computed results from published values.
- **Verification:** The production build passed. Checked the live solver, contour toggle, IRC citations, and a published benchmark in the browser.

## 5. Restyled the workbench with the requested palette

- Blended neumorphism and minimalism using softly raised panels, recessed controls, restrained borders, and rounded corners. Applied the shared theme across Plate Solver, IRC Pavement & Bridge, Matrix & Validation, and the checks drawer.
- Used `#66545e` for plum text and actions, `#a39193` for taupe borders and grids, `#aa6f73` for rose status accents, `#eea990` for peach footprints, and `#f6e0b5` for cream selected controls. The deflection plot and its legend share one colour scale drawn from the palette.
- **Verification:** TypeScript and the Vite production build passed. Reviewed all three tabs in the browser and opened the IRC checks drawer.

## 6. Extended IRC integration

- Read the architecture, project engineering rules, and [IRC library guide](archive/IRC_FEA_LIBRARY_GUIDE.md) before extending the integration. The vendored [IRC library](backend/hosnt12/irc/irc_fea_library.py) was not edited; IRC lookups and their source references remain in that file, while translations to solver inputs are in [adapters.py](backend/hosnt12/irc/adapters.py).
- Added rigid-pavement preparation using the library's CBR-to-k and effective-k lookups, PQC properties, and temperature differentials. Effective foundation support is rejected when explicit supporting layers would double-count the subbase; uncapped raw effective-k values are exposed for audit, not used as analysis stiffness. Invalid, missing, dashed, or out-of-range lookup cells remain library errors.
- Added IRC:37 flexible catalogue preparation with a project-selected bituminous modulus, finite subgrade thickness, wheel contacts, and one-sided critical interface queries. The prepared model warns that HOSNT12 is a finite plate with `eps_z = 0` and does not replace semi-infinite layered-elastic subgrade strain checks.
- Extended bridge load cases to include Class AA tracked and wheeled and SV trailer contacts alongside Class A, Class B, and 70R. AA wheeled contacts require four explicit verified transverse offsets; full SV contacts require caller-supplied prime-mover geometry. Placement and sweep cases retain the original contact pressure when a footprint overhangs the plate.
- Added adapter-backed foundation audit, pavement preparation, compliance, bridge guidance, IRC solve, and IRC sweep routes. Compliance results retain the library's source citations. The UI separates rigid, flexible, and bridge cases, previews footprints, and provides a compliance and provenance drawer. Some advanced functions, including SV prime-mover contacts, bridge guidance, and IRC sweep preparation, remain API-only; additional compliance checks in the drawer accept JSON arguments.
- **Verification at this milestone:** 57 pytest tests passed, including IRC adapter and API tests; the vendored library self-test, Ruff, and frontend production build passed. The FastAPI test client hung in the sandbox, so the full suite was run outside it with approval. Starlette reported one test-client deprecation warning.

## 7. Installed REA and cleaned the branch

- Installed REA 6.10.1 for Codex after reviewing its setup plan. Configured the investigation skill for explicit invocation and added a user-level Codex instruction to use REA only when the user requests it for the current task. The REA MCP server process may still start when Codex loads connections; a live connection requires restarting Codex.
- The initial npm cache was mistakenly committed under `.rea-npm-cache`. Moved the local package and cache to `external_tools/rea-npm-cache`, updated the Codex MCP path, and verified that REA's diagnostic reported the registration and skill aligned. The skill and Codex configuration remain in the user profile. Native analysis providers such as Ghidra and IDA were not configured.
- The `external_tools/` directory and legacy `.rea-npm-cache/` path are ignored by [.gitignore](.gitignore). Commit `2ac56f3` on `phase-2-irc-web` removed 6,372 cache files from the tracked tree while keeping the local installation. The earlier commit `0020c8d` still contains the cache in Git history; history was not rewritten.

## 8. Improved pavement, traffic, foundation, thermal, and climate controls

- Reviewed the existing solver and web workflows. Added editable pavement-layer controls and validated that explicit layers cover the plate thickness continuously without gaps or overlaps. The workbench exposes the existing vehicle contact patches and moving-load sweeps as traffic loading.
- Fixed the prepared-model handoff for nullable thermal coefficients and corrected foundation mode selection when dimensional foundation values are returned alongside null dimensionless fields. Exposed the independent dimensional `Kp_y` input and explained the thermal profile coefficients.
- Added IRC:58 climate-zone options directly from the vendored provision's state and regional descriptions. Users choose the zone for the actual site, day or night, and whether to allow bounded interpolation; a state name is not automatically assigned a zone. The API returns the top-to-bottom differential and source citation. The table is a fallback maximum, not a weather time series, and the daytime linear through-depth profile used by the solver is an approximation to a nonlinear profile. Permanent curl is not included.
- Rejected applying an IRC slab-only temperature differential across an explicit multilayer stack. Flexible catalogue preparation rejects existing nonzero thermal or moisture loading because the catalogue does not supply the required layer expansion properties. Documented the workflows and their limits in the [frontend README](frontend/README.md).
- **Latest verification:** 59 pytest tests passed; the CLI self-test passed 44 of 44 checks; `python -m hosnt12.cli --validate 10` completed; the vendored IRC self-test, Ruff, frontend type-check and production build, and `git diff --check` passed. The 10×10 paper report still shows a maximum 18.478% discrepancy in the cited Table 3 normalized axial-stress case; completion of the validation command does not mean exact agreement with the published table. The API tests were run outside the sandbox with approval because its FastAPI test client hung inside it. Starlette emitted its existing test-client deprecation warning.
- **Working-tree status at this entry:** the pavement and climate changes and this log update are uncommitted on `phase-2-irc-web`. The IRC library remains unchanged.
