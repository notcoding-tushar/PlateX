export interface Patch {
  shape: "rectangle" | "circle";
  x_m: number;
  y_m: number;
  force_N: number;
  radius_m?: number | null;
  length_m?: number | null;
  width_m?: number | null;
  label?: string;
}
export interface Vehicle {
  patches: Patch[];
}
export interface Layer {
  h_bottom: number; h_top: number;
  E1: number; E2: number; E3: number;
  nu12: number; nu23: number; nu13: number;
  G12: number; G13: number; G23: number;
  theta_rad: number;
  alpha1: number; alpha2: number; alpha3: number;
  beta1: number; beta2: number; beta3: number;
}
export interface Config {
  a: number;
  b: number;
  h: number;
  m: number;
  n: number;
  E: number | null;
  nu: number | null;
  material_mode: "isotropic" | "laminate";
  choicebc: number;
  load_case: "sinusoidal" | "uniform";
  q0: number;
  alpha: number;
  beta: number;
  thermal_distribution: "sinusoidal" | "uniform";
  t_coeffs: number[] | null;
  c_coeffs: number[] | null;
  foundation: Partial<Record<"K0" | "J0" | "Kw" | "Kp" | "Kp_y", number | null>>;
  vehicle_load: Vehicle;
  layers?: Layer[] | null;
  query_points?: unknown[];
}
export const initial: Config = {
  a: 1,
  b: 3,
  h: 0.1,
  m: 10,
  n: 10,
  E: 117e9,
  nu: 1 / 3,
  material_mode: "isotropic",
  choicebc: 1,
  load_case: "sinusoidal",
  q0: 100,
  alpha: 0,
  beta: 0,
  t_coeffs: [0, 0, 0],
  c_coeffs: [0, 0, 0],
  thermal_distribution: "sinusoidal",
  foundation: {},
  vehicle_load: { patches: [] },
};
export const metrics = {
  w_center_m: ["Centre deflection", "m"],
  max_abs_deflection_m: ["Peak |w|", "m"],
  sigma_x_pa: ["Normal stress σx", "Pa"],
  tau_xy_pa: ["In-plane shear τxy", "Pa"],
  tau_xz_pa: ["Transverse shear τxz", "Pa"],
  w_bar: ["Deflection w̄", ""],
  sigma_x_bar: ["Normal stress σ̄x", ""],
  tau_xy_bar: ["In-plane shear τ̄xy", ""],
  tau_xz_bar: ["Transverse shear τ̄xz", ""],
} as const;
export type Metric = keyof typeof metrics;
export interface Field {
  coordinates: [number, number][];
  elements: number[][];
  w_m: number[];
}
export type Result = Record<Metric, number | null> & {
  mesh: string;
  nodes: number;
  elements: number;
  free_dofs: number;
  ndof: number;
  time_s: number;
  field: Field;
  solver_warnings: string[];
  stiffness_info: {
    nnz: number;
    global_shape: [number, number];
    max_asymmetry: number;
    density_pct: number;
    Db_top_left_4x4: number[][];
    Ds_top_left_2x2: number[][];
  };
};
export interface Option {
  case: string;
  label: string;
  mode: "flexible" | "rigid" | "bridge";
}
export interface Placement {
  case: string;
  a: number;
  b: number;
  x_m: number;
  y_m: number;
  group_load_kN: number;
  wheel_offsets_m: number[];
  spacing_m: number;
  tyre_pattern: "L" | "M" | "N";
  aa_wheel_offsets_y_mm?: number[] | null;
  flexural_strength_MPa: number | null;
  water_cm: number | null;
}
export interface Source {
  code: string;
  location: string;
  printed_pages: number[];
  pdf_pages: number[];
  filename: string;
}
export interface Preview {
  vehicle_load: Vehicle;
  sources: Source[];
  notes: string[];
  inside_plate: boolean;
}
export interface ClimateOptions {
  zones: { zone: string; region: string }[];
  source: Source;
  notes: string[];
}
export interface Check {
  name: string;
  status: "pass" | "fail" | "needs_input";
  message: string;
  source: Source;
}
export type Benchmark = {
  computed: Record<string, number>;
  reference: Record<string, number>;
};
async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(
    (import.meta.env.VITE_API_BASE_URL ?? "") + "/api/" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const d = data.detail;
    throw new Error(
      Array.isArray(d)
        ? d.map((x) => x.loc.slice(1).join(".") + " " + x.msg).join("; ")
        : d || "Request failed (" + res.status + ")",
    );
  }
  return res.json();
}
export const api = {
  solve: (c: Config) => request<Result>("solve", c),
  sweep: (c: Config, loads: Vehicle[]) =>
    request<Result[]>("solve-sweep", { base_config: c, load_cases: loads }),
  options: () => request<Option[]>("irc/options"),
  climateOptions: () => request<ClimateOptions>("irc/climate-options"),
  climateTemperature: (zone: string, thickness_m: number, period: string, interpolate: boolean) =>
    request<{ delta_T_K: number; notes: string[]; source: Source }>("irc/climate-temperature", { zone, thickness_m, period, interpolate }),
  preview: (v: Placement) => request<Preview>("irc/preview-loads", v),
  check: (v: Placement) => request<Check[]>("irc/check", v),
  prepare: (mode: "rigid" | "flexible", body: unknown) =>
    request<{ config: Config; modeling_notes: string[]; sources: Source[]; details: unknown }>("irc/" + mode, body),
  compliance: (kind: string, args: unknown) => request<{ checks: Check[]; options: Record<string, number>[]; sources: Source[] }>("irc/compliance", { kind, arguments: args }),
  benchmark: (thermal: boolean) =>
    request<Benchmark>("validation?hygrothermal=" + thermal),
};
export const fmt = (value: number | null | undefined) =>
  value == null
    ? "—"
    : value === 0
      ? "0"
      : Math.abs(value) < 0.001 || Math.abs(value) >= 1e5
        ? value.toExponential(3)
        : Number(value.toPrecision(5)).toString();
