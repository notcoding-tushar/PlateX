import { useMemo, useRef, useState } from "react";
import { Button, ToggleButton, ToggleButtonGroup } from "@mui/material";
import type { Field } from "../api/client";
import { fmt } from "../api/client";
import { palette } from "../theme";

const ramp = ["#e9f0f0", "#b5d1d6", "#78abbc", "#487e9a", "#234a65"];
const initialView = { yaw: -1.02, pitch: 0.49, x: 0, y: 0 };
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
  const [view, setView] = useState(initialView), [mode, setMode] = useState("rotate");
  const pointer = useRef<{id: number; x: number; y: number} | null>(null);
  const { yaw, pitch } = view;
  function move(dx: number, dy: number, pan: boolean) {
    setView(v => pan ? { ...v, x: v.x+dx, y: v.y+dy } : { ...v,
      yaw: v.yaw+dx*.008, pitch: Math.max(-1.5, Math.min(1.5, v.pitch+dy*.008)) });
  }
  const drawing = useMemo(() => {
    const a = Math.max(...field.coordinates.map((c) => c[0])),
      b = Math.max(...field.coordinates.map((c) => c[1]));
    const low = Math.min(...field.w_m),
      high = Math.max(...field.w_m),
      span = high - low,
      peak = Math.max(Math.abs(low), Math.abs(high));
    const cos = Math.cos(yaw), sin = Math.sin(yaw), tilt = Math.sin(pitch);
    const scale = surface ? Math.min(530/(a*Math.abs(cos)+b*Math.abs(sin)),
      185/Math.max(1e-9, Math.abs(tilt)*(a*Math.abs(sin)+b*Math.abs(cos)))) : Math.min(540/a, 210/b);
    function project(x: number, y: number, w: number) {
      const X = (x - a / 2) * scale,
        Y = (y - b / 2) * scale;
      return surface
        ? [
            330 + X*cos - Y*sin,
            145 - (X*sin + Y*cos)*tilt + (peak ? w/peak*48*Math.cos(pitch) : 0),
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
            depth: -scale*Math.cos(pitch)*(sin*(x0+(x1-x0)*(i+.5)/subdiv)
              + cos*(y0+(y1-y0)*(j+.5)/subdiv))
              - (peak ? corners.reduce((sum,c) => sum+c.w, 0)/(4*peak)*48*tilt : 0),
            outline:
              (i === 0 ? edge(3) : "") +
              (j === 0 ? edge(0) : "") +
              (i === subdiv - 1 ? edge(1) : "") +
              (j === subdiv - 1 ? edge(2) : ""),
          });
        }
    }
    return { cells: cells.sort((u, v) => u.depth - v.depth), high, low };
  }, [field, surface, yaw, pitch]);
  const pan = !surface || mode === "pan";
  const axes = surface ? [["x", Math.cos(yaw), -Math.sin(yaw)*Math.sin(pitch)],
    ["y", -Math.sin(yaw), -Math.cos(yaw)*Math.sin(pitch)], ["z", 0, -Math.cos(pitch)]] as const
    : [["x", 1, 0], ["y", 0, -1]] as const;
  return (
    <div className="plotArea">
      <div className="plotTools">
        {surface && <ToggleButtonGroup size="small" exclusive value={mode} aria-label="Drag action"
          onChange={(_, v) => { if (v) setMode(v); }}>
          <ToggleButton value="rotate">Rotate</ToggleButton><ToggleButton value="pan">Pan</ToggleButton>
        </ToggleButtonGroup>}
        <span className="meta">{pan ? "Drag to pan" : "Drag to rotate"}</span>
        <Button size="small" onClick={() => setView(initialView)}>Reset view</Button>
      </div>
      <svg
        id="deflection-plot"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 660 290"
        role="img"
        tabIndex={0}
        aria-description="Drag or use the arrow keys. Hold Shift to pan. Home resets the view."
        onPointerDown={e => {
          if (e.button !== 0 || pointer.current) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          pointer.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
        }}
        onPointerMove={e => {
          const last = pointer.current, matrix = e.currentTarget.getScreenCTM();
          if (last?.id !== e.pointerId || !matrix) return;
          move((e.clientX-last.x)/matrix.a, (e.clientY-last.y)/matrix.d, pan || e.shiftKey);
          pointer.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
        }}
        onLostPointerCapture={() => { pointer.current = null; }}
        onKeyDown={e => {
          const dx = Number(e.key === "ArrowRight") - Number(e.key === "ArrowLeft");
          const dy = Number(e.key === "ArrowDown") - Number(e.key === "ArrowUp");
          if (dx || dy) { e.preventDefault(); move(dx*12, dy*12, pan || e.shiftKey); }
          if (e.key === "Home") { e.preventDefault(); setView(initialView); }
        }}
        aria-label={
          surface
            ? "Deflected plate surface, vertical displacement exaggerated"
            : "Plan contour of transverse deflection"
        }
      >
        <rect width="660" height="290" fill={palette.drawing} />
        <g transform={`translate(${view.x} ${view.y})`}>{drawing.cells.map((c, i) => (
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
        ))}</g>
        <g transform="translate(46 246)" fill={palette.ink} textAnchor="middle" fontSize="12">
          {axes.map(([name, x, y]) => <g key={name}><line x2={22*x} y2={22*y} stroke={palette.ink}/>
            <text x={32*x} y={32*y+4}>{name}</text></g>)}</g>
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
