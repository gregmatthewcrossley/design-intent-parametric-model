import type { BuildJ, DesignInfo, IntentInfo, IntentOp, ProposalJ, RequestJ, ServerEvent } from "./types";

/** A non-2xx response with its JSON body (409 conflicts carry the current state). */
export class HttpError extends Error {
  constructor(public status: number, public body: Record<string, unknown>) {
    super(String(body.error ?? status));
  }
}

async function call<T>(url: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(url, body === undefined ? { method } :
    { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({ error: `${r.status} ${r.statusText}` }));
  if (!r.ok) throw new HttpError(r.status, j as Record<string, unknown>);
  return j as T;
}

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
  intent: () => call<IntentInfo>("/api/intent"),
  patchIntent: (base_hash: string | null, ops: IntentOp[]) =>
    call<{ intent: IntentInfo; build: BuildJ | null; results: unknown[] }>("/api/intent", "PATCH", { base_hash, ops }),
  rename: (base_hash: string | null, design_hash: string | null, old: string, new_: string) =>
    call<{ intent: IntentInfo; build: BuildJ; renamed_literals: number }>("/api/intent/rename", "POST",
                                                                          { base_hash, design_hash, old, new: new_ }),
  proposals: () => call<{ proposals: ProposalJ[]; requests: RequestJ[] }>("/api/proposals"),
  accept: (id: string, comment = "") =>
    call<{ proposal: ProposalJ; build: BuildJ }>(`/api/proposals/${id}/accept`, "POST", { comment }),
  reject: (id: string, comment: string) => call<{ proposal: ProposalJ }>(`/api/proposals/${id}/reject`, "POST", { comment }),
  ask: (node: string, note: string) => call<RequestJ>("/api/requests", "POST", { node, note }),
  proposalMesh: (id: string, which: "before" | "after") =>
    fetch(`/api/proposals/${id}/mesh/${which}`).then((r) => {
      if (!r.ok) throw new Error(`proposal mesh ${id}/${which}: ${r.status}`);
      return r.arrayBuffer();
    }),
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
