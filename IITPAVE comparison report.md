# IITPAVE and PlateX: software and pavement-engineering comparison

**Assessment date:** 24 November 2026  
**Investigated installation:** `external_tools/IRC_37_IITPAVE/`  
**PlateX baseline:** current `phase-2-irc-web` working tree, including uncommitted pavement and climate changes.

## Executive findings

IITPAVE and PlateX both calculate pavement responses from material properties and wheel loads, but they solve **different boundary-value problems**. IITPAVE's packaged examples and controlled runs support its role as a layered elastic wheel-load response tool. PlateX is a finite Q8 higher-order plate model with plane-stress constitutive behavior and constrained transverse normal deformation. In particular, PlateX's present point-result contract does **not** return vertical subgrade strain. A label saying “vertical compressive strain” on an IRC query does not make it an IITPAVE-equivalent calculation.

For an IRC:37 flexible-pavement workflow, a verified layered-elastic implementation is generally the more relevant model for subgrade vertical strain and the critical responses assumed by the IRC procedure. For an idealized finite rigid slab, PlateX's explicit finite boundaries, foundation, and thermal loading are more relevant to slab mechanics. **Neither conclusion proves that either program is numerically accurate for a specific project.** Calibration, independently verified benchmarks, and appropriate model assumptions are required.

An important finding needs follow-up: the supplied seven-layer IITPAVE case reproduced exactly, but its reported vertical stress and displacement show a substantial jump across a tested material interface. This is inconsistent with a perfectly bonded interface under the usual no-interface-load assumptions, if the output columns represent the same physical components and point. It is a reproducible observation, not a diagnosis of the cause or evidence that every IITPAVE result is wrong. See §2.5.

## Scope, evidence and confidence

The investigation used REA 6.10.1 for non-executing JAR inventory and PE import/resource inspection, Java class-file inspection, the supplied input/output and quadrature files, and controlled runs of a **copy** of the 32-bit solver in isolated temporary directories. It did not modify the original executables, the vendored IRC library, or the archived reference solver. No GUI run was observed. Controlled cases are limited probes, not complete verification. The bundle's old IRC:37-2012 PDF was scanned but not text-extracted for this report; the code edition must not be confused with IRC:37-2018 in PlateX's current library.

REA reported that Ghidra, IDA and Kuna native providers were not configured. Therefore there is **no native decompilation or call-graph evidence** for the exact numerical solver implementation. The result must not be read as a complete recovery of IITPAVE's equations, numerical integration, limit checks, or hidden functionality. REA's JAR inventory and PE parsers are static observations; Windows API imports or embedded names do not themselves prove reachable code paths.

| ID | Evidence / reproducibility |
|---|---|
| E1 | REA JAR inventory, parent evidence `ev_5306a99c31d0867ad10abc72f588542d78e2a0d7bab3b1fba54010eb892b7af5`: complete central-directory scope, 32 inventoried occurrences, including `META-INF/MANIFEST.MF`, `NewJFrame1.class`, `NewJFrame.class` and handler classes. JAR SHA-256 `4d8e04440977a12c5e01f2fca37b198f17a69cf962dbcee1c53f15c14d932adf`. |
| E2 | REA PE imports, evidence `ev_d0cfff81aed8eb8d1153e4bee682bb6c0946bf4fc3917af6579d32f61ebd914e`: `IITPAVE.exe`, PE32/x86, 573,541 bytes, SHA-256 `0a217406c5700de84db017e84e964ce96d4abd6995357e2dfb2499eb2c62d97c`; imports include Windows file, process and console functions. `IITPAVE/IITPFILE.exe` has the same SHA-256. REA resource evidence `ev_513c158efedfec69f77fb1e7c4840045f57e2177dc0f130567e3209f27560ed3` found no PE resource directory. |
| E3 | Java class-file static inspection: `NewJFrame1` manifest entry and `NewJFrame` method bytecode / constant pools; the relevant methods and offsets are listed in §1. This is not evidence of an observed GUI session. |
| E4 | Root `IITPAVE.IN`, `iitpave.out`, `gauss.qua`; nested `IITPAVE/IITPAVE.IN`, `IITPAVE/IITPAVE.out`, and `IITPAVE/IITPAVE_TDC.txt`. These are shipped artifacts; `result.txt` is a different example and is not paired with the current root input. |
| E5 | Controlled subprocess runs of copies of `IITPAVE.exe` and `gauss.qua` from isolated temporary directories. The root seven-layer input reproduced the shipped root output byte-for-byte, exit code 0. Additional three-layer scaling, single/dual-wheel, and interface probes are specified in §2. |
| E6 | PlateX source: [schemas](backend/hosnt12/schemas.py), [mesh](backend/hosnt12/mesh.py), [elements](backend/hosnt12/elements.py), [materials](backend/hosnt12/materials.py), [boundary](backend/hosnt12/boundary.py), [loads](backend/hosnt12/loads.py), [solver](backend/hosnt12/solver.py), [postprocess](backend/hosnt12/postprocess.py), and [IRC adapters](backend/hosnt12/irc/adapters.py). |

