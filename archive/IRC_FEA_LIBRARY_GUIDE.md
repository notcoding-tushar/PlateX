# IRC library for the FEA solver

Companion file: `irc_fea_library.py` · Python 3.10+ · No third-party packages required.

The library contains **117 source-referenced provisions**, including **48 flexible-pavement catalogue figures / 288 exact trial sections**, plus numerical formulas, input checks, material adapters and vehicle-contact generators. It reads no PDFs at runtime and prints nothing when imported.

## 1. Sources and boundaries

Only the six supplied PDFs were used. No properties were obtained from other standards, websites or generic material databases. Where an IRC clause cites another standard, the library records only the requirement actually stated in the supplied IRC text.

| Supplied file | Edition printed inside | PDF page = printed page + |
|---|---|---:|
| Rigid pavement irc 58 2015.pdf | IRC:58-2015 | 10 |
| irc 37 2019.pdf | **IRC:37-2018** | 10 |
| Supporting Codes.pdf | IRC:SP:49-2014 | 8 |
| Rigid pavement construction IRC 15 2017.pdf | IRC:15-2017 | 2 |
| WBM layer IRC 19 2005.pdf | IRC:19-2005 | 8 |
| Bridge loading IRC 6 2017.pdf | IRC:6-2017 | 7 |

The flexible-pavement filename says 2019; the document itself identifies the edition as 2018. Source references follow the printed edition and actual pages. For example, IRC:58 Table 1 is on printed page 7 / PDF page 17, although the associated discussion starts on page 6.

Each `Provision` contains `data`, `units`, `source`, `kind` and `notes`. A `Source` supplies the code, clause/table/figure, printed pages, PDF pages and original filename. `get()` returns a defensive copy; `find()` searches the local registry. `FUNCTION_SOURCES` links the principal computational functions to registry keys.

```python
import irc_fea_library as irc

entry = irc.get("58.cbr_k")
print(entry.data[10])             # 55 MPa/m
print(entry.source.location)     # 5.7.3.4; Table 2
print(entry.source.pdf_pages)    # (19,)
```

This is an **input and checking library**. It does not assemble stiffness matrices, solve layered elasticity, search for maximum stress, or establish complete IRC design compliance.

## 2. What was extracted and converted

The following tables map every requested subject to its executable function or structured data. `get("key").data` accesses a registry entry. Construction requirements remain separate from elastic material properties.

### IRC:58-2015 — rigid pavement

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| PQC/DLC/GSB arrangements; Fig.1, p.3 | `58.layers` | Two ordered profiles; sheet/BC dimensions and subgrade requirement |
| Single/tandem/tridem loads and pressure; 5.2, p.4 | `58.axles`, `rigid_axle_group_patches()` | Historical loads, spectrum intervals, 0.8 MPa design pressure |
| Axle spacing; 5.3, p.4 | `58.spacing`, `rigid_top_down_eligible()` | Compare surveyed axle spacing with actual transverse joint spacing |
| Temperature differential; 5.6.1/Table1, pp.6–7 | `58.temperature`, `rigid_temperature_delta()` | Seven zones, four thickness columns; signed day/night differential |
| Foundation k; 5.7.3.1, pp.8–9 | `58.winkler`, `winkler_k_from_plate()` | Pressure/deflection; 750 mm plate, 1.25 mm standard deflection |
| CBR–k; Table2, p.9 | `58.cbr_k`, `rigid_cbr_to_k()` | Exact lookup; optional bounded linear interpolation |
| DLC thickness/strength; 5.7.4.1, p.11 | `58.dlc`, `check_dlc()` | 150 mm major-highway thickness; 7 MPa / bonded 10 MPa requirements |
| PQC flexural strength; 5.8.2, pp.12–13 | `58.pqc_strength`, `check_pqc()` | Minimum 4.5 MPa at 28 days; optional 1.10 strength-gain factor stored |
| PQC E and nu; 5.8.4.1, p.13 | `58.pqc_elastic`, `irc_material("PQC")` | Conditional 30,000 MPa / 0.15 stress-analysis preset |
| PQC thermal expansion; 5.8.5, p.13 | `58.pqc_alpha` | 10 × 10^-6 per °C |
| Interior/mid-panel, edge, near-joint positions; 6.1.1–6.1.3, pp.14–16 | `58.positions` | Load-case descriptions and critical tension surfaces; no invented joint offset |

