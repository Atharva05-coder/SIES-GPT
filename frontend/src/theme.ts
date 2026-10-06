import { useCallback, useLayoutEffect, useState } from "react";

export type Mode = "light" | "dark";

export interface ThemeSettings {
  mode: Mode;
  accent: string;
  accent2: string;
  blur: number; // px
}

export const PRESETS = [
  { name: "Indigo", accent: "#4f46e5", accent2: "#38bdf8" },
  { name: "Emerald", accent: "#059669", accent2: "#a3e635" },
  { name: "Rose", accent: "#e11d48", accent2: "#fb923c" },
  { name: "Violet", accent: "#7c3aed", accent2: "#f472b6" },
  { name: "Slate", accent: "#334155", accent2: "#94a3b8" },
] as const;

const STORAGE_KEY = "campusai-theme-v2";
const HEX = /^#[0-9a-f]{6}$/i;

function defaults(): ThemeSettings {
  const prefersDark =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  return {
    mode: prefersDark ? "dark" : "light",
    accent: PRESETS[0].accent,
    accent2: PRESETS[0].accent2,
    blur: 16,
  };
}

function load(): ThemeSettings {
  const base = defaults();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return base;
    const p = JSON.parse(raw) as Partial<ThemeSettings>;
    return {
      mode: p.mode === "light" || p.mode === "dark" ? p.mode : base.mode,
      accent: typeof p.accent === "string" && HEX.test(p.accent) ? p.accent : base.accent,
      accent2: typeof p.accent2 === "string" && HEX.test(p.accent2) ? p.accent2 : base.accent2,
      blur:
        typeof p.blur === "number" && Number.isFinite(p.blur)
          ? Math.min(30, Math.max(0, p.blur))
          : base.blur,
    };
  } catch {
    return base;
  }
}

// --- pick a readable text color for content drawn on the accent color ---
function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

function contrast(a: number, b: number): number {
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function readableOn(hex: string): string {
  const l = luminance(hex);
  return contrast(l, luminance("#ffffff")) >= contrast(l, luminance("#0b0b12"))
    ? "#ffffff"
    : "#0b0b12";
}

function apply(s: ThemeSettings): void {
  const root = document.documentElement;
  root.dataset.theme = s.mode;
  root.style.setProperty("--accent", s.accent);
  root.style.setProperty("--accent-2", s.accent2);
  root.style.setProperty("--on-accent", readableOn(s.accent));
  root.style.setProperty("--blur", `${s.blur}px`);
}

export function useTheme() {
  const [settings, setSettings] = useState<ThemeSettings>(load);

  useLayoutEffect(() => {
    apply(settings);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      /* storage unavailable (private mode, etc.) */
    }
  }, [settings]);

  const update = useCallback((patch: Partial<ThemeSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const toggleMode = useCallback(() => {
    setSettings((prev) => ({ ...prev, mode: prev.mode === "dark" ? "light" : "dark" }));
  }, []);

  const reset = useCallback(() => {
    setSettings((prev) => ({ ...defaults(), mode: prev.mode }));
  }, []);

  return { settings, update, toggleMode, reset };
}