**Evidence terminology:** “Observed” means a file, static bytecode/PE fact, or specified controlled output was actually inspected. “Inferred” identifies an engineering interpretation consistent with those facts. “Unknown” means the inspection did not establish the claim. REA evidence IDs identify this investigation's in-memory records; the observations and artifact hashes are recorded here because no binary dumps or permanent evidence bundle were requested.

## 1. How IITPAVE runs

### 1.1 Components and entry points

**Observed:** `IITPAVE_START.jar` is a Java archive; its manifest declares `Main-Class: NewJFrame1` and a Java 1.6-era build. Its class inventory contains a main screen, a `NewJFrame` form, event-handler classes and image resources [E1, E3]. The package also includes `IITPAVE.exe`, a native 32-bit PE, and a byte-identical nested `IITPAVE/IITPFILE.exe` [E2]. The binary contains Fortran runtime strings and an embedded build path ending in `IITPAVE.FOR`, together with `MAIN$IITPAVE`: this strongly suggests a compiled Fortran calculation core, but a source file was not recovered.

`launch.jnlp` declares `NewJFrame1` and Java 1.6+ but points to a historical `JavaApplication7.jar` and an old local codebase. The generic `README.TXT` also names that historical JAR. These are packaging clues, not proof that those old launch instructions work for the current copy. The distribution includes a Java runtime installer; it was not run.

### 1.2 File and calculation pipeline

The following is a **static control-flow reconstruction** of the GUI, not a live GUI trace [E3]:

1. The initial screen contains choices to design a new section or edit an existing file. `NewJFrame.inter_dep` opens a file chooser and reads input using `FileReader`, `BufferedReader` and `StringTokenizer`; it parses the number of layers and analysis points and populates form fields (bytecode offsets 24–85, 326–329, 591–604).
2. `NewJFrame.jButton1ActionPerformed` gathers the values and checks for empty fields. It writes a text input file at `IITPAVE\\IITPAVE.IN` with `FileWriter` (creation at bytecode offsets 671–678, write/flush 709–714). Empty-field validation is observed; full numeric range and physical admissibility validation were not established.
3. The run handler `jButton4ActionPerformed` checks for the input, then invokes `cmd /c IITPFILE.exe` with `PATH=IITPAVE` and working directory `IITPAVE`, reads child stdout, and waits for the process (offsets 0–12, 26–65, 118). This establishes intended invocation and file locations in the class, not successful operation of the GUI on this machine.
4. A result-display handler reads `IITPAVE//IITPAVE.out` into a text area. Controls also refer to viewing results and opening a file in an editor [E3].

**Observed runtime:** starting a copy of the native executable with `IITPAVE.IN` and `gauss.qua` in its working directory produced console output and `iitpave.out`. The supplied seven-layer case exited with status 0 and exactly reproduced the supplied output file [E5]. This establishes that path for that input; it does not establish how every GUI action behaves, nor that every failure returns a nonzero exit status.

### 1.3 Output

