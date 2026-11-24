import { useState } from "react";
import { Alert, Button } from "@mui/material";
import {
  api,
  fmt,
  type H2Refinement,
  type PaperReport,
  type Result,
} from "../api/client";
import { Num } from "../components/Controls";

const quantity = {
  w_bar: "w̄ — Dimensionless deflection",
  sigma_x_bar: "σ̄x — Dimensionless axial stress",
  tau_xy_bar: "τ̄xy — Dimensionless longitudinal shear stress",
  tau_xz_bar: "τ̄xz — Dimensionless transverse shear stress",
};

function H2StressStudy() {
  const [study, setStudy] = useState<H2Refinement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      setStudy(await api.h2Refinement());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const errorPct = (value: number, reference: number) => fmt(100 * Math.abs((value - reference) / reference));
  return <section>
    <h3>H2 axial stress · mesh refinement</h3>
    <p>At the centre of the top face, thermal expansion offsets most of the stress from the
      computed strain. The remaining axial stress is small, so its percentage error is sensitive
      to the mesh. Compare it with the centre deflection as the mesh gets finer.</p>
    <Button variant="outlined" onClick={run} disabled={busy}>
      {busy ? "Solving three meshes…" : "Run H2 mesh refinement"}
    </Button>
    {error && <Alert severity="error">{error}</Alert>}
    {study && <>
      <p>Published axial stress σ̄x = {study.stress_reference.toFixed(5)}</p>
      <div style={{ overflowX: "auto" }}><table>
        <thead><tr><th>Mesh</th><th>Deflection w̄</th><th>Axial stress σ̄x</th><th>Stress error (%)</th></tr></thead>
        <tbody>{study.meshes.map(row => <tr key={row.mesh}>
          <th scope="row">{row.mesh} × {row.mesh}</th><td>{row.w_bar.toPrecision(8)}</td>
          <td>{row.sigma_x_bar.toPrecision(8)}</td><td>{errorPct(row.sigma_x_bar, study.stress_reference)}</td>
        </tr>)}</tbody>
      </table></div>
      {study.stress_limit_estimate !== null && study.observed_order !== null
        ? <p>Estimated stress at zero mesh spacing (Richardson extrapolation) <strong>{study.stress_limit_estimate.toPrecision(8)}</strong>.
          The observed convergence order is {study.observed_order.toFixed(2)}.
          The estimate differs from the published value by {errorPct(study.stress_limit_estimate, study.stress_reference)}%.</p>
        : <p>The three meshes did not yield a consistent convergence order for extrapolation.</p>}
      <p className="meta">The benchmark pass/fail summary uses the original 10 × 10 solve.</p>
    </>}
  </section>;
}

