import { Button } from "@mui/material";
import ArrowForward from "@mui/icons-material/ArrowForward";
import type { Result } from "../api/client";
import { Plot } from "../components/Plot";

export function Landing({ result, openSolver, openIrc, openValidation }: {
  result: Result | null;
  openSolver: () => void;
  openIrc: () => void;
  openValidation: () => void;
}) {
  return <div className="landing">
    <section className="landingHero">
      <div className="landingIntro">
        <span className="landingKicker">Pavement analysis workbench</span>
        <h1>See how the pavement responds.</h1>
        <p>Explore deflection, stress and strain across pavement layers under wheel loads, pressure and environmental effects.</p>
        <Button variant="contained" size="large" endIcon={<ArrowForward />} onClick={openSolver}>
          Open the solver
        </Button>
      </div>
      <div className="landingFigure">
        <div className="landingFigureHead"><span>Transverse displacement</span><span>HOSNT12 · Q8</span></div>
        {result ? <Plot field={result.field} surface /> : <div className="landingFigureEmpty" role="status">Preparing the example analysis…</div>}
        <p>Computed pavement response · vertical displacement exaggerated</p>
      </div>
    </section>
    <section className="landingCapabilities">
      <div className="landingSectionTitle"><span>Built for engineering exploration</span><h2>From layer properties to pavement response.</h2></div>
      <div className="landingCapabilityList">
        <article><h3>Model the section</h3><p>Configure a finite pavement section, its bonded layers, edge supports and elastic foundation. Apply pressure, contact patches, thermal and moisture effects.</p><Button onClick={openSolver}>Explore the solver</Button></article>
        <article><h3>Place real load cases</h3><p>Explore IRC pavement and bridge load geometries. Use IRC:37 layered-elastic analysis for a flexible pavement over a semi-infinite subgrade.</p><Button onClick={openIrc}>Explore IRC analysis</Button></article>
        <article><h3>Inspect the evidence</h3><p>Review stiffness diagnostics, compare the plate model with published benchmarks, and export response data and deflection plots.</p><Button onClick={openValidation}>View validation</Button></article>
      </div>
    </section>
    <section className="landingAchievement">
      <div><span className="landingKicker">The work behind PlateX</span><h2>Research-grade methods, brought into one workbench.</h2></div>
      <div><p>PlateX brings a higher-order finite-element formulation, layered-elastic analysis and IRC load preparation into an interactive environment. It turns detailed numerical models into results that can be inspected, compared and exported.</p>
        <p>The validation view makes comparisons visible, including cases outside the selected tolerance. Model choice, inputs and convergence remain part of the engineering assessment.</p>
        <Button variant="outlined" onClick={openValidation}>Explore the benchmark results</Button></div>
    </section>
  </div>;
}