The near-joint clauses do not provide a universal numerical offset. Edge loading refers to a tyre footprint tangent to the longitudinal edge; longitudinal mid-panel loading is not a separate prescribed interior-coordinate formula. The solver must position actual contacts and evaluate the response.

### IRC:37-2018 — flexible pavement

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| Six layer categories; 12.2, p.35 | `37.categories`, `FLEXIBLE_CATEGORIES` | Ordered top-to-bottom stacks a–f |
| Standard BC/binder/WMM/GSB profile; Fig.12.1, p.36 | `37.figure_12_1`, `catalogue_profile("a",5,traffic)` | All six labelled traffic columns and thicknesses |
| Other catalogues; Figs.12.2–12.48, pp.36–51 | `37.figure_12_2` … `37.figure_12_48`, `CATALOGUES` | All 48 figures digitised; 8 CBR values × 6 categories × 6 traffic values |
| Binder/mix selection; 9.1/Table9.1, pp.27–29 | `37.binder_options` | Traffic bands, road-class exceptions and special surfacing options |
| Temperature-dependent bituminous MR; 9.2/Table9.2, pp.29–30 | `37.bituminous_modulus`, `bituminous_modulus()` | 20/25/30/35/40 °C rows; measured-value caps |
| Bituminous Poisson ratio; 9.2, p.31 | `37.bituminous_modulus`, `Material` | nu = 0.35 |
| Structural layer properties; Table11.1, p.34 | `37.materials`, `irc_material()` | Named E/MR and nu presets; formulas where a fixed E is inappropriate |
| CBR moisture/density condition; 6.2, p.19 | `37.subgrade_test` | 4-day soaked default, density, specimen and percentile requirements |
| Subgrade MR from CBR; 6.3/Eqs.6.1–6.2, p.19 | `subgrade_resilient_modulus()` | Piecewise equation, with separate design-cap option |
| Effective subgrade and 100 MPa limit; 6.4/Eq.6.3, p.20 | `37.effective_subgrade`, `effective_subgrade_modulus()` | Equivalent MR from prescribed soil-system surface deflection; optional cap |
| GSB drainage/filter thickness; 7.2.2, pp.21–22 | `37.gsb` | 100 mm each / 150 mm combined, aggregate-size recommendation |
| Granular MR; 7.2.3/Eq.7.1, pp.22–23 | `granular_resilient_modulus()` | Support-dependent modulus using total contiguous granular thickness |
| CTSB; 7.3.1–7.3.2/Eq.7.2, pp.23–24 | `37.ctsb`, `cemented_intact_modulus()` | 200 mm minimum; intact UCS relationship separate from design 600 MPa |
| WMM/WBM base; 8.1, pp.24–25 | `37.unbound_base` | 150 mm minimum; 300/350 MPa over CTSB; combined GSB/base rule |
| CTB thickness, strength, E/nu; 8.2.1/Table11.1, pp.25–26/34 | `37.ctb`, `irc_material("CTB")` | 100 mm minimum, strength ages, 5000 MPa and nu 0.25 |
| CTB flexural strength; 8.2.2, p.26 | `ctb_flexural_strength()` | 20% of 28-day UCS, capped by stabilised-material type |
| Granular crack relief; 8.3, pp.26–27 | `37.crack_relief` | 100 mm, 450 MPa, nu 0.35; SAMI excluded structurally |
| Stabilised RAP; 8.4, p.27 | `37.rap` | 100 mm minimum, 800 MPa, nu 0.35 and ITS constraints |
| Standard structural load; 11.1.4, p.33 | `37.standard_load`, `flexible_standard_patches()` | 80 kN axle; analysis dual pair, 20 kN per wheel |
| Wheel load/spacing; 3.6, p.6 | `flexible_standard_patches()` | Two circular patches, 310 mm centres; 0.56/0.80 MPa cases |
| Analysis assumptions; Table3.1, p.9 | `37.analysis` | Isotropic linear elasticity, bonded interfaces and critical parameters |
| VDF; 4.4.3/Eqs.4.1–4.4, p.15 | `axle_equivalence()`, `vehicle_damage_factor()` | Fourth-power reference loads 65/80/148/224 kN; vehicle-average summation |
| Axle survey sample; 4.4.4/Table4.1, p.15 | `37.survey`, `axle_survey_minimum()` | Percentage plus applicable minimum; rounded up to integer samples |
| Spectrum classification; 4.4.5, p.16 | `37.spectrum` | 10/20/30 kN class intervals |
| Indicative VDF; Table4.2, p.16 | `indicative_vdf()` | Terrain/traffic fallback values with applicability notes |
| Critical strain/stress locations; 3.3/Figs.3.1–3.6, pp.4/10–12 | `critical_locations()` | Interface depths and one-sided response queries |

