import { componentRequest } from "./streamlit";

export async function request<T>(path: string, body?: unknown): Promise<T> {
  if (import.meta.env.MODE === "streamlit") return componentRequest<T>(path, body);
  let res: Response;
  try {
    res = await fetch(
    (import.meta.env.VITE_API_BASE_URL ?? "") + "/api/" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  } catch {
    throw new Error("Cannot reach the analysis service. Check the connection and retry.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const d = data.detail;
    throw new Error(
      Array.isArray(d)
        ? d.map((x) => x.loc.slice(1).join(".") + " " + x.msg).join("; ")
        : d || "Request failed (" + res.status + ")",
    );
  }
  try {
    return await res.json();
  } catch {
    throw new Error("The analysis service returned an invalid response.");
  }
}
