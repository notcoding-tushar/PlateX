// A Streamlit component reruns Python for each submitted value. Serialize requests
// so parallel previews and checks each receive their own matching reply.
const send = (type: string, fields: Record<string, unknown>) =>
  window.parent.postMessage({ isStreamlitMessage: true, type, ...fields }, "*");

let tail = Promise.resolve();
let nextId = 0;
let receive: ((reply: Reply) => void) | undefined;
type Reply = { id: string; result?: unknown; error?: string };

export function componentRequest<T>(path: string, body?: unknown): Promise<T> {
  const pending = tail.then(() => new Promise<T>((resolve, reject) => {
    const id = `${Date.now()}-${++nextId}`;
    const timeout = window.setTimeout(() => {
      receive = undefined;
      reject(new Error("The analysis did not respond within five minutes. Please retry."));
    }, 300_000);
    receive = reply => {
      if (reply.id !== id) return;
      receive = undefined;
      window.clearTimeout(timeout);
      if (reply.error) reject(new Error(reply.error));
      else resolve(reply.result as T);
    };
    send("streamlit:setComponentValue", { dataType: "json", value: { id, path, body } });
  }));
  tail = pending.then(() => undefined, () => undefined);
  return pending;
}

export function initializeComponent(mount: () => void) {
  let mounted = false;
  window.addEventListener("message", event => {
    if (event.source !== window.parent || event.data?.type !== "streamlit:render") return;
    if (!mounted) {
      mounted = true;
      mount();
      const root = document.getElementById("root")!;
      new ResizeObserver(() => send("streamlit:setFrameHeight", {
        height: Math.max(550, Math.ceil(root.getBoundingClientRect().height) + 2),
      })).observe(root);
    }
    const reply = event.data.args?.reply;
    if (reply?.id) receive?.(reply);
  });
  send("streamlit:componentReady", { apiVersion: 1 });
}
