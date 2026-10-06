import { useCallback, useRef, useState } from "react";
import { streamChat } from "../api";
import type { ChatMessage, StreamEvent } from "../types";

let seq = 0;
// crypto.randomUUID() is unavailable on plain-http LAN addresses, so use a counter.
const nextId = () => `m${Date.now()}-${seq++}`;

const MAX_HISTORY = 12;

const statusFor = (tool: string) =>
  tool === "read_page" ? "Reading page" : "Searching the website";

export function useChat() {
  const [mode, setMode] = useState<"website" | "syllabus">("syllabus");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const patchLast = useCallback((fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) =>
      prev.length === 0 ? prev : [...prev.slice(0, -1), fn(prev[prev.length - 1])],
    );
  }, []);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || busy) return;

      const history = [
        ...messages.filter((m) => m.content && !m.error),
        { role: "user" as const, content },
      ]
        .slice(-MAX_HISTORY)
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content, sources: [] },
        { id: nextId(), role: "assistant", content: "", sources: [], streaming: true },
      ]);
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const onEvent = (e: StreamEvent) => {
        switch (e.type) {
          case "token":
            patchLast((m) => ({ ...m, content: m.content + e.text, status: undefined }));
            break;
          case "tool_call":
            patchLast((m) => ({ ...m, status: statusFor(e.name) }));
            break;
          case "tool_output":
            patchLast((m) => ({ ...m, status: "Reviewing results" }));
            break;
          case "sources":
            patchLast((m) => ({ ...m, sources: e.sources }));
            break;
          case "error":
            patchLast((m) => ({ ...m, error: e.message }));
            break;
          default:
            break;
        }
      };

      try {
        await streamChat(history, onEvent, controller.signal, mode);
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        if (!aborted) {
          const message = err instanceof Error ? err.message : "Request failed.";
          patchLast((m) => ({ ...m, error: message }));
        }
      } finally {
        patchLast((m) => ({ ...m, streaming: false, status: undefined }));
        setBusy(false);
        abortRef.current = null;
      }
    },
    [messages, busy, patchLast],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
  }, []);

  return { messages, busy, send, stop, clear, mode, setMode };
}