`catalogue_layers()` creates the code's structural analysis representation: bituminous courses combined using the selected bottom DBM modulus; adjacent WMM+GSB combined; granular crack relief retained separately; SAMI omitted from structural stiffness; subgrade represented as semi-infinite. A WMM course over CTSB uses the crushed-rock 350 MPa value. The physical construction profile remains available separately.

### IRC:SP:49-2014 — DLC

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| Width/thickness; 2, p.2 | `49.geometry` | 500 mm mechanised / 200 mm manual side extension; 150/100 mm thickness cases |
| Cement/aggregates; 3, pp.2–3 | `49.materials`, `grading_envelope()` | Cement options, absorption, grading and admixture limits |
| Compressive strength; 4.1, p.4 | `49.strength`, `check_dlc()` | Five-cube mean ≥7 MPa; each cube ≥5.5 MPa at 7 days |
| Mix proportions/content; 4.2, p.4 | `49.mix`, `check_dlc()` | OPC 14:1 / PPC-PSC 12:1 maximum; minimum 140 kg/m³ cementitious material |
| Drainage below DLC; 5, p.4 | `49.drainage` | GSB under DLC across road width |
| Subgrade compaction; 6, p.4 | `49.subgrade`, `check_dlc()` | ≥97% modified Proctor density; uniform support |
| Quality control; 7.10, p.8 | `49.qc`, `dlc_qc_plan()` | ±10 mm thickness; daily area-based density coverage and strength samples |

### IRC:15-2017 — construction provisions affecting the model

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| Concrete materials; 3, pp.3–8 | `15.concrete_materials`, `15.air_entrainment`, grading entries | Material limits, steel type and conditional air requirements |
| Concrete mix; 4, pp.10–12 | `15.mix`, `check_pqc()` | Water/CM, cement and measured flexural-strength requirements |
| Subgrade/layer arrangement; 6.1, p.16 | `15.layers` | PQC/DLC/drainage/filter/select-subgrade sequence |
| GSB properties/grading; 6.3/Table4, pp.17–18 | `15.layers`, `15.gsb_grading` | Six sieve envelopes, permeability, CBR and plasticity limits |
| Foundation k; 6.4/Table5, p.18 | `15.cbr_k`, `rigid_cbr_to_k(code="IRC:15-2017")` | Source-specific CBR–k table |
| Effective k; 6.5/Tables6–7, p.19 | `effective_k15()` | Separate untreated, cement-treated and DLC tables; missing-cell rejection |
| Joints; 8, pp.24 onward | `15.joints` | Typical panel dimensions, joint functions and saw-cut depth range |
| Dowels/ties; 8.3–8.4/Table8, pp.33–37 | `15.dowels`, `15.tie_bars`, `check_dowel()`, `tie_bar_options()` | Length/alignment checks and exact tie-bar options; no invented dowel stiffness |

