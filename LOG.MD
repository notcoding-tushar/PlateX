# PlateX work log

This log records implementation and verification through 25 November 2026. Test counts reflect the runs performed at each milestone. Update this file after each major change with the work completed, checks performed, and remaining limitations.

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

## 9. Investigated IITPAVE and added a launcher

- Inspected the local IITPAVE Java interface and native executable with REA at the user's request. Documented observed execution, inputs, outputs, tests, engineering interpretation, and unresolved questions in [IITPAVE comparison report.md](IITPAVE%20comparison%20report.md). The report distinguishes observed behavior from inferred layered-elastic methods.
- Reproduced the supplied seven-layer output with a copy of the executable in an isolated working directory. A separate test showed an unexpected change in vertical stress and displacement at one interface. Its cause remains unresolved.
- Added [Run IITPAVE.cmd](Run%20IITPAVE.cmd) to launch the Java interface with the required classpath and use the Git-ignored `external_tools/IITPAVE_work` directory for generated files. The executable and quadrature file are copied there when needed. The launcher supports `--check` for prerequisites.
- **Verification at this milestone:** the launcher prerequisite check succeeded and the input form opened. A complete analysis through the GUI was not tested. The report describes a separate successful native executable run.

## 10. Added IRC:37 layered-elastic analysis and refreshed the UI

- Added [layered_elastic.py](backend/hosnt12/irc/layered_elastic.py), a bonded isotropic layered half-space solver using Fourier modes and Bessel integration with a direct Boussinesq disk field near the surface. It supports one or two circular wheel loads, one-sided interface queries, displacement, stresses, strains, and horizontal principal response. Depth and displacement are positive downwards and tensile stresses and strains are positive.
- Extended the IRC adapter and schemas to obtain catalogue sections, material properties, standard contacts, critical depths, checks, warnings, and citations from the vendored library. The dedicated `POST /api/irc/flexible/layered-elastic` endpoint returns `layered_elastic_irc37`; plate results identify `hosnt12_plate_q8`. The finite-plate path retains its model limitation notice and citations.
- Added a focused IRC Flexible engine selector, catalogue and wheel controls, critical response table, optional query point, stack checks, and source details. The default dual-wheel results sample the wheel centre and pair midpoint. Added surface rotation, pan, reset, and keyboard controls to the plate graph. Refreshed the palette and typography and updated the architecture and frontend instructions.
- **Verification at this milestone:** 72 pytest tests passed, including analytical circular-load, interface continuity, dual-wheel superposition, catalogue, API, and legacy regression tests. All 288 catalogue sections solved for both standard and CTB pressure cases, totaling 576 solves. The IRC library self-test, Ruff, frontend production build, and 44 HOSNT12 CLI self-checks passed. Browser checks covered plot controls, the layered solve, mobile width, and engine switching. Starlette emitted a test-client deprecation warning.
- **Limitations:** sampled response locations do not establish a spatial maximum. Fatigue and rutting life require separate evaluation. The comparison against one recorded IITPAVE case supplements the analytical and continuity tests and does not establish general equivalence.

## 11. Prepared temporary Cloudflare sharing

- Added [scripts/share.mjs](scripts/share.mjs) and frontend README instructions. On Windows the launcher checks the local virtual environment, frontend dependencies, and `external_tools/cloudflare/cloudflared.exe`, builds the frontend, serves the app and API on localhost port 18573, and starts a Cloudflare Quick Tunnel. Ctrl+C stops its child processes. The Cloudflare executable is in the Git-ignored external tools directory.
- The initial executable download stalled, and a later session had a usable executable. A subsequent launch reported port 18573 already in use by an existing sharing session. A separate Quick Tunnel was started against that existing PlateX server. The address supplied by the user returned a DNS error; the replacement address returned HTTP 200 for the page and `status: ok` from the public API when checked. Quick Tunnel URLs are temporary and may change when restarted.
- **Verification:** `node --check scripts/share.mjs` and `git diff --check` passed. The replacement public URL and API were checked at the time of sharing; their current availability has not been checked in this entry.

## Current working tree

- As of 25 November 2026, the current branch is `phase-2-irc37-layered-elastic`. The layered-elastic, UI, documentation, and sharing-launcher changes remain uncommitted.
- The working tree also contains untracked `desktop.ini`, root `node_modules/`, and `pnpm-lock.yaml`. Their origin and intended disposition have not been established. They were left in place.

## 12. Refined the workbench interface

- Applied the Unslop skill by Damir Sokolovsky to the shared Material UI theme and controls. The design uses neutral technical-drawing surfaces, an ochre action accent, a blue deflection scale, quieter navigation, consistent panel and control radii, and clearer spacing and typography.
- Updated shared input, button, toggle, focus, drawer, table, and text-area styling across the Plate Solver, IRC, and validation workflows. Added horizontal scrolling to the critical-response table for small screens. Existing analysis controls and results remain available.
- **Verification:** the frontend TypeScript and production build passed. An isolated headless browser completed a plate solve, IRC layered-elastic analysis, and validation benchmark and checked all three navigation screens for horizontal overflow at 390 px. The desktop plate solver was visually reviewed before and after the change.
- The selected interface font falls back to locally installed system fonts when Instrument Sans is unavailable. No font files were added.