The text output echoes the section and load, identifies “Single Wheel” or “Dual Wheel”, then lists `Z`, `R`, `SigmaZ`, `SigmaT`, `SigmaR`, `TaoRZ`, `DispZ`, `epZ`, `epT`, `epR` [E4, E5]. The formatting is compact fixed-width scientific notation: adjacent fields can touch, so naïve whitespace splitting may fail. The physical units of all output columns and sign conventions are not separately declared in the shown output header. Stress in MPa, displacement in mm, and dimensionless strain are **consistent with** the input unit system and dimensional relationships, but should be confirmed against authoritative documentation or a verified test before automated interchange.

At a tested interface, the ordinary row approached the result at `z = interface − 0.1 mm` and the `L` row approached the result at `z = interface + 0.1 mm`; for that case the evidence supports interpreting `L` as the lower-side value (§2.4). This does not prove the implementation's behavior for all interfaces or edge cases.

## 2. Algorithms and numerical methods

### 2.1 Layered elastic model: evidence and limits

**Observed:** the interface requests a layer count, one elastic modulus and Poisson ratio for each layer, thicknesses for the upper layers, a wheel load and pressure, and depth/radial response coordinates [E3, E4]. A three-layer input contains two finite thicknesses, consistent with the final layer being treated differently. The output includes vertical, radial and circumferential stresses, vertical displacement, and three strain components. Responses changed with layer material, loading and depth in the controlled runs [E5].

**Engineering inference:** the format and outputs are consistent with a horizontally extended, isotropic multilayer elastic half-space and circular load representation of the Burmister family. The last layer is plausibly the half-space. They do **not** by themselves prove the exact half-space boundary condition, layer-interface bonding treatment, the complete formulation, the name/version of a published algorithm, or its numerical implementation. “IITPAVE is layered elastic” is useful as a model-category interpretation, not a recovered source-code specification.

### 2.2 Quadrature and Bessel-related clues

`gauss.qua` contains tabulated negative abscissae and positive weights for symmetric 10-, 6-, and 4-point Gauss–Legendre rules [E4]. The binary contains the filename `gauss.qua` and debug-name strings including `BESS`, `BESROT`, `ROOTS`, `FINAL`, `MATIN`, `BUBBL`, and `ABCD`. These are compatible with quadrature and Bessel/root-based solution methods commonly used in axisymmetric layered elasticity. **Unknown:** which routines are reached, which integrals are evaluated, how roots are obtained, truncation/convergence criteria, precision, stability strategy, and whether those names represent the expected mathematical functions. The data file and names alone do not prove that a specific quadrature rule is used for a particular wheel or depth.

### 2.3 Loads, superposition and selected experiments

For a uniformly loaded circular footprint, geometry gives `a = sqrt(P / (πp))`; with `P = 20,000 N` and `p = 0.56 MPa = 0.56 N/mm²`, this would give approximately 106.6 mm. The native input has force and pressure, not a separate contact-radius field. The formula is a **geometry inference**, not a recovered instruction from IITPAVE's binary.

In a three-layer test (E = 2000/200/75 MPa, ν = 0.3, top thicknesses 100/300 mm, point `Z=200, R=155 mm`), doubling force from 20 to 40 kN **and** pressure from 0.56 to 1.12 MPa preserves the inferred footprint radius. Every printed response doubled within display precision: for example `SigmaZ` −0.05222 to −0.1044, `DispZ` 0.2371 to 0.4743 [E5]. This is consistent with linear elastic scaling for that case; changing force alone changes the inferred contact area and is not the same test.

With the same section, load and pressure, dual mode at `R=155` produced twice the single-wheel scalar outputs at `R=155` within displayed rounding. At `R=0`, dual `SigmaZ` (−0.1061) matches the sum of single responses at `R=0` (−0.08990) and `R=310` (−0.01618), and corresponding vertical displacement agrees to rounding. This is consistent with superposing two wheel contributions at 310 mm spacing, but the actual geometry and component transformations are **not confirmed from native code**. Do not treat `R` as an arbitrary 2-D `(x,y)` location or assume user-adjustable dual spacing without independent confirmation.

The dual-wheel `TaoRZ` at `R=155` is approximately twice the single-wheel value (−0.05905 versus −0.02953). If this coordinate denotes the physical midpoint between two equal symmetric contacts and `TaoRZ` is the net signed shear in the line between them, symmetry would require cancellation. The output's component basis and superposition convention have not been recovered, so this is a **targeted concern to investigate**, not a confirmed defect or a proven physical interpretation of the output.

