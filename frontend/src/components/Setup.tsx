import { useRef } from "react";
import { Button } from "@mui/material";
import type { Config, Layer, Patch } from "../api/client";
import { Section, Select, Num } from "./Controls";

export function Setup({
  c,
  set,
  count,
  setCount,
  travel,
  setTravel,
}: {
  c: Config;
  set: (v: Config) => void;
  count: number;
  setCount: (v: number) => void;
  travel: number;
  setTravel: (v: number) => void;
}) {
  const update = (v: Partial<Config>) => set({ ...c, ...v });
  const num = (
    key: "a" | "b" | "h" | "m" | "n" | "nu" | "q0" | "alpha" | "beta",
    label: string,
  ) => <Num label={label} value={c[key]} set={(v) => update({ [key]: v })} />;
  const layers = c.material_mode === "laminate" ? c.layers : null;
  const custom = Boolean(layers?.length);
  const previousStack = useRef<Pick<Config, "h" | "layers" | "query_points"> | null>(null);
  const setThicknesses = (stack: Layer[], thicknesses: number[]) => {
    const h = thicknesses.reduce((sum, value) => sum + value, 0);
    let z = -h / 2;
    update({ h, query_points: [], layers: stack.map((layer, i) => {
      const bottom = z;
      z += thicknesses[i];
      return { ...layer, h_bottom: bottom, h_top: z };
    }) });
  };
  const resizeStack = (count: number) => {
    if (!layers?.length) return;
    const kept = layers.slice(0, count);
    const last = kept[kept.length - 1];
    const bottom = last.h_bottom;
    const pieces = count - kept.length + 1;
    const step = (c.h / 2 - bottom) / pieces;
    update({ query_points: [], layers: [...kept.slice(0, -1), ...Array.from({length: pieces}, (_, i) =>
      ({ ...last, h_bottom: bottom + i * step, h_top: bottom + (i + 1) * step }))] });
  };
  const patches = c.vehicle_load.patches;
  const setPatches = (list: Patch[]) =>
    update({ vehicle_load: { patches: list } });
  const coeff = (key: "t_coeffs" | "c_coeffs", label: string) => (
    <div className="three">
      {(c[key] ?? [0, 0, 0]).map((v, i) => (
        <Num
          key={i}
          label={label + (i + 1)}
          value={v}
          set={(n) =>
            update({ [key]: (c[key] ?? [0, 0, 0]).map((old, j) => (i === j ? n : old)) })
          }
        />
      ))}
    </div>
  );
  return (
    <aside className="card setup">
      <div className="cardHeading">
        <h2>Model setup</h2>
      </div>
      <Section title="Pavement geometry" open>
        <div className="two">
          {num("a", "Length a (m)")}
          {num("b", "Width b (m)")}
        </div>
        {custom ? <p>Total layer thickness · {Number(c.h.toPrecision(8))} m</p> : num("h", "Section thickness (m)")}
        <div className="two">
          {num("m", "Elements · x")}
          {num("n", "Elements · y")}
        </div>
      </Section>
      <Section title="Pavement layers" open>
        <Select label="Layer configuration" value={custom ? "custom" : c.material_mode}
          items={[["isotropic", "Single isotropic layer"], ["custom", "Custom pavement stack"],
            ["laminate", "Benchmark laminate [0/90/0]"]]}
          set={mode => {
            if (mode !== "custom") {
              if (custom) previousStack.current = { h: c.h, layers, query_points: c.query_points };
              update({ material_mode: mode as Config["material_mode"], layers: null, query_points: [] });
              return;
            }
            if (previousStack.current) {
              update({ material_mode: "laminate", ...previousStack.current });
              return;
            }
            const E = c.E ?? NaN, nu = c.nu ?? NaN, G = E / (2 * (1 + nu));
            update({ material_mode: "laminate", layers: [{ h_bottom: -c.h/2, h_top: c.h/2,
              E1:E, E2:E, E3:E, nu12:nu, nu23:nu, nu13:nu, G12:G, G13:G, G23:G,
              theta_rad:0, alpha1:c.alpha, alpha2:c.alpha, alpha3:0, beta1:c.beta, beta2:c.beta, beta3:0 }] });
          }} />
        {c.material_mode === "isotropic" && (
          <div className="two">
            <Num
              label="E (GPa)"
              value={c.E == null ? null : c.E / 1e9}
              set={(v) => update({ E: v * 1e9 })}
            />
            {num("nu", "Poisson ratio ν")}
          </div>
        )}
        {custom && layers && <>
          <Select label="Number of layers" value={String(layers.length)} set={v => resizeStack(Number(v))}
            items={Array.from({length: Math.max(10, layers.length + 1)}, (_, i) => [String(i+1), String(i+1)])} />
          {!!c.query_points?.length && <p className="meta">Changing the stack geometry clears the imported section’s evaluation points.</p>}
          <p className="meta">Layers run from bottom to top. Increasing the count divides the top layer. Reducing it extends the highest retained material to the surface.</p>
          {layers.map((layer, i) => {
            const field = (key: keyof Layer, label: string, scale = 1) => <Num label={label}
              value={layer[key] / scale} set={v => update({ layers: c.layers!.map((old, j) => j === i ? { ...old, [key]: v * scale } : old) })} />;
            return <div className="patchForm" key={i}>
              <strong>Layer {i + 1} · bottom to top</strong>
              <label>Thickness (m)
                <input type="number" step="any" min="0" required
                  key={String(layer.h_top-layer.h_bottom)}
                  defaultValue={Number((layer.h_top-layer.h_bottom).toPrecision(12))}
                  onBlur={e => {
                    const value = e.currentTarget.valueAsNumber;
                    if (value === Number((layer.h_top-layer.h_bottom).toPrecision(12))) return;
                    if (Number.isFinite(value) && value > 0)
                      setThicknesses(layers, layers.map((l, j) => i === j ? value : l.h_top-l.h_bottom));
                    else e.currentTarget.value = String(layer.h_top-layer.h_bottom);
                  }} />
              </label>
              <div className="two">{field("E1", "E₁ (GPa)", 1e9)}{field("E2", "E₂ (GPa)", 1e9)}</div>
              <details><summary>Out-of-plane material properties</summary>
                <p className="meta">These properties are recorded for completeness under plane stress.</p>
                {field("E3", "E₃ (GPa)", 1e9)}{field("nu23", "ν₂₃")}{field("nu13", "ν₁₃")}
              </details>
              <div className="two">{field("nu12", "ν₁₂")}{field("theta_rad", "Orientation (rad)")}</div>
              <div className="three">{field("G12", "G₁₂ (GPa)", 1e9)}{field("G13", "G₁₃ (GPa)", 1e9)}{field("G23", "G₂₃ (GPa)", 1e9)}</div>
              <div className="two">{field("alpha1", "α₁ (1/K)")}{field("alpha2", "α₂ (1/K)")}</div>
              <div className="two">{field("beta1", "β₁")}{field("beta2", "β₂")}</div>
            </div>;
          })}
        </>}
      </Section>
      <Section title="Edge supports">
        <Select label="Boundary conditions" value={String(c.choicebc)}
          set={v => update({ choicebc: Number(v) })}
          items={[
            ["1", "SSSS · All edges simply supported"], ["2", "CCCC · All edges clamped"],
            ["3", "SFSF · Left/right simply supported, top/bottom free"],
            ["4", "FSFS · Left/right free, top/bottom simply supported"],
            ["5", "SCSC · Left/right simply supported, top/bottom clamped"],
            ["6", "CSCS · Left/right clamped, top/bottom simply supported"],
          ]} />
        <p className="meta">Left and right are x = 0 and a. Bottom and top are y = 0 and b.</p>
      </Section>
      <Section title="Mechanical pressure">
        <Select
          label="Distribution"
          value={c.load_case}
          set={(v) => update({ load_case: v as Config["load_case"] })}
          items={[
            ["sinusoidal", "Sinusoidal"],
            ["uniform", "Uniform"],
          ]}
        />
        {num("q0", "Pressure q₀ (Pa)")}
      </Section>
      <Section title="Thermal & moisture">
        <p className="meta">Enter the mean temperature change and the difference between the top and bottom of the section.</p>
        <Select
          label="In-plane distribution"
          value={c.thermal_distribution}
          set={(v) =>
            update({
              thermal_distribution: v as Config["thermal_distribution"],
            })
          }
          items={[
            ["sinusoidal", "Sinusoidal"],
            ["uniform", "Uniform"],
          ]}
        />
        {c.material_mode === "isotropic" && (
          <div className="two">
            {num("alpha", "Thermal α (1/K)")}
            {num("beta", "Moisture β")}
          </div>
        )}
        <div className="two">
          <Num label="Mean temperature change (K)" value={c.t_coeffs?.[0] ?? 0}
            set={v => update({t_coeffs: [v, c.t_coeffs?.[1] ?? 0, c.t_coeffs?.[2] ?? 0]})} />
          <Num label="Top − bottom temperature (K)" value={c.t_coeffs?.[1] ?? 0}
            set={v => update({t_coeffs: [c.t_coeffs?.[0] ?? 0, v, c.t_coeffs?.[2] ?? 0]})} />
        </div>
        <details><summary>Advanced thermal and moisture profile</summary>
          <p className="meta">T(z) = T1 + (z/h) T2 + sin(πz/h) T3 / π. Moisture uses the same profile.</p>
          {coeff("t_coeffs", "T")}
          {coeff("c_coeffs", "C")}
        </details>
      </Section>
      <Section title="Elastic foundation">
        <Select
          label="Parameter units"
          value={c.foundation.K0 != null || c.foundation.J0 != null ? "scaled" : "si"}
          set={(v) =>
            update({
              foundation: v === "scaled" ? { K0: 0, J0: 0 } : { Kw: 0, Kp: 0 },
            })
          }
          items={[
            ["si", "Dimensional"],
            ["scaled", "Dimensionless"],
          ]}
        />
        <div className="two">
          {(
            (c.foundation.K0 != null || c.foundation.J0 != null ? ["K0", "J0"] : ["Kw", "Kp"]) as Array<
              keyof Config["foundation"]
            >
          ).map((k) => (
            <Num
              key={k}
              label={k === "Kw" ? "Kw (N/m³)" : k === "Kp" ? "Kp (N/m)" : k}
              value={c.foundation[k] ?? 0}
              set={(v) => update({ foundation: { ...c.foundation, [k]: v } })}
            />
          ))}
        </div>
        {c.foundation.K0 == null && c.foundation.J0 == null && <Num label="Kp y (N/m, blank uses Kp)" value={c.foundation.Kp_y ?? null} set={v => update({ foundation: { ...c.foundation, Kp_y: Number.isNaN(v) ? null : v } })} />}
        <p className="meta">Kw is Winkler stiffness; Kp and Kp y are shear-layer stiffnesses. Blank Kp y uses Kp. Dimensionless coefficients override dimensional values.</p>
      </Section>
      <Section title="Traffic, vehicle & patch loads">
        {patches.map((p, i) => {
          const put = (v: Patch) =>
            setPatches(patches.map((old, j) => (j === i ? v : old)));
          const field = (
            k: "x_m" | "y_m" | "length_m" | "width_m" | "radius_m" | "force_N",
            label: string,
          ) => (
            <Num
              label={label}
              value={p[k] ?? 0}
              set={(v) => put({ ...p, [k]: v })}
            />
          );
          return (
            <div className="patchForm" key={i}>
              <Select
                label={"Patch " + (i + 1)}
                value={p.shape}
                set={(v) =>
                  put({
                    x_m: p.x_m,
                    y_m: p.y_m,
                    force_N: p.force_N,
                    ...(v === "circle"
                      ? { shape: "circle", radius_m: 0.1 }
                      : { shape: "rectangle", width_m: 0.2, length_m: 0.2 }),
                  })
                }
                items={[
                  ["circle", "Circular"],
                  ["rectangle", "Rectangular"],
                ]}
              />
              <div className="two">
                {field("x_m", "x (m)")}
                {field("y_m", "y (m)")}
              </div>
              {field("force_N", "Force (N)")}
              {p.shape === "circle" ? (
                field("radius_m", "Radius (m)")
              ) : (
                <div className="two">
                  {field("length_m", "Length (m)")}
                  {field("width_m", "Width (m)")}
                </div>
              )}
              <Button
                onClick={() => setPatches(patches.filter((_, j) => i !== j))}
              >
                Remove patch
              </Button>
            </div>
          );
        })}
        <Button
          variant="outlined"
          onClick={() =>
            setPatches([
              ...patches,
              {
                shape: "circle",
                radius_m: 0.1,
                x_m: c.a / 2,
                y_m: c.b / 2,
                force_N: 1000,
              },
            ])
          }
        >
          Add contact patch
        </Button>
        {patches.length > 0 && (
          <>
            <Num
              label="Sweep positions"
              value={count}
              set={setCount}
              min={1}
              step={1}
            />
            {count > 1 && (
              <Num label="Total x travel (m)" value={travel} set={setTravel} />
            )}
          </>
        )}
      </Section>
    </aside>
  );
}
