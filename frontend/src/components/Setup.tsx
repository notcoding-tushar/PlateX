import { Button } from "@mui/material";
import Tune from "@mui/icons-material/Tune";
import type { Config, Patch } from "../api/client";
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
      {c[key].map((v, i) => (
        <Num
          key={i}
          label={label + (i + 1)}
          value={v}
          set={(n) =>
            update({ [key]: c[key].map((old, j) => (i === j ? n : old)) })
          }
        />
      ))}
    </div>
  );
  return (
    <aside className="card setup">
      <div className="cardHeading">
        <Tune />
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
              value={c.E / 1e9}
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
          value={"K0" in c.foundation ? "scaled" : "si"}
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
            ("K0" in c.foundation ? ["K0", "J0"] : ["Kw", "Kp"]) as Array<
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
      </Section>
      <Section title="Vehicle & patch loads">
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
