import { useEffect, useRef, useState } from "react";
import type { ThemeSettings } from "../theme";
import { MoonIcon, PaletteIcon, SunIcon } from "./icons";
import { ThemePanel } from "./ThemePanel";

interface Props {
  settings: ThemeSettings;
  onThemeChange: (patch: Partial<ThemeSettings>) => void;
  onThemeReset: () => void;
  onToggleMode: () => void;
}

export function Header({ settings, onThemeChange, onThemeReset, onToggleMode }: Props) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const dark = settings.mode === "dark";

  return (
    <div className="topbar" ref={wrapRef}>
      <header className="header">
        <div className="container header-inner">
          <div className="brand">
            <span>
                <img src="favicon.svg" height={30} width={30}/>
            </span>
            <span className="brand-name">Campus AI</span>
          </div>
          <div className="header-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              aria-label="Appearance settings"
              title="Appearance"
            >
              <PaletteIcon />
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={onToggleMode}
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              title={dark ? "Light mode" : "Dark mode"}
            >
              {dark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>

      {open && (
        <div className="container panel-anchor">
          <ThemePanel settings={settings} onChange={onThemeChange} onReset={onThemeReset} />
        </div>
      )}
    </div>
  );
}