Tie bars resist separation; they must not be treated as dowels carrying joint shear. The table is for the stated 3.5 m lane. Dowel diameter, spacing and joint spring properties require project design; this extraction does not assign arbitrary values.

### IRC:19-2005 — WBM

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| Description/applications; 2.1.1, p.3 | `19.description` | Layer role and material description |
| Silty/clayey subgrade restriction; 2.1.3, p.4 | `19.description`, `check_wbm()` | Require intervening granular layer |
| Aggregate physical properties; Table1, p.4 | `19.physical`, `check_wbm()` | LA **or** AIV, applicable flakiness limits |
| Grading/lift thickness; Table2, p.5 | `19.aggregate_grading`, `check_wbm()` | Three gradings; 100/75/75 mm compacted lifts |
| Screenings; Table3, p.6 | `19.screenings`, `check_grading()` | A/B envelopes and compatible coarse gradings |
| Construction; 4, pp.7–9 | `19.construction` | Relevant sequence and support/compaction conditions |

A 150 mm total WBM base under IRC:37 can contain two 75 mm lifts under IRC:19. These are different constraints. IRC:19's listed clauses do not give an elastic modulus; use the appropriate IRC:37 support-dependent rule rather than inventing a WBM E.

### IRC:6-2017 — optional bridge/deck load cases

| Requested subject / source | Library representation | Conversion to code |
|---|---|---|
| 70R/AA/A/B/SV classification; 201.1, p.4 | `6.classification` | Applicability labels and Class A cross-check requirement |
| Loads/forces; 202.1, pp.5–6 | `6.load_types` | Load-case labels only; no unrequested force formulas |
| 70R wheels/tracks; Fig.1, pp.10–11 | `6.70R_wheeled`, `6.70R_tracked`, `bridge_axles()`, `bridge_patches()` | 100 t wheeled train; 70 t tracked case; L/M/N alternatives |
| Vehicle positioning; 204.1.2–204.1.5, p.11 | `6.positioning`, `translate_patches()` | Simultaneous unit axles and clearance-constrained moving-load input |
| Class A axles; Fig.2, p.12 | `6.A_train`, `bridge_axles("A")` | Eight axle loads and seven gaps |
| Class A contacts; Table2, p.13 | `bridge_patches("A")` | Two equivalent side contacts per axle with tabulated B/W |
| Class B axles; Fig.4, p.14 | `6.B_train`, `bridge_axles("B")` | Eight axle loads and seven gaps |
| Class B contacts; Table4, p.15 | `bridge_patches("B")` | Tabulated rectangular equivalent contacts |
| Lane combinations; 204.3/Tables6–6A, pp.16–20 | `lane_load_cases()`, `6.lane_combinations` | Vehicle sequences, mixed-case width limits and mirrored arrangements |
| SV axles/tyres; Figs.6–6A, p.21 | `6.SV`, `bridge_axles("SV")`, `bridge_patches("SV_TRAILER")` | All 23 axles; 20 trailer axles with eight contacts each |
| SV transverse placement; 204.5.3/Fig.6B, p.22 | `combine_sv_contacts()` | Check ±300 mm eccentricity and supplied prime-mover resultants |
| Class AA; AnnexA/Fig.A-1, p.86 | `6.AA`, `bridge_axles("AA_WHEELED")`, AA patch cases | Track geometry and unequal wheeled axle shares; verified transverse centres required |

**Two contact-geometry limits are explicit:**

- **Class AA wheeled:** the low-resolution plan and cross-section do not resolve into one unambiguous transverse centre chain. Readable labels remain stored. `bridge_patches("AA_WHEELED")` requires four verified `aa_wheel_offsets_y_mm`; it does not guess them. Axle loads, axle spacing, unequal tyre shares and contact sizes are provided.
- **SV:** the figure specifies trailer contacts, but does not specify prime-mover tyre-contact geometry. `SV_TRAILER` returns 160 trailer contacts, totalling 360 t. Full SV axle data total 385 t. `combine_sv_contacts()` adds caller-supplied prime-mover contacts only after checking their three axle resultants.

