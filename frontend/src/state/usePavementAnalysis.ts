import { useEffect, useState } from "react";
import { api, initial, type Config, type Result } from "../api/client";

export function usePavementAnalysis() {
  const [c, set] = useState<Config>(initial),
    [results, setResults] = useState<Result[]>([]),
    [index, select] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [surface, setSurface] = useState(true),
    [count, setCount] = useState(1),
    [travel, setTravel] = useState(0.3),
    [snapshot, setSnapshot] = useState(""),
    [notes, setNotes] = useState<string[]>([]);
  const r = results[index],
    positions = c.vehicle_load.patches.length ? count : 1;
  const signature = JSON.stringify([c, positions, positions > 1 ? travel : 0]);
  const dirty = Boolean(r) && snapshot !== signature;
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      if (!Number.isInteger(positions) || positions < 1)
        throw new Error("Sweep positions must be a positive integer.");
      if (positions > 1 && !Number.isFinite(travel))
        throw new Error("Enter total travel in metres.");
      const loaded =
        positions === 1
          ? [await api.solve(c)]
          : await api.sweep(
              c,
              Array.from({ length: positions }, (_, i) => ({
                patches: c.vehicle_load.patches.map((p) => ({
                  ...p,
                  x_m: p.x_m + (travel * i) / (positions - 1),
                })),
              })),
            );
      setResults(loaded);
      select(0);
      setSnapshot(signature);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void run();
  }, []);
  return { c, set, results, index, select, busy, error, surface, setSurface, count,
    setCount, travel, setTravel, notes, setNotes, r, positions, dirty, run };
}
