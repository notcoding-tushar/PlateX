import { Alert, Button } from "@mui/material";
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
      <Section title="Plate geometry" open>
        <div className="two">
          {num("a", "Length a (m)")}
          {num("b", "Width b (m)")}
        </div>
        {num("h", "Thickness h (m)")}
        <div className="two">
          {num("m", "Elements · x")}
          {num("n", "Elements · y")}
        </div>
      </Section>
      <Section title="Material & supports">
        <Select
          label="Material"
          value={c.material_mode}
          set={(v) => update({ material_mode: v as Config["material_mode"] })}
          items={[
            ["isotropic", "Isotropic"],
            ["laminate", "Preset [0/90/0] laminate"],
          ]}
        />
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
        <Select
          label="Boundary conditions"
          value={String(c.choicebc)}
          set={(v) => update({ choicebc: Number(v) })}
          items={["SSSS", "CCCC", "SFSF", "FSFS", "SCSC", "CSCS"].map(
            (s, i) => [String(i + 1), s],
          )}
        />
      </Section>
      {c.material_mode === "laminate" && <Section title="Pavement layers" open>
        <p className="meta">Layers use z coordinates in metres from the plate mid-plane. They must form a continuous stack from −h/2 to +h/2. Interfaces are bonded.</p>
        {!c.layers?.length ? <Alert severity="info">The [0/90/0] benchmark preset is active. Prepare an IRC flexible model to inspect its pavement stack, or create a layer from the isotropic material values.</Alert> :
          c.layers.map((layer, i) => {
            const field = (key: keyof Layer, label: string, scale = 1) => <Num label={label}
              value={layer[key] / scale} set={v => update({ layers: c.layers!.map((old, j) => j === i ? { ...old, [key]: v * scale } : old) })} />;
            return <div className="patchForm" key={i}>
              <strong>Layer {i + 1} · bottom to top</strong>
              <div className="two">{field("h_bottom", "Bottom z (m)")}{field("h_top", "Top z (m)")}</div>
              <div className="two">{field("E1", "E₁ (GPa)", 1e9)}{field("E2", "E₂ (GPa)", 1e9)}</div>
              <div className="two">{field("nu12", "ν₁₂")}{field("theta_rad", "Orientation (rad)")}</div>
              <div className="three">{field("G12", "G₁₂ (GPa)", 1e9)}{field("G13", "G₁₃ (GPa)", 1e9)}{field("G23", "G₂₃ (GPa)", 1e9)}</div>
              <div className="two">{field("alpha1", "α₁ (1/K)")}{field("alpha2", "α₂ (1/K)")}</div>
              <div className="two">{field("beta1", "β₁")}{field("beta2", "β₂")}</div>
            </div>;
          })}
        {c.layers?.length ? <Button onClick={() => {
          const layers = [...c.layers!], last = layers[layers.length - 1], mid = (last.h_top + last.h_bottom) / 2;
          layers.splice(layers.length - 1, 1, { ...last, h_top: mid }, { ...last, h_bottom: mid });
          update({ layers });
        }}>Split top layer</Button> : <Button disabled={c.E == null || c.nu == null} onClick={() => {
          const E = c.E!, nu = c.nu!, G = E / (2 * (1 + nu));
          update({ layers: [{ h_bottom: -c.h/2, h_top: c.h/2, E1:E, E2:E, E3:E,
            nu12:nu, nu23:nu, nu13:nu, G12:G, G13:G, G23:G, theta_rad:0,
            alpha1:c.alpha, alpha2:c.alpha, alpha3:0, beta1:c.beta, beta2:c.beta, beta3:0 }] });
        }}>Create layer from current isotropic material</Button>}
      </Section>}
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
        <p className="meta">T(z) = T1 + (z/h) T2 + sin(πz/h) T3 / π. T2 is the linear top-to-bottom difference (K); T1 is the mean component. Moisture uses the same profile.</p>
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
        {coeff("t_coeffs", "T")}
        {coeff("c_coeffs", "C")}
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