Class A/B B–W contact dimensions and SV B–W labels have different directions in their figures. The module normalises them to `length_mm` along travel and `width_mm` across the deck. The 70R 610/510 mm tyre dimensions are not used as rectangular ground-contact lengths. Its contact length is derived from tyre load, pressure and tread width; the maximum stated pressure is converted from kgf/cm².

## 3. Numerical formulas and conventions

| Calculation | Implemented relationship | Source |
|---|---|---|
| Subgrade MR | `10*CBR` for CBR≤5; otherwise `17.6*CBR**0.64` | 37 Eqs.6.1–6.2 |
| Equivalent subgrade MR | `2*(1-nu**2)*p*a/delta` | 37 Eq.6.3 |
| Granular MR | `0.2*h_mm**0.45*MR_support` | 37 Eq.7.1 |
| Intact cemented E | `1000*UCS_28d` | 37 Eq.7.2 |
| CTB flexural strength | `min(0.2*UCS_28d, material_cap)` | 37 8.2.2 |
| Axle equivalence | `(group_load_kN/reference_kN)**4` | 37 Eqs.4.1–4.4 |
| Winkler k | `pressure_MPa/(deflection_mm/1000)` | 58 5.7.3.1 definition |
| Equivalent circular contact | `radius=sqrt(force/(pi*pressure))` | Geometry conversion from the specified wheel load/pressure |

CBR is entered as a percentage number, e.g. `8`, not `0.08`. Tandem/tridem load inputs mean the **total group load**. The standard flexible-pavement structural analysis uses one dual pair: **40 kN total**, consisting of two 20 kN wheels. The 80 kN figure refers to the whole four-wheel axle.

Native data use N, mm, MPa, k in MPa/m and temperature differences in °C. `Material.to_SI()`, `Layer.to_SI()`, `Patch.to_SI()` and `k_to_SI()` provide explicit SI exports.

| Quantity | Native → SI |
|---|---|
| Length | mm / 1000 → m |
| Elastic modulus/contact pressure | MPa × 10^6 → Pa |
| Foundation k | MPa/m × 10^6 → N/m³ |
| Force | N unchanged |
| Thermal expansion | per °C unchanged for temperature increments in K |
| Bridge tonne-force | 1000 × 9.80665 N; configurable with `tonne_force_N` |

The gravitational conversion and circle/rectangle geometry are unit/mathematical operations, not additional IRC material data. Patch force/pressure are positive **downward**; adapt the sign to the solver's coordinate convention.

Exact lookup is the default. Selected tables allow explicit `interpolate=True` as a numerical convenience; interpolation is identified as a software choice. Extrapolation and missing/dashed foundation cells are rejected. Catalogues are exact-only and never interpolate between CBR or traffic columns.

## 4. Source differences retained

| Source issue | Handling |
|---|---|
| IRC:58 Fig.1 sheet is labelled PVC but caption says polythene; BC diagram says BC2 while caption says BC1 | Keep conflicting labels in notes; preserve geometry and debonding function |
| DLC 75 μm passing limit: SP:49 Table1 = 10%, IRC:15 Table2 = 5% | Separate source tables; project must select governing requirements |
| IRC:15 Table7 raw effective k includes 389 and 417* MPa/m | Preserve raw values; design lookup applies 300 MPa/m maximum before interpolation, as required by the footnote |
| IRC:15 Table7 150 mm DLC at subgrade k=62 is a dash | Reject; never extrapolate or replace with zero |
| IRC:37 intact CTSB E from UCS differs from design 600 MPa | Separate function and design preset; no silent replacement |
| IRC:37 Section12.3 overlaps at 20 msa in its mix-parameter lists/reliability wording | Store both statements; catalogue profiles remain trial geometry, without automatic selection of disputed assumptions |
| IRC:37 Table4.2 labels overlap at 150 cvpd | Explicit software convention: use the higher traffic band at 150 |
| IRC:6 Table6 four-lane width overlaps the five-lane row | Use explicit Table6A 13.1≤CW<16.6 m range; also enforce its extra mixed-case minimum widths |

