import { useEffect, useState } from "react";
import { Alert, Button, Checkbox, FormControlLabel } from "@mui/material";
import { api, fmt, type DepthPoint, type ElasticResponse, type ElasticResult } from "../api/client";
import { Num, Section, Select } from "../components/Controls";

function PointDetails({ row }: { row: ElasticResponse }) {
  const quantities: [string, number, string][] = [
    ["Displacement w", row.w_m * 1000, "mm"],
    ["Vertical stress σz", row.sigma_z_Pa / 1000, "kPa"],
    ["Radial stress σr", row.sigma_r_Pa / 1000, "kPa"],
    ["Hoop stress σθ", row.sigma_theta_Pa / 1000, "kPa"],
    ["Shear τrz", row.tau_rz_Pa / 1000, "kPa"],
    ["Vertical strain εz", row.eps_z * 1e6, "µε"],
    ["Radial strain εr", row.eps_r * 1e6, "µε"],
    ["Hoop strain εθ", row.eps_theta * 1e6, "µε"],
  ];
  return <details><summary>{row.layer} · {row.label?.split(" · ")[0]} · {fmt(row.depth_m * 1000)} mm</summary>
    <p className="meta">x {fmt(row.x_m)} m · y {fmt(row.y_m)} m · {row.side} at an interface</p>
    <dl>{quantities.map(([name, value, unit]) => <div className="dlrow" key={name}>
      <dt>{name}</dt><dd>{fmt(value)} {unit}</dd></div>)}</dl>
  </details>;
}

const menu = (values: (string | number)[]): [string, string][] => values.map(v => [String(v), String(v)]);

