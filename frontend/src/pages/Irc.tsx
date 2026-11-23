import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
} from "@mui/material";
import Close from "@mui/icons-material/Close";
import FactCheckOutlined from "@mui/icons-material/FactCheckOutlined";
import {
  api,
  fmt,
  type Check,
  type Option,
  type Placement,
  type Preview,
  type Source,
  type Vehicle,
} from "../api/client";
import { palette } from "../theme";
import { Num, Select, Section } from "../components/Controls";

const initial: Placement = {
  case: "dual",
  a: 4.5,
  b: 3.5,
  x_m: 2.25,
  y_m: 1.75,
  group_load_kN: 80,
  wheel_offsets_m: [-0.75, 0.75],
  spacing_m: 1.3,
  tyre_pattern: "L",
  flexural_strength_MPa: null,
  water_cm: null,
};
function Cite({ s }: { s: Source }) {
  return (
    <small className="citation">
      <span>
        <strong>{s.code}</strong> · {s.location}
      </span>
      <span>
        Printed pp. {s.printed_pages.join(", ")} · PDF pp.{" "}
        {s.pdf_pages.join(", ")}
      </span>
    </small>
  );
}
export function Irc({
  drawer,
  close,
  open,
  apply,
}: {
  drawer: boolean;
  close: () => void;
  open: () => void;
  apply: (p: Placement, v: Vehicle, notes: string[]) => void;
}) {
  const [options, setOptions] = useState<Option[]>([]),
    [p, setP] = useState(initial),
    [preview, setPreview] = useState<Preview | null>(null),
    [checks, setChecks] = useState<Check[]>([]),
    [err, setErr] = useState(""),
    [retry, setRetry] = useState(0);
  const [offsets, setOffsets] = useState("-0.75, 0.75");
  const mode = options.find((o) => o.case === p.case)?.mode ?? "flexible";
  useEffect(() => {
    let alive = true;
    api
      .options()
      .then((v) => {
        if (alive) setOptions(v);
      })
      .catch((e) => {
        if (alive) setErr(e.message);
      });
    return () => {
      alive = false;
    };
  }, [retry]);
  useEffect(() => {
    let alive = true;
    if (!options.length) return;
    setErr("");
    setPreview(null);
    setChecks([]);
    const timer = setTimeout(
      () =>
        Promise.all([api.preview(p), api.check(p)])
          .then(([r, c]) => {
            if (alive) {
              setPreview(r);
              setChecks(c);
            }
          })
          .catch((e) => {
            if (alive) setErr(e.message);
          }),
      180,
    );
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [p, options]);
  const update = (v: Partial<Placement>) => {
    setPreview(null);
    setChecks([]);
    setP({ ...p, ...v });
  };
  const number = (
    k:
      | "a"
      | "b"
      | "x_m"
      | "y_m"
      | "group_load_kN"
      | "spacing_m"
      | "water_cm"
      | "flexural_strength_MPa",
    label: string,
  ) => (
    <Num
      label={label}
      value={p[k]}
      set={(n) => update({ [k]: Number.isNaN(n) ? null : n })}
    />
  );
  const scale = Math.min(500 / p.a, 172 / p.b),
    w = p.a * scale,
    h = p.b * scale,
    x0 = (640 - w) / 2,
    y0 = (240 - h) / 2 - 8;
  return (
    <>
      <div className="pageHead">
        <div>
          <h1>IRC Pavement &amp; Bridge</h1>
          <p>Place pavement tyres and bridge loads on the analysis plate</p>
        </div>
        <Button
          variant="outlined"
          startIcon={<FactCheckOutlined />}
          onClick={open}
        >
          IRC Checks &amp; Provenance
        </Button>
      </div>
      {err && (
        <Alert
          severity="error"
          action={<Button onClick={() => setRetry((v) => v + 1)}>Retry</Button>}
        >
          {err}
        </Alert>
      )}
      <div className="workgrid">
        <aside className="card setup">
          <div className="cardHeading">
            <h2>Load placement</h2>
          </div>
          <Section title="Vehicle configuration" open>
            {options.length > 0 && (
              <>
                <Select
                  label="Application"
                  value={mode}
                  items={[
                    ["flexible", "Flexible pavement"],
                    ["rigid", "Rigid pavement"],
                    ["bridge", "Bridge carriageway"],
                  ]}
                  set={(v) => {
                    const c = options.find((o) => o.mode === v)!;
                    update({
                      case: c.case,
                      ...(v === "bridge"
                        ? { a: 24, b: 7, x_m: 1, y_m: 3.5 }
                        : { a: 4.5, b: 3.5, x_m: 0.6, y_m: 1.75 }),
                    });
                  }}
                />
                <Select
                  label="Load case"
                  value={p.case}
                  set={(v) => update({ case: v })}
                  items={options
                    .filter((o) => o.mode === mode)
                    .map((o) => [o.case, o.label])}
                />
              </>
            )}
            {mode === "rigid" && (
              <>
                {number("group_load_kN", "Total group load (kN)")}
                <label>
                  Tyre offsets from centreline (m)
                  <input
                    value={offsets}
                    onChange={(e) => {
                      setOffsets(e.target.value);
                      update({
                        wheel_offsets_m: e.target.value
                          .split(",")
                          .map((v) => (v.trim() ? Number(v) : NaN)),
                      });
                    }}
                  />
                </label>
                {p.case !== "single" && number("spacing_m", "Axle spacing (m)")}
              </>
            )}
            {p.case === "70R_WHEELED" && (
              <Select
                label="Tyre pattern"
                value={p.tyre_pattern}
                set={(v) =>
                  update({ tyre_pattern: v as Placement["tyre_pattern"] })
                }
                items={["L", "M", "N"].map((v) => [v, v])}
              />
            )}
            <div className="two">
              {number("x_m", "Origin x (m)")}
              {number("y_m", "Origin y (m)")}
            </div>
          </Section>
          <Section title="Plate dimensions">
            <div className="two">
              {number("a", "Length (m)")}
              {number("b", "Width (m)")}
            </div>
          </Section>
          {mode === "rigid" && (
            <Section title="PQC check inputs">
              {number(
                "flexural_strength_MPa",
                "28-day flexural strength (MPa)",
              )}
              {number("water_cm", "Free water / cementitious ratio")}
            </Section>
          )}
        </aside>
        <div className="card">
          <div className="cardHeading">
            <h2>Contact footprints</h2>
            <span className="meta">Plan view · metres</span>
          </div>
          {preview ? (
            <>
              <svg
                role="img"
                aria-label="Plate and contact footprints in plan"
                viewBox="0 0 640 240"
                className="plan"
              >
                <defs>
                  <pattern
                    id="planGrid"
                    width="16"
                    height="16"
                    patternUnits="userSpaceOnUse"
                  >
                    <path
                      d="M16 0H0V16"
                      fill="none"
                      stroke={palette.taupe}
                      strokeWidth=".65"
                      strokeOpacity=".55"
                    />
                  </pattern>
                </defs>
                <rect
                  x={x0}
                  y={y0}
                  width={w}
                  height={h}
                  fill="url(#planGrid)"
                  stroke={palette.plum}
                  strokeWidth="1.2"
                />
                {preview.vehicle_load.patches.map((v, i) => {
                  const x = x0 + v.x_m * scale,
                    y = y0 + h - v.y_m * scale;
                  return v.shape === "circle" ? (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r={v.radius_m! * scale}
                      fill={palette.peach}
                      stroke={palette.plum}
                      strokeWidth="1"
                    />
                  ) : (
                    <rect
                      key={i}
                      x={x - (v.length_m! * scale) / 2}
                      y={y - (v.width_m! * scale) / 2}
                      width={v.length_m! * scale}
                      height={v.width_m! * scale}
                      fill={palette.peach}
                      stroke={palette.plum}
                      strokeWidth="1"
                    />
                  );
                })}
                <g fill="none" stroke={palette.plum} strokeWidth="1">
                  <path d={`M${x0} ${y0 + h + 8}v16m0 -8h${w}m0 -8v16`} />
                  <path d={`M${x0 - 8} ${y0}h-16m8 0v${h}m-8 0h16`} />
                </g>
                <g
                  fill={palette.ink}
                  fontFamily="monospace"
                  fontSize="13"
                  textAnchor="middle"
                >
                  <text x={x0 + w / 2} y={y0 + h + 36}>
                    x · {fmt(p.a)} m
                  </text>
                  <text
                    transform={`translate(${x0 - 26} ${y0 + h / 2}) rotate(-90)`}
                  >
                    y · {fmt(p.b)} m
                  </text>
                </g>
              </svg>
              <div className="inner planSummary">
                <div>
                  <h3>{preview.vehicle_load.patches.length} contact patches</h3>
                  <p>
                    {fmt(
                      preview.vehicle_load.patches.reduce(
                        (s, v) => s + v.force_N,
                        0,
                      ) / 1000,
                    )}{" "}
                    kN nominal load ·{" "}
                    {preview.inside_plate
                      ? "Fully on plate"
                      : "Clipped at plate edge"}
                  </p>
                </div>
                <Button
                  variant="contained"
                  onClick={() => apply(p, preview.vehicle_load, preview.notes)}
                >
                  Use in plate solver
                </Button>
                <p className="meta">
                  Transfers plate dimensions and footprints with distributed
                  pressure set to zero
                </p>
              </div>
            </>
          ) : (
            <div className="empty">
              {err ? "Preview unavailable" : <CircularProgress size={24} />}
            </div>
          )}
        </div>
      </div>
      <Drawer anchor="right" open={drawer} onClose={close}>
        <div className="drawer">
          <div className="cardHeading">
            <h2>IRC checks &amp; provenance</h2>
            <IconButton aria-label="Close panel" onClick={close}>
              <Close />
            </IconButton>
          </div>
          {err && <Alert severity="error">{err}</Alert>}
          {!preview && !err && <CircularProgress size={24} />}
          {checks.map((c, i) => (
            <article key={i}>
              <div className="checkHeading">
                <h3>{c.name}</h3>
                <Chip
                  size="small"
                  label={
                    { pass: "Pass", fail: "Fail", needs_input: "Needs input" }[
                      c.status
                    ]
                  }
                  variant="outlined"
                  color={
                    c.status === "pass"
                      ? "success"
                      : c.status === "fail"
                        ? "error"
                        : "warning"
                  }
                />
              </div>
              <p>{c.message}</p>
              <Cite s={c.source} />
            </article>
          ))}
          {preview && (
            <article>
              <h3>Load geometry sources</h3>
              {preview.sources.map((s) => (
                <Cite key={s.location} s={s} />
              ))}
              {preview.notes.map((s) => (
                <p key={s}>{s}</p>
              ))}
            </article>
          )}
        </div>
      </Drawer>
    </>
  );
}