### 2.4 One-sided interface test

For the same three-layer section, single wheel, `R=155 mm`, and the 400 mm cumulative interface, four reported rows were:

| Depth / row | SigmaZ | SigmaT | DispZ | epZ |
|---|---:|---:|---:|---:|
| 399.90 | −0.02197 | 0.02339 | 0.1962 | −0.0001734 |
| 400.00 | −0.02196 | 0.02341 | 0.1962 | −0.0001734 |
| 400.00 L | −0.02196 | 0.002896 | 0.1962 | −0.0003093 |
| 400.10 | −0.02195 | 0.002894 | 0.1962 | −0.0003092 |

The upper and lower limiting rows closely follow the two neighboring depths; vertical stress and displacement are approximately continuous while tangential stress and vertical strain change. This supports one-sided recovery for this **particular** interface, including the meaning of `L` in this experiment. Rounding limits what can be inferred. No full interface treatment or numerical tolerance is established by this one case.

### 2.5 Seven-layer interface discrepancy

The supplied root example has seven layers with E = 3000, 3000, 100, 5000, 600, 80, 80 MPa; ν = 0.45, 0.45, 0.35, 0.25, 0.25, 0.35, 0.35; thicknesses 100, 100, 100, 200, 200, 200 mm; dual 20 kN wheels at 0.7 MPa. A copy produced the bundled `iitpave.out` byte-for-byte [E5]. A follow-up at the 700 mm interface, `R=155 mm`, gave:

| Z (mm) / row | SigmaZ | TaoRZ | DispZ |
|---|---:|---:|---:|
| 699.90 | −0.03661 | 0.03086 | 0.1999 |
| 700.00 | −0.03665 | 0.03089 | 0.1998 |
| 700.00 L | −0.01110 | −0.001175 | 0.1882 |
| 700.10 | −0.01110 | −0.001175 | 0.1882 |

The continuity issue persists in neighboring-depth results; it is not just a printed `L` label. Under an ideal perfectly bonded interface with no applied interfacial traction, vertical and shear tractions and displacement should be continuous. The observed result warrants independent comparison and investigation of model assumptions, numerical conditioning, interface treatment, and output conventions. The input includes a relatively stiff 5000 MPa layer over softer layers, but **no cause has been established**. This finding should not be generalized beyond the tested case.

### 2.6 Fatigue and rutting

The observed response file contains stresses, strains and displacement, not an explicit fatigue life, rutting life, traffic damage, reliability, or pass/fail decision [E4, E5]. No fatigue/rutting equation was recovered from the native executable or demonstrated in a runtime test. Their presence elsewhere in an uninspected path cannot be ruled out; do not claim IITPAVE performs or does not perform a complete IRC design from this limited evidence. Applying design equations requires separately verified edition-specific inputs and criteria.

## 3. IITPAVE inputs, units, defaults and constraints

| Input | Observed form | Units / confidence |
|---|---|---|
| Number of layers | First record; GUI layer selector contains 1–10 | Count; selector range is observed, not the native executable's proven maximum |
| Elastic modulus | One number per layer, second record | MPa, explicitly labeled in GUI/output; `E`/resilient modulus selection depends on project input |
| Poisson's ratio | One per layer, third record | Dimensionless, `Mu` in output. One bundled case uses 0.5; this does not establish a validated range or safe conditioning |
| Layer thickness | `n−1` values in example input | mm; examples omit a final thickness, consistent with a half-space but not proof of its numerical implementation |
| Single-wheel load and tyre pressure | Pair on one record | N and MPa, explicitly labeled |
| Analysis locations | Count followed by depth/radial-distance pairs | mm; depth `Z` and `R`. Full coordinate and sign convention, particularly dual-wheel basis, remains to be verified |
| Wheel set | Final integer; tested `1` and `2` | GUI and output identify 1 as single, 2 as dual; no independent wheel separation field is evident in the inspected form/input |
| Contact radius | No separate field found in inspected input | Can be calculated geometrically from supplied force and uniform pressure, subject to verifying the native model |
| Parameters for thermal/moisture/foundation, fatigue/rutting | None observed in this input format or inspected GUI labels | Their absence from this path is not proof no other code path exists |

