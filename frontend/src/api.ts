import type { Health, Role, StreamEvent } from "./types";

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch(`${BASE}/api/health`, { signal });
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return (await res.json()) as Health;
}

export async function streamChat(
  messages: { role: Role; content: string }[],
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
  requestId?: string
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (requestId) {
    headers["X-Request-ID"] = requestId;
  }
  const res = await fetch(`${BASE}/api/smart_chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ messages, request_id: requestId }),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as StreamEvent);
      } catch {
        /* ignore a malformed frame */
      }
    }
  }
}

export async function fetchPdfStatus(signal?: AbortSignal): Promise<import("./types").PdfStatus> {
  const res = await fetch(`${BASE}/api/pdf/status`, { signal });
  if (!res.ok) throw new Error(`PDF status failed (${res.status})`);
  return (await res.json()) as import("./types").PdfStatus;
}

export async function triggerPdfIngest(adminToken?: string): Promise<{ status: string }> {
  const headers: Record<string, string> = {};
  if (adminToken) headers["X-Admin-Token"] = adminToken;
  const res = await fetch(`${BASE}/api/pdf/ingest`, {
    method: "POST",
    headers,
  });
  if (!res.ok) throw new Error(`PDF ingest request failed (${res.status})`);
  return (await res.json()) as { status: string };
}

export async function cancelChat(requestId: string): Promise<void> {
  try {
    await fetch(`${BASE}/api/chat/cancel?request_id=${encodeURIComponent(requestId)}`, {
      method: "POST",
    });
  } catch {
    /* ignore network abort errors when sending cancel request */
  }
}

