import { useState } from "react";
import { Alert, Button } from "@mui/material";
import { api, fmt, type Benchmark, type Result } from "../api/client";
import { Select } from "../components/Controls";

export function Validation({ result }: { result: Result | null }) {
  const [thermal, setThermal] = useState(false),
    [bench, setBench] = useState<Benchmark | null>(null),
    [busy, setBusy] = useState(false),
    [err, setErr] = useState("");
  const run = async () => {
    setBusy(true);
    setErr("");
    try {
      setBench(await api.benchmark(thermal));
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
          <div className="crumb">Workbench / Diagnostics</div>
          <h1>Matrix &amp; Validation</h1>
          <p>
            Inspect the latest stiffness matrix and reproduce the reference
            case.
          </p>
        </div>
      </div>
      <div className="equalgrid">
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
          <p>10 × 10 mesh · Simply supported · K₀ = J₀ = 0</p>
          <fieldset disabled={busy}>
            <Select
              label="Published TSDT benchmark"
              value={thermal ? "3" : "2"}
              set={(v) => {
                setThermal(v === "3");
                setBench(null);
              }}
              items={[
                ["2", "Table 2 · Mechanical"],
                ["3", "Table 3 · Hygrothermal"],
              ]}
            />
          </fieldset>
          {thermal && (
            <p>Table 3 uses the archive’s assumed pressure of 100 kPa.</p>
          )}
          <Button variant="contained" disabled={busy} onClick={run}>
            {busy ? "Solving…" : "Run benchmark"}
          </Button>
          {err && <Alert severity="error">{err}</Alert>}
          {bench && (
            <table>
              <thead>
                <tr>
                  <th>Quantity</th>
                  <th>Computed</th>
                  <th>Paper</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(bench.computed).map(([k, v]) => (
                  <tr key={k}>
                    <th>{k}</th>
                    <td>{fmt(v)}</td>
                    <td>{fmt(bench.reference[k])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </>
  );
}