export function Validation({ result }: { result: Result | null }) {
  const [tolerance, setTolerance] = useState(2),
    [bench, setBench] = useState<PaperReport | null>(null),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState("");
  const run = async () => {
    setBusy(true);
    setErr("");
    try {
      setBench(await api.benchmarkSuite(tolerance));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="pageHead">
        <div>
          <h1>Matrix &amp; validation</h1>
          <p>Stiffness diagnostics and published plate benchmarks</p>
        </div>
      </div>
      <div className="workgrid validationGrid">
        <section className="card inner">
          <h2>Stiffness matrix</h2>
          {result ? (
            <>
              <p>
                {result.ndof.toLocaleString()} DOFs ·{" "}
                {result.free_dofs.toLocaleString()} free
              </p>
              <dl>
                <dt>Nonzero entries</dt>
                <dd>{result.stiffness_info.nnz.toLocaleString()}</dd>
                <dt>Density</dt>
                <dd>{fmt(result.stiffness_info.density_pct)}%</dd>
                <dt>Maximum asymmetry</dt>
                <dd>{fmt(result.stiffness_info.max_asymmetry)}</dd>
              </dl>
              {[
                ["Bending block Db", result.stiffness_info.Db_top_left_4x4],
                ["Shear block Ds", result.stiffness_info.Ds_top_left_2x2],
              ].map(([title, rows]) => (
                <details key={String(title)}>
                  <summary>{String(title)}</summary>
                  <table>
                    <tbody>
                      {(rows as number[][]).map((r, i) => (
                        <tr key={i}>
                          {r.map((n, j) => (
                            <td key={j}>{fmt(n)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              ))}
            </>
          ) : (
            <p>Run a plate analysis to inspect the matrix.</p>
          )}
        </section>
        <section className="card inner">
          <h2>Zidi et al. (2014)</h2>
          <p>10 × 10 mesh · Simply supported · Homogeneous ceramic · TSDT</p>
          <details><summary>Replication settings and pressure convention</summary>
            <p>Plate dimensions 1 × 3 × 0.1 m, E = 117 GPa, ν = 1/3, α = 7.11 × 10⁻⁶ /K and β = 0.
              The paper specifies the geometric ratios. The mesh and dimensions are replication settings.
              Each case uses sinusoidal pressure and dimensionless foundation parameters K₀ and J₀.</p>
            <p>Both tables print q₀ = 100, while the text gives a general convention of 100 GPa.
              This replication uses 100 Pa for Table 2 and assumes 100 kPa for Table 3.
              The authors’ intended Table 3 unit is unresolved.</p>
            <p>Table 2 has zero environmental loads. Table 3 uses t = (0, 10, 0) and c = (0, 100, 0).
              With β = 0, the ceramic has zero moisture expansion. Separate self-tests exercise nonzero β.</p>
          </details>
          <Num label="Tolerance (%)" value={tolerance} set={setTolerance} min={0} />
          <p className="meta">The default tolerance is 2% for all four quantities.
            A case passes when every absolute percentage error is within the selected tolerance.</p>
          <Button variant="contained" disabled={busy || !Number.isFinite(tolerance) || tolerance < 0} onClick={run}>
            {busy ? "Solving eight cases…" : "Run all eight cases"}
          </Button>
          {err && <Alert severity="error">{err}</Alert>}
          {bench && <>
            <p>Completed run · {bench.tolerance_pct}% tolerance</p>
            {[2, 3].map(table => <section key={table}>
              <h3>{table === 2 ? "Mechanical Loading — Table 2" : "Hygrothermal Loading — Table 3"}</h3>
              <div style={{ overflowX: "auto" }}><table>
                <thead><tr>{["Case", "K₀", "J₀", "Output parameter", "Published", "Computed", "Absolute error",
                  "Error (%)", "Status"].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
                <tbody>{bench.comparisons.filter(row => row.table === table).map(row =>
                  <tr key={row.case + row.parameter}>
                    <th scope="row">{row.case}</th><td>{row.K0}</td><td>{row.J0}</td>
                    <td>{quantity[row.parameter]}</td><td>{row.reference.toFixed(5)}</td>
                    <td className="computed">{row.computed.toPrecision(8)}</td>
                    <td>{fmt(row.absolute_error)}</td><td>{fmt(row.error_pct)}</td>
                    <td><strong>{row.passed ? "Pass" : "Fail"}</strong></td>
                  </tr>)}</tbody>
              </table></div>
            </section>)}
            <h3>Validation summary</h3>
            <p>{bench.passed_cases.length + bench.failed_cases.length} cases · {bench.comparisons.length} parameter comparisons</p>
            <p>Passed ({bench.passed_cases.length}) · {bench.passed_cases.join(", ") || "None"}<br/>
              Failed ({bench.failed_cases.length}) · {bench.failed_cases.join(", ") || "None"}</p>
            <p>Mean absolute percentage error {fmt(bench.mean_error_pct)}%<br/>
              Maximum error {fmt(bench.worst.error_pct)}% · {bench.worst.case} · {quantity[bench.worst.parameter]}</p>
          </>}
          <H2StressStudy />
        </section>
      </div>
    </>
  );
}