## Streamlit migration (2026-11-25)

- Added root Streamlit entry point with submitted JSON forms for HOSNT12 plate and IRC:37 layered-elastic configurations, and cached catalogue options. Solver and IRC calculation code was not modified.
- Added root requirements and documented startup and current scope in ARCHITECTURE.md. Existing frontend and API remain intact.
- Verification: `.venv\Scripts\python.exe -m pytest -v` passed 72 tests (one Starlette deprecation warning); IRC library self-test passed. Installed Streamlit 1.67.0 in the local virtual environment. Streamlit server started successfully outside the sandbox; Streamlit AppTest successfully submitted the example plate and layered-elastic forms.
- Limitations: JSON forms require knowledge of schemas; dedicated rigid/bridge, sweep, compliance and validation screens remain to be migrated. Full user-facing feature parity and deployment have not been verified.

## Structured Streamlit controls (2026-11-25)

- Replaced JSON-only primary workflows with form tabs for plate geometry, mesh, supports, isotropic or explicit ply properties, pressure, contact patch, foundation and thermal inputs; complete JSON remains available for advanced options. Isotropic E and nu must be entered explicitly.
- Added IRC:37 catalogue, wheel configuration and optional depth-query forms. The adapter still supplies its critical interface points. Displayed result metrics, response and layer tables, model notes and checks; added a nodal deflection contour and sampled vertical stress/strain versus depth plots. Plots use returned values and close their figures. Last successful results persist in session state.
- Verification: `.venv\Scripts\python.exe -m pytest -v` passed all 72 tests (one existing Starlette deprecation warning). Streamlit AppTest passed isotropic and laminate solves, a rectangular patch with thermal loading, layered-elastic solve, graph rendering, missing-material validation, and session persistence. Local Streamlit health endpoint returned `ok`.
- Numerical solver and IRC modules were not changed. Contour values between nodes are interpolated for display. Depth scatter points can represent different horizontal positions or interface sides. Full rigid/bridge, sweep and compliance workflows remain outside the dedicated Streamlit forms; advanced plate JSON retains access to additional plate options.

## Shared React workbench in Streamlit

- Made the existing React workbench the default Streamlit interface, including plate setup, surface/contour interactions, export actions, IRC applications and matrix diagnostics. The sidebar retains the native forms and advanced JSON views.
- Added a Streamlit build target and packaged its static assets. The component queues requests per session and uses the existing validated API routes in process. Frontend source changes require rebuilding the packaged assets.
- Verified the build, a live 341-node plate result, surface/contour switching, the IRC dual-wheel response table and the mechanical Table 2 benchmark in the local Streamlit browser. The numerical modules were untouched.

## Zidi paper validation on the website

Matrix & Validation runs eight independent 10 × 10 TSDT cases and reports all 32 signed comparisons to Tables 2 and 3. The editable tolerance defaults to the 0.1% used for the existing Table 2 deflection self-test. A case passes when all four comparisons pass. The report documents the inferred Table 3 pressure and the zero moisture expansion of the ceramic.

The validation API returned all 32 comparisons. Eight individual comparisons and zero complete cases passed at 0.1%. Mean absolute percentage error was 1.359497%; the largest was 18.478045% for H2 axial stress (computed −0.022337016, published −0.02740). All 72 regression tests passed and the Streamlit frontend build succeeded.

## Refresh deployed workbench assets

The public deployment linked to the migration branch but displayed the old single-case benchmark. Streamlit now serves the component under a name derived from the packaged HTML digest. A changed JS or CSS bundle reference therefore produces a fresh component entry URL on deployment.

## H2 axial stress mesh refinement

The validation tolerance default was subsequently changed to 2% at the user's request in both the frontend and API request model. The default model value was verified and the Streamlit frontend rebuilt successfully.

Matrix & Validation now runs an optional H2 study with the same top-centre sampling point and Table 3 inputs on 10 × 10, 14 × 14 and 20 × 20 meshes. Direct normalized axial stresses were −0.022337016, −0.024775616 and −0.026061202. The stress differences from the published −0.02740 decreased from 18.478% to 9.578% to 4.886%. The observed order of 2.02 gives a Richardson estimate of −0.027277305 (0.448% difference). The paper value is used only for comparison. The original suite still scores its 32 direct 10 × 10 results.

The thermal strain term nearly cancels the total-strain contribution to the top-face stress. At 10 × 10 the normalized centre deflection was 0.97211727 versus 0.97216 in Table 3. All 72 regression tests and 44 CLI self-checks passed, as did the IRC self-test, Ruff and the Streamlit frontend build. The Table 3 pressure remains a replication assumption.

## 2026-11-27 — Pavement layer workbench

