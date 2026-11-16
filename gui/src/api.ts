import type { BuildJ, DesignInfo, ServerEvent } from "./types";

async function json<T>(r: Response): Promise<T> {
  const body = await r.json().catch(() => ({ error: `${r.status} ${r.statusText}` }));
  if (!r.ok) throw new Error((body as { error?: string }).error ?? `${r.status}`);
  return body as T;
}

export const api = {
  design: () => fetch("/api/design").then((r) => json<DesignInfo>(r)),
  build: (params: Record<string, unknown>) =>
    fetch("/api/build", { method: "POST", headers: { "content-type": "application/json" },
                          body: JSON.stringify({ params }) }).then((r) => json<BuildJ>(r)),
  answer: (assumption_id: string, reading: string) =>
    fetch("/api/answer", { method: "POST", headers: { "content-type": "application/json" },
                           body: JSON.stringify({ assumption_id, reading }) }).then((r) => json<BuildJ>(r)),
  mesh: (id: string) =>
    fetch(`/api/mesh/${id}`).then((r) => {
      if (!r.ok) throw new Error(`mesh ${id}: ${r.status}`);
      return r.arrayBuffer();
    }),
};

/** WebSocket with automatic reconnect.  Returns a function that closes it. */
export function connectEvents(onEvent: (e: ServerEvent) => void, onState: (up: boolean) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let delay = 500;
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/api/events`);
    ws.onopen = () => { delay = 500; onState(true); };
    ws.onmessage = (m) => {
      try { onEvent(JSON.parse(m.data)); } catch { /* ignore malformed */ }
    };
    ws.onclose = () => {
      onState(false);
      if (!closed) setTimeout(open, (delay = Math.min(delay * 2, 8000)));
    };
  };
  open();
  return () => { closed = true; ws?.close(); };
}
