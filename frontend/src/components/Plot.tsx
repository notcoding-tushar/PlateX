import { useMemo } from "react";
import type { Field } from "../api/client";
import { fmt } from "../api/client";
import { palette } from "../theme";

const ramp = [
  palette.cream,
  palette.peach,
  palette.taupe,
  palette.rose,
  palette.plum,
];
const stops = ramp.map((hex) =>
  [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16)),
);

function color(t: number) {
  const v = Math.max(0, Math.min(1, t)) * 4,
    i = Math.min(3, Math.floor(v));
  return (
    "rgb(" +
    stops[i]
      .map((x, k) => Math.round(x + (stops[i + 1][k] - x) * (v - i)))
      .join(",") +
    ")"
  );
}
// Evaluate the eight serendipity nodal values only for rendering the solved field.
function interpolate(w: number[], x: number, y: number) {
  const s = [
    (-(1 - x) * (1 + y) * (1 + x - y)) / 4,
    ((1 - x * x) * (1 + y)) / 2,
    (-(1 + x) * (1 + y) * (1 - x - y)) / 4,
    ((1 + x) * (1 - y * y)) / 2,
    (-(1 + x) * (1 - y) * (1 - x + y)) / 4,
    ((1 - x * x) * (1 - y)) / 2,
    (-(1 - x) * (1 - y) * (1 + x + y)) / 4,
    ((1 - x) * (1 - y * y)) / 2,
  ];
  return s.reduce((sum, n, i) => sum + n * w[i], 0);
}
export function Plot({ field, surface }: { field: Field; surface: boolean }) {
  const drawing = useMemo(() => {
    const a = Math.max(...field.coordinates.map((c) => c[0])),
      b = Math.max(...field.coordinates.map((c) => c[1]));
    const low = Math.min(...field.w_m),
      high = Math.max(...field.w_m),
      span = high - low,
      peak = Math.max(Math.abs(low), Math.abs(high));
    const scale = surface
      ? Math.min(530 / (a * 0.9 + b), 185 / (a * 0.55 + b * 0.24))
      : Math.min(540 / a, 210 / b);
    function project(x: number, y: number, w: number) {
      const X = (x - a / 2) * scale,
        Y = (y - b / 2) * scale;
      return surface
        ? [
            330 + Y + 0.9 * X,
            153 - 0.24 * Y + 0.55 * X + (peak ? (w / peak) * 48 : 0),
          ]
        : [330 + X, 145 - Y];
    }
    const cells: {
      points: string;
      fill: string;
      depth: number;
      outline: string;
    }[] = [];
    for (const el of field.elements) {
      const [x0, y0] = field.coordinates[el[6]],
        [x1, y1] = field.coordinates[el[2]],
        ws = el.map((i) => field.w_m[i]);
      const subdiv = 3;
      for (let j = 0; j < subdiv; j++)
        for (let i = 0; i < subdiv; i++) {
          const corners = [
            [i, j],
            [i + 1, j],
            [i + 1, j + 1],
            [i, j + 1],
          ].map(([ix, iy]) => {
            const u = ix / subdiv,
              v = iy / subdiv,
              w = interpolate(ws, 2 * u - 1, 2 * v - 1);
            return { p: project(x0 + (x1 - x0) * u, y0 + (y1 - y0) * v, w), w };
          });
          const points = corners.map((c) => c.p.join(",")).join(" "),
            shade = span
              ? (corners.reduce((s, c) => s + c.w, 0) / 4 - low) / span
              : 0.5;
          const edge = (k: number) =>
            "M" +
            corners[k].p.join(" ") +
            "L" +
            corners[(k + 1) % 4].p.join(" ");
          cells.push({
            points,
            fill: color(shade),
            depth:
              0.55 * (x0 + ((x1 - x0) * i) / subdiv) -
              0.24 * (y0 + ((y1 - y0) * j) / subdiv),
            outline:
              (i === 0 ? edge(3) : "") +
              (j === 0 ? edge(0) : "") +
              (i === subdiv - 1 ? edge(1) : "") +
              (j === subdiv - 1 ? edge(2) : ""),
          });
        }
    }
    return { cells: cells.sort((u, v) => u.depth - v.depth), high, low };
  }, [field, surface]);
  return (
    <div className="plotArea">
      <svg
        id="deflection-plot"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 660 290"
        role="img"
        aria-label={
          surface
            ? "Deflected plate surface, vertical displacement exaggerated"
            : "Plan contour of transverse deflection"
        }
      >
        <rect width="660" height="290" fill={palette.drawing} />
        {drawing.cells.map((c, i) => (
          <g key={i}>
            <polygon
              points={c.points}
              fill={c.fill}
              stroke={c.fill}
              strokeWidth=".7"
            />
            <path
              d={c.outline}
              fill="none"
              stroke={palette.ink}
              strokeOpacity=".35"
              strokeWidth=".8"
            />
          </g>
        ))}
        <g transform="translate(42 244)" stroke={palette.plum} fill="none">
          <path
            d={surface ? "M0 0l22 -6M0 0l15 10M0 0v-20" : "M0 0h24M0 0v-23"}
          />
        </g>
        <g fill={palette.ink} fontFamily="monospace" fontSize="14">
          <text x="69" y="242">
            {surface ? "y" : "x"}
          </text>
          <text x={surface ? 60 : 39} y={surface ? 268 : 213}>
            {surface ? "x" : "y"}
          </text>
          {surface && (
            <text x="39" y="216">
              z
            </text>
          )}
        </g>
      </svg>
      <div className="legend">
        <span>w (m)</span>
        <span>{fmt(drawing.low)}</span>
        <i
          style={{ background: `linear-gradient(90deg, ${ramp.join(", ")})` }}
        />
        <span>{fmt(drawing.high)}</span>
      </div>
    </div>
  );
}
