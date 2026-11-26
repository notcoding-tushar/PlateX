import { useState } from "react";
import {
  Alert,
  AppBar,
  Button,
  Tab,
  Tabs,
  Toolbar,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import Layers from "@mui/icons-material/Layers";
import PlayArrowRounded from "@mui/icons-material/PlayArrowRounded";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import {
  fmt,
  metrics,
  type Metric,
} from "./api/client";
import { Plot } from "./components/Plot";
import { Setup } from "./components/Setup";
import { Section, Select, download } from "./components/Controls";
import { Irc } from "./pages/Irc";
import { Validation } from "./pages/Validation";
import { Landing } from "./pages/Landing";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { usePavementAnalysis } from "./state/usePavementAnalysis";

const keys = Object.keys(metrics) as Metric[];
export default function App() {
  const [tab, setTab] = useState(-1),
    [visited, setVisited] = useState(false),
    [drawer, setDrawer] = useState(false);
  const { c, set, results, index, select, busy, error, surface, setSurface, count,
    setCount, travel, setTravel, notes, setNotes, r, positions, dirty, run } = usePavementAnalysis();
  const csv = () => {
    if (!r) return;
    const rows = [
      "quantity,value,unit",
      ...keys.map((k) => [k, r[k] ?? "", metrics[k][1]].join(",")),
      "",
      "node,x_m,y_m,w_m",
      ...r.field.coordinates.map(([x, y], i) =>
        [i + 1, x, y, r.field.w_m[i]].join(","),
      ),
    ];
    download(
      "platex-position-" + (index + 1) + ".csv",
      rows.join("\r\n"),
      "text/csv;charset=utf-8",
    );
  };
  const exportPlot = () => {
    const el = document.getElementById("deflection-plot");
    if (el && r) {
      const svg = el.cloneNode(true) as SVGElement;
      const title = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "title",
      );
      title.textContent =
        "Transverse deflection (m), " +
        fmt(Math.min(...r.field.w_m)) +
        " to " +
        fmt(Math.max(...r.field.w_m));
      svg.prepend(title);
      download(
        "platex-deflection.svg",
        new XMLSerializer().serializeToString(svg),
        "image/svg+xml",
      );
    }
  };
  return (
    <>
      <AppBar position="static" className="topbar">
        <Toolbar className="toolbar">
          <div className="brand">
            <span>
              <Layers />
            </span>
            PlateX
          </div>
          <Tabs
            value={tab}
            textColor="inherit"
            onChange={(_, v) => {
              setTab(v);
              if (v === 1) setVisited(true);
            }}
            variant="scrollable"
            scrollButtons="auto"
            aria-label="Workbench navigation"
          >
            <Tab value={-1} label="Overview" />
            {[
              "Pavement Layer Solver",
              "IRC Pavement & Bridge",
              "Matrix & Validation",
            ].map((n) => (
              <Tab key={n} value={["Pavement Layer Solver", "IRC Pavement & Bridge", "Matrix & Validation"].indexOf(n)} label={n} />
            ))}
          </Tabs>
          {tab !== 1 && tab !== -1 && <div className="engine" title={r?.engine}>HOSNT12 Q8</div>}
        </Toolbar>
      </AppBar>
      <main>
        {tab === -1 && <Landing result={r ?? null} openSolver={() => setTab(0)}
          openIrc={() => { setVisited(true); setTab(1); }} openValidation={() => setTab(2)} />}
        {tab === 0 && (
          <>
            <div className="pageHead">
              <div>
                <h1>Pavement layer solver</h1>
              </div>
              <Button
                variant="contained"
                size="large"
                startIcon={<PlayArrowRounded />}
                disabled={busy}
                onClick={run}
              >
                {busy
                  ? "Solving…"
                  : positions > 1
                    ? "Run sweep"
                    : "Run analysis"}
              </Button>
            </div>
            {error && <Alert severity="error" role="alert">{error}</Alert>}
            {notes.map((n) => (
              <Alert key={n} severity="info">
                {n}
              </Alert>
            ))}
            <div className="workgrid">
              <Setup
                c={c}
                set={set}
                count={count}
                setCount={setCount}
                travel={travel}
                setTravel={setTravel}
              />
              <div className="output">
                <section className="card">
                  <div className="cardHeading">
                    <h2>Deflection field</h2>
                    <ToggleButtonGroup
                      exclusive
                      size="small"
                      value={surface ? "surface" : "contour"}
                      onChange={(_, v) => {
                        if (v) setSurface(v === "surface");
                      }}
                      aria-label="Deflection view"
                    >
                      <ToggleButton value="surface">Surface</ToggleButton>
                      <ToggleButton value="contour">Contour</ToggleButton>
                    </ToggleButtonGroup>
                  </div>
                  {r ? (
                    <Plot field={r.field} surface={surface} />
                  ) : (
                    <div className="empty" role="status">
                      {busy
                        ? "Computing nodal displacements…"
                        : "Run an analysis to plot deflection."}
                    </div>
                  )}
                  <div className="plotFoot" role="status">
                    <span>
                      {busy
                        ? "Computing"
                        : dirty
                          ? "Inputs changed · showing last solve"
                          : r
                            ? "Solved field"
                            : "Awaiting solve"}
                    </span>
                    <span>
                      {r
                        ? r.mesh.replace("x", " × ") +
                          " Q8 mesh · " +
                          r.nodes +
                          " nodes"
                        : ""}
                      {r && surface ? " · z exaggerated" : ""}
                    </span>
                  </div>
                </section>
                {results.length > 1 && (
                  <Select
                    label="Sweep result"
                    value={String(index)}
                    set={(v) => select(Number(v))}
                    items={results.map((_, i) => [
                      String(i),
                      "Position " + (i + 1) + " / " + results.length,
                    ])}
                  />
                )}
                <section className="card response">
                  <div className="cardHeading">
                    <h2>Response summary</h2>
                    <span className="meta">SI units</span>
                  </div>
                  <div className="metrics">
                    {(
                      ["w_center_m", "sigma_x_pa", "tau_xz_pa"] as Metric[]
                    ).map((k) => (
                      <div key={k}>
                        <span>{metrics[k][0]}</span>
                        <strong>
                          {fmt(r?.[k])} <small>{metrics[k][1]}</small>
                        </strong>
                      </div>
                    ))}
                  </div>
                  <Section title="All result quantities">
                    <dl>
                      {keys.map((k) => (
                        <div className="dlrow" key={k}>
                          <dt>{metrics[k][0]}</dt>
                          <dd>
                            {fmt(r?.[k])} {metrics[k][1]}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </Section>
                  <Section title="Plot & CSV export">
                    <div className="buttons">
                      <Button
                        disabled={!r}
                        onClick={csv}
                        startIcon={<DownloadOutlined />}
                      >
                        Download CSV
                      </Button>
                      <Button disabled={!r} onClick={exportPlot}>
                        Save plot (SVG)
                      </Button>
                    </div>
                  </Section>
                </section>
                {r?.solver_warnings.map((w, i) => (
                  <Alert key={i} severity="warning">
                    {w}
                  </Alert>
                ))}
              </div>
            </div>
          </>
        )}
        {visited && (
          <div hidden={tab !== 1}>
            <Irc
              config={c}
              applyConfig={(config, info) => { set(config); setNotes(info); setTab(0); }}
              drawer={drawer}
              close={() => setDrawer(false)}
              open={() => setDrawer(true)}
              apply={(p, v, info) => {
                set({ ...c, a: p.a, b: p.b, vehicle_load: v, q0: 0 });
                setCount(1);
                setNotes(info);
                setTab(0);
              }}
            />
          </div>
        )}
        {tab === 2 && <ErrorBoundary><Validation result={r ?? null} stale={dirty} /></ErrorBoundary>}
      </main>
    </>
  );
}