The bundled root input uses 20,000 N per wheel and 0.7 MPa, four query points and dual mode. The nested example uses 20,000 N and 0.56 MPa, 3 layers, and 4 points. These are **examples**, not validated defaults or universal code requirements. A GUI empty-field message is present; numeric limits, unit enforcement, maximum query count, support for unbonded interfaces, and material-default behavior remain unverified. Do not assume physically questionable or inconsistent entries are automatically rejected.

## 4. Similarities with PlateX

Both systems accept layered material descriptions involving moduli, Poisson ratios and thicknesses; both support mechanical wheel/contact loading and point responses. Their paired output concepts overlap for vertical displacement and some stresses, and both can form multi-position engineering workflows. Both should be supplied site-appropriate material properties and load geometry; IRC trial sections are not automatically a complete design.

PlateX represents circular and rectangular patches with force and geometric footprint. Its circular pressure is derived from force/area and integrated over element intersections; clipped areas retain their pressure rather than being rescaled. IITPAVE instead exposes wheel force, tyre pressure, wheel set and radial/depth queries in the inspected path. Conversion is possible for a single uniform circular contact only after checking units, orientation, contact assumptions, and placement. A 40 kN dual pair is not the same as an 80 kN complete axle.

## 5. Key differences from PlateX

| Topic | IITPAVE: inspected artifact | PlateX: current source |
|---|---|---|
| Governing model | Layered elastic axisymmetric/radial representation is strongly suggested; exact native equations and final-layer condition are unverified. | Finite rectangular higher-order plate with Q8 serendipity elements and 12 DOFs per node; 3×3 bending/foundation/loading and reduced 2×2 transverse shear integration. |
| Through-depth physics | Outputs include `SigmaZ` and `epZ`; interface probes show different one-sided values. | Plane stress `sigma_z = 0`; `T3`, `WS`, `T3S` constrained at every node, so `eps_z = 0` in this formulation. |
| Layers | Examples show isotropic E and ν for each layer and no final-layer thickness. Bonding/slip and half-space behavior require confirmation. | Finite thickness stack, bonded kinematics, isotropic or orthotropic plies; explicit stacks must cover `−h/2` to `+h/2` without gaps. No semi-infinite subgrade. |
| Domain and supports | Input lacks finite plan dimensions and plate edge supports in the inspected path; inference is horizontally extended layered domain. | Finite `a × b` geometry, structured mesh, six plate-edge boundary-condition choices; Winkler/Pasternak foundation or dimensionless equivalents. |
| Loads | Input gives force, tyre pressure, single/dual choice and radial/depth points. Exact native dual-wheel transformation is unresolved. | Sinusoidal/uniform distributed pressure, nodal loads, circular/rectangular patches, and translated-position sweeps; patches can cross an edge without pressure rescaling. |
| Thermal / moisture | Not found in inspected input/output path; other paths unverified. | Prescribed through-depth three-coefficient thermal/moisture profile and uniform or sinusoidal in-plane distribution. Not a transient climate or heat-transfer model. |
| Results | Text file and console output for vertical/radial/tangential stress, shear, vertical displacement and three strain labels. | Field displacement and point `w`, `sigma_x`, `sigma_y`, `tau_xy`, `tau_xz`, `tau_yz`; no reported `sigma_z`, `eps_z`, or horizontal strains in `PointResult`. |
| Architecture | Java Swing-like form / text-file handoff / 32-bit native executable, established as above; full implementation unknown. | Python NumPy/SciPy solver, typed Pydantic inputs, FastAPI routes and React/Material UI. Reusable sparse factorization for load sweeps. |

PlateX's native 12-DOF order is `[U, V, W, T1, T2, T3, US, VS, WS, T1S, T2S, T3S]`. The constrained thickness-stretching DOFs are essential to interpreting the plane-stress model; using a finite extra “subgrade” ply does not turn the plate into a three-dimensional elastic half-space. PlateX extrapolates transverse shear strains from 2×2 Gauss points before applying the shear constitutive matrix. Its laminate reference rigidity uses the full stack D11 [E6].

## 6. Accuracy, relevance and IRC workflow assessment

### 6.1 Flexible pavements