- Promoted single-layer, custom bonded stack and benchmark laminate configurations to the main pavement setup. The layer count selector splits the top material or extends the highest retained material. Editing individual thicknesses rebuilds contiguous interfaces about the mid-plane. Changing stack geometry clears imported evaluation points tied to the previous section.
- Named all six finite-section boundary conditions by edge support while retaining the existing solver IDs. Updated navigation, Streamlit titles and project documentation to describe pavement analysis.
- Replaced the comma-separated Class AA input with four signed transverse centre fields in millimetres. The bridge preview waits for four entries and uses the existing IRC geometry validation.
- Verified both production builds and the bundled Streamlit entry point. Headless Edge completed a three-layer finite-section solve after a thickness edit and an AA preview with eight contact patches. All 72 pytest tests, 44 CLI self-tests, IRC library self-tests and backend Ruff checks passed. The 10 × 10 paper comparison completed and retained the known 18.478% axial-stress discrepancy in the hygrothermal foundation case.
- Custom finite pavement stacks use the HOSNT12 model. The separate IRC:37 semi-infinite layered-elastic workflow uses catalogue sections.


## 2026-11-27 — Custom IRC:37 layers and accuracy benchmark

- Added a custom layered-elastic stack with editable count, thickness, modulus and Poisson ratio, ending in a half-space. Default values describe a runnable three-layer section.
- Added an IITPAVE comparison report using the existing recorded three-layer benchmark and current calculated results. The five differences range from 0.105% to 0.156%.
- Catalogue-based analyses remain available. Custom sections use interface response sampling and do not receive IRC catalogue compliance checks. The benchmark covers one case and the previously documented seven-layer IITPAVE discrepancy remains unresolved.

## 2026-11-27 — Layer response graphs and clearer trial inputs

- Added graphs for vertical and horizontal strain, vertical stress and displacement at the actual layered-elastic interface sampling locations, distinguishing wheel centre and pair midpoint.
- Expanded all IRC:37 category choices with their top-down layer arrangements. Separated catalogue trial inputs from the custom layer configuration and wheel loading controls, preserving their independent values.
- Simplified the thermal inputs to mean temperature change and top-to-bottom difference, with the full thermal and moisture profiles available under Advanced.
- Streamlit frontend build passed. The graphs display sampled interface responses rather than a continuous depth profile; the final half-space has no finite bottom interface.


## 2026-11-27 — Workbench structure and validation reliability

- Extracted pavement analysis state and request lifecycle into a dedicated React hook, extracted the shared request transport, and split validation endpoints into their own router while retaining public paths.
- Added environment settings for the API proxy and CORS origins, and documented the feature, transport, state and backend boundaries.
- The Streamlit bridge now uses browser-independent request identifiers, reports unexpected server errors, and times out stalled requests. Matrix diagnostics identify when they belong to an earlier solve.
- Standalone and Streamlit builds passed. All 72 pytest cases, 44 CLI self-checks, the IRC self-test, backend Ruff, and the CLI paper comparison completed. The validation suite endpoint returned all 32 comparisons with H2 outside tolerance. The Windows sandbox blocked the local socket used by the standalone API probe, so it was verified outside the sandbox. Benchmark comparisons retain the documented Table 3 load convention and numerical discrepancy.

## 2026-11-27 — Streamlit validation route refresh

- Reproduced "Not Found" when running the validation suite on the existing Streamlit server. Its long-running Python process held the older API route table and schemas.
- Restarted the local Streamlit server to load the current modules. In the browser, matrix diagnostics appeared and the eight-case suite returned all 32 comparisons. Seven cases passed at 2% tolerance and H2 retained its known 18.478% axial-stress difference.

## 2026-11-27 — Workbench visual refinement

- Applied a quieter pavement-analysis interface with compact rectangular controls, reduced card decoration, consistent numerical typography, and a wider edge-to-edge deflection plot. Retained the existing copper accent and analysis controls.
- Removed the redundant solver subtitle and rebuilt the shared Streamlit bundle. Verified the live Streamlit solver view and Matrix & Validation navigation. The Streamlit production build passed.

## 2026-11-27 — Workbench interaction polish

- Improved toggle and button target sizes, focus indicators, numeric alignment and mobile input sizing. Kept the plot responsive and exposed initial loading and analysis errors to assistive technology.
- Rebuilt the Streamlit bundle and visually checked the live desktop solver after the update. The production frontend build passed.
- Mobile rendering, keyboard interaction and frame-by-frame motion were not independently verified in this pass.

## 2026-11-27 — Pavement workbench landing page

- Added an Overview landing page introducing finite pavement sections, IRC loading and layered-elastic analysis, validation, and the project's numerical work. The hero displays the current computed deflection field.
- Added direct navigation to the solver, IRC workflows and validation. Built the Streamlit component and verified the landing page and solver navigation in the local Streamlit app.
- The public Streamlit app remains on the previous deployed build pending approval to reboot its existing sessions.
