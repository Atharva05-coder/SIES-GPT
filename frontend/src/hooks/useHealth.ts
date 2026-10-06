import { useEffect, useState } from "react";
import { fetchHealth } from "../api";
import type { Health } from "../types";

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    const tick = async () => {
      try {
        const h = await fetchHealth(controller.signal);
        setHealth(h);
        setUnreachable(false);
        if (h.ready || (h.error && !h.building)) return; // stop polling
      } catch {
        if (controller.signal.aborted) return;
        setUnreachable(true);
      }
      timer = window.setTimeout(tick, 2500);
    };

    void tick();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, []);

  return { health, unreachable };
}