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
  mode: "website" | "syllabus" = "website"
): Promise<void> {
  if (mode === "syllabus") {
    const lastMessage = messages[messages.length - 1];
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: lastMessage.content }),
      signal,
    });

    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }

    const data = await res.json();
    if (data.answer) {
      onEvent({ type: "token", text: data.answer });
    }
    if (data.sources) {
      const grouped = Object.values(
        data.sources.reduce((acc: any, s: any) => {
          if (!acc[s.filename]) {
            acc[s.filename] = { ...s, pages: [s.page] };
          } else if (!acc[s.filename].pages.includes(s.page)) {
            acc[s.filename].pages.push(s.page);
          }
          return acc;
        }, {})
      ).map((groupedSource: any) => ({
        url: groupedSource.url || `https://siesgst.edu.in/images/${encodeURIComponent(groupedSource.filename)}`,
        title: `${groupedSource.filename} (Pages ${groupedSource.pages.join(", ")})`
      }));
      onEvent({ type: "sources", sources: grouped });
    }
    return;
  }

  // Website mode (CampusAI)
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
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