export function LayeredElastic() {
  const [options, setOptions] = useState<Awaited<ReturnType<typeof api.catalogue>>>();
  const [category, setCategory] = useState("a"), [cbr, setCbr] = useState("5"),
    [traffic, setTraffic] = useState("10"), [modulus, setModulus] = useState(2000);
  const [wheels, setWheels] = useState("dual"), [load, setLoad] = useState("normal");
  const [force, setForce] = useState<number | null>(null), [pressure, setPressure] = useState<number | null>(null),
    [spacing, setSpacing] = useState<number | null>(null);
  const [probe, setProbe] = useState(false), [point, setPoint] = useState<DepthPoint>(
    { x_m: 0, y_m: 0, depth_m: 0, side: "below", label: "Query point" });
  const [result, setResult] = useState<ElasticResult>(), [busy, setBusy] = useState(false),
    [error, setError] = useState(""), [retry, setRetry] = useState(0), [snapshot, setSnapshot] = useState("");
  useEffect(() => {
    let active = true;
    api.catalogue().then(v => { if (active) { setOptions(v); setError(""); } })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [retry]);
  const body = { category, cbr: Number(cbr), traffic_msa: Number(traffic), bituminous_E_MPa: modulus,
    wheels, ctb_fatigue: load === "ctb", points: probe ? [point] : [],
    wheel_force_N: force == null ? undefined : force*1000,
    pressure_Pa: pressure == null ? undefined : pressure*1e6,
    spacing_m: wheels === "dual" && spacing != null ? spacing : undefined };
  const signature = JSON.stringify(body);
  const run = async () => {
    setBusy(true); setError("");
    try { setResult(await api.elastic(body)); setSnapshot(signature); }
    catch (e) { setError(e instanceof Error ? e.message : "Analysis failed"); }
    finally { setBusy(false); }
  };
  return <div className="workgrid">
    <aside className="card">
      <div className="cardHeading"><h2>Trial pavement section</h2></div>
      <Section title="Catalogue & loading" open>
        {options && <>
          <Select label="Catalogue category" value={category} set={setCategory} items={menu(options.categories)} />
          <div className="two">
            <Select label="CBR (%)" value={cbr} set={setCbr} items={menu(options.cbr)} />
            <Select label="Traffic (MSA)" value={traffic} set={setTraffic} items={menu(options.traffic_msa)} />
          </div>
        </>}
        <Num label="Bottom DBM modulus (MPa)" value={modulus} set={setModulus} min={0} />
        <Select label="Wheel arrangement" value={wheels} set={setWheels}
          items={[["dual", "Standard dual pair"], ["single", "Single wheel"]]} />
        <Select label="Contact pressure case" value={load} set={setLoad}
          items={[["normal", "Standard"], ["ctb", "CTB fatigue"]]} />
      </Section>
      <Section title="Wheel load overrides">
        <p className="meta">Leave a field blank to use the selected IRC load case.</p>
        <Num label="Force per wheel (kN)" value={force} set={v => setForce(Number.isFinite(v) ? v : null)} min={0} />
        <Num label="Contact pressure (MPa)" value={pressure} set={v => setPressure(Number.isFinite(v) ? v : null)} min={0} />
        {wheels === "dual" && <Num label="Centre spacing (m)" value={spacing}
          set={v => setSpacing(Number.isFinite(v) ? v : null)} min={0} />}
      </Section>
      <Section title="Additional evaluation point">
        <FormControlLabel control={<Checkbox checked={probe} onChange={e => setProbe(e.target.checked)} />}
          label="Include a query point" />
        {probe && <>
          <p className="meta">Coordinates start at the wheel-set centre. Depth increases downwards.</p>
          <div className="two">{(["x_m", "y_m"] as const).map((k, i) => <Num key={k}
            label={i ? "y (m)" : "x (m)"} value={point[k]} set={v => setPoint({ ...point, [k]: v })} />)}</div>
          <Num label="Depth (m)" value={point.depth_m} min={0} set={v => setPoint({ ...point, depth_m: v })} />
          <Select label="Interface side" value={point.side} set={v => setPoint({ ...point, side: v as DepthPoint["side"] })}
            items={[["above", "Above"], ["below", "Below"]]} />
        </>}
      </Section>
      <div className="inner"><Button variant="contained" disabled={!options || busy} onClick={run}>
        {busy ? "Solving…" : "Run layered analysis"}</Button></div>
    </aside>
    <section className="card">
      <div className="cardHeading"><h2>Critical responses</h2>
        {result && <span className="meta" title={result.engine}>IRC:37 Layered Elastic</span>}</div>
      {error && <Alert severity="error" action={!options && <Button onClick={() => setRetry(v => v+1)}>Retry</Button>}>{error}</Alert>}
      {result ? <>
        {snapshot !== signature && <Alert severity="info">Inputs changed. Showing the previous solve.</Alert>}
        <div className="elasticResults">
          <p className="meta">{result.patches.length === 1 ? "Single wheel" : "Dual wheels"} ·
            {" "}{fmt(result.pressure_Pa/1e6)} MPa · tension positive</p>
          <table><thead><tr><th>Layer / position</th><th>Depth</th><th>Response</th></tr></thead>
            <tbody>{result.critical.map((row, i) => <tr key={i}>
              <th>{row.layer}<small>{row.label?.split(" · ")[0]}</small></th>
              <td>{fmt(row.depth_m*1000)} mm<small>{row.side}</small></td>
              <td>{fmt(1e6*(row.layer === "subgrade" ? row.eps_z : row.max_horizontal_strain))} µε
                <small>{row.layer === "subgrade" ? "Vertical" : "Max. horizontal"}</small>
                {row.layer === "CTB" && <span>{fmt(row.max_horizontal_stress_Pa/1000)} kPa</span>}</td>
            </tr>)}</tbody></table>
        </div>
        <Section title="Point stresses, strains & displacement">
          {[...result.points, ...result.critical].map((row, i) => <PointDetails key={i} row={row} />)}
        </Section>
        <Section title="Effective layers & wheel loads">
          {result.layers.map(l => <div key={l.name}><strong>{l.name}</strong>
            <p>{l.thickness_m == null ? "Half-space" : fmt(l.thickness_m*1000)+" mm"} ·
              {" "}{fmt(l.E_Pa/1e6)} MPa · ν {fmt(l.nu)}</p></div>)}
          {result.patches.map(p => <p key={p.label}>{p.label} · {fmt(p.force_N/1000)} kN ·
            {" "}{fmt(1000*(p.radius_m ?? 0))} mm radius · y {fmt(p.y_m)} m</p>)}
        </Section>
        <Section title="Stack checks & source notes">
          {result.checks.map((c,i) => <div key={i}><strong>{c.name} · {c.status.replace("_"," ")}</strong>
            <p>{c.message}</p><small>{c.source.code} · {c.source.location}</small></div>)}
          {result.modeling_notes.map(n => <p key={n}>{n}</p>)}
          {result.sources.map((s,i) => <small key={i}>{s.code} · {s.location} · printed pp. {s.printed_pages.join(", ")}
            {" · "}{s.filename}, PDF pp. {s.pdf_pages.join(", ")}</small>)}
        </Section>
      </> : <div className="inner"><p>Run the trial section to evaluate its bonded interfaces and the top of the subgrade.</p></div>}
    </section>
  </div>;
}