## 5. Use with the FEA solver

Put the Python file beside the solver and import it. No installation step is needed.

```python
import irc_fea_library as irc

pqc = irc.irc_material("PQC").to_SI()
k_soil = irc.rigid_cbr_to_k(10)            # 55 MPa/m
k_effective = irc.effective_k15(k_soil, 150, "DLC")
k_foundation = irc.k_to_SI(k_effective)    # 300e6 N/m³

delta_T = irc.rigid_temperature_delta("IV", 300)  # top minus bottom: +21 C
```

The temperature output is a top-to-bottom **difference**, not a uniform temperature rise or an automatic value for the solver's `t1/t2/t3` coefficients. Daytime temperature is nonlinear; Table1 does not uniquely determine its full depth profile. Night output uses the clause's approximate negative half-day magnitude. No permanent-curl correction from unrequested provisions is inserted.

For a rigid model, represent foundation support consistently: a slab on a lumped effective k and a model with explicit supporting layers require different support definitions. Do not count the same DLC stiffening twice. If the solver accepts dimensionless K0/J0 rather than physical foundation constants, apply its own documented normalisation before assigning these SI values. A CBR-derived resilient modulus is not k; no universal MR-to-k conversion is supplied. The selected clauses give no Pasternak shear parameter.

```python
# Exact flexible trial section and its structural input stack
profile = irc.catalogue_profile("b", 8, 30)
layers = irc.catalogue_layers("b", 8, 30, bituminous_E_MPa=2800)
checks = irc.check_flexible_stack(layers, category="b")
queries = irc.critical_locations(layers)
loads = [p.to_SI() for p in irc.flexible_standard_patches(ctb_fatigue=True)]
```

The bituminous modulus argument is an explicit project/trial input, capped by the relevant 35 °C table maximum. Catalogue modulus assumptions do not establish suitability for a particular road class. IRC:37's bonded, semi-infinite layered-elastic model needs the appropriate response calculation: directly feeding its stack to a finite rectangular HOSNT plate model does not by itself reproduce that model or its critical strains.

```python
# Bridge Class A: all eight axles act together
contacts = irc.bridge_patches("A")
placed = irc.translate_patches(contacts, dx_mm=1000, dy_mm=3500)

# Separate 70R tyre-pattern cases for the solver's moving-load sweep
cases_70R = {
    pattern: irc.bridge_patches("70R_WHEELED", tyre_pattern=pattern)
    for pattern in ("L", "M", "N")
}
```

The solver must integrate patch pressure against its own element shape functions and search positions/directions for governing effects. `translate_patches()` only moves geometry. A patch partly outside a domain requires integration over its intersection; its full load must not be reassigned to the clipped area. Bridge impact factors, force-combination factors and analytical wind/seismic models were not extracted from unrequested clauses.

Checks return `pass`, `fail` or `needs_input`, with a source reference. They evaluate the supplied subset only. `check_grading()` compares raw sieve envelopes; IRC:15's permitted fine-aggregate tolerances need separate project review. No strength, density, thermal expansion or moisture expansion coefficient is inferred from unrelated construction data.

## 6. Verification and remaining solver work

Tested on Python 3.12.14. Verification covered all 288 trial sections, construction-to-analysis thickness conservation, critical-interface depths, source-page bounds, formula values, foundation caps/missing cells, grading differences, axle totals, pressure-area resultants, motion invariance and input rejection. The built-in regression check can be rerun with:

```bash
python irc_fea_library.py --self-test
python irc_fea_library.py --summary
```

This verification checks the library's data handling and calculations; it is not validation of the existing FEA solver. Material-specific density, moisture expansion, arbitrary material E/nu, joint stiffness, complete thermal profiles, and project-specific geometry remain explicit solver/project inputs wherever the selected clauses do not supply them. No GUI, unrelated codes, benchmark printing or solver modifications are included.