IITPAVE's observed `epZ`, `epT`, and `epR` outputs and layered/radial inputs are closer in kind to the response quantities used in layered-elastic flexible-pavement design. That makes an independently verified IITPAVE-style method **more directly relevant** for IRC:37 vertical subgrade compressive strain and selected layer-interface responses than the current PlateX model. It does not mean the specific binary has been validated for the intended material, load, interface, or climate. The seven-layer continuity anomaly is a concrete reason to perform independent checks before reliance on that case.

PlateX's `catalogue_profile`, `catalogue_layers`, standard dual-wheel patches and critical-location metadata are supplied through the vendored IRC library and adapters. Its flexible adapter constructs a **finite** user-selected subgrade thickness and carries a `eps_z = 0` / Burmister limitation notice. Critical-point labels describe the IRC quantity of interest; the current result schema returns stresses and displacement, not the requested tensile or vertical strains. Supplying the IRC stack does not establish IRC:37 fatigue/rutting compliance or make PlateX equivalent to IITPAVE [E6].

### 6.2 Rigid pavements and foundations

PlateX can represent a finite pavement slab, its idealized edge supports, patch geometry, Winkler/Pasternak foundation and prescribed thermal/moisture strains. These are directly relevant to idealized slab/plate bending and curling questions; their adequacy depends on joints, support, load transfer and field calibration. The inspected IITPAVE input has no explicit plate geometry, edge conditions, foundation springs or thermal profile, and does not demonstrate a rigid-jointed-slab analysis. Absence is limited to the inspected workflow.

The PlateX IRC:58 adapter offers raw subgrade `k` or lumped effective `k`; it guards against using an effective foundation with explicit supporting layers. For climate-zone differential it uses a linear through-depth approximation and documents that IRC daytime profiles are nonlinear. An IRC slab-only differential is rejected across an explicitly layered stack. None of these choices automatically models joint load transfer, permanent curl, seasonal moisture, or complete rigid-pavement compliance.

### 6.3 Verification and recommended comparison program

The PlateX work log records legacy parity testing, 59 passing pytest tests, 44 CLI self-checks and a completed 10×10 paper comparison. The latter reports up to 18.478% difference from a published Table 3 axial-stress value with an explicitly assumed Table 3 pressure; this is not an IITPAVE comparison or a general error bound. IITPAVE's byte-for-byte reproduction of a bundled output establishes repeatability for the tested binary/input, **not validation**.

Before using either output as a design decision:

1. Confirm the applicable IRC edition, contact conventions, units, interfaces and critical response definitions. Record wheel force **per wheel**, pressure, radius, wheel centres and query coordinates explicitly.
2. Benchmark IITPAVE's single-wheel homogeneous or layered cases against an independent analytical or validated layered-elastic solver, including off-axis and dual-wheel shear directions. Reproduce the §2.5 interface discontinuity with alternate independent implementations and varied material contrasts before diagnosing it.
3. Perform mesh refinement, boundary-distance and support sensitivity studies for PlateX. Compare only response components and boundary conditions that both models represent; do not compare IITPAVE `epZ` with a PlateX stress query as if they were equivalent.
4. Treat measured or validated project-specific material, traffic and thermal inputs as inputs to a broader design process. Implement or use separate, independently verified code-specific fatigue/rutting and reliability checks where required.

## 7. Unresolved questions and next investigation steps

- Recover or inspect the native solver's actual call graph and equations with a configured native decompiler, including use of `BESS`, `BESROT`, `ROOTS`, quadrature tables, integration limits, precision and any interface boundary matrix.
- Establish exact radial/dual-wheel geometry and signed component transformations, including the midpoint `TaoRZ` observation; check whether output stresses are expressed in wheel-centred bases or a shared global basis.
- Determine why the seven-layer case fails the expected continuity check, including whether output rows are sampled at identical locations, units and conventions; investigate conditioning and other material contrasts.
- Establish numeric validity limits, error handling, permitted layer/point counts, exact final-layer and bonding assumptions, and any uninspected fatigue/rutting functionality.
- Validate all output units and signs against authoritative documentation and controlled analytical examples. A complete GUI end-to-end run was not performed in this investigation.
