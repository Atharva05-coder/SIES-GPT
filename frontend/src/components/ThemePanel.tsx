import { PRESETS } from "../theme";
import type { ThemeSettings } from "../theme";

interface Props {
  settings: ThemeSettings;
  onChange: (patch: Partial<ThemeSettings>) => void;
  onReset: () => void;
}

export function ThemePanel({ settings, onChange, onReset }: Props) {
  return (
    <div className="panel glass" role="dialog" aria-label="Appearance settings">
      <div>
        <span className="panel-label">Presets</span>
        <div className="swatches">
          {PRESETS.map((p) => {
            const active = settings.accent === p.accent && settings.accent2 === p.accent2;
            return (
              <button
                key={p.name}
                type="button"
                className="swatch"
                aria-label={p.name}
                title={p.name}
                aria-pressed={active}
                style={{ background: `linear-gradient(135deg, ${p.accent} 50%, ${p.accent2} 50%)` }}
                onClick={() => onChange({ accent: p.accent, accent2: p.accent2 })}
              />
            );
          })}
        </div>
      </div>

      <label className="panel-row">
        <span className="panel-label">Accent color</span>
        <input
          type="color"
          value={settings.accent}
          onChange={(e) => onChange({ accent: e.target.value })}
        />
      </label>

      <label className="panel-row">
        <span className="panel-label">Background glow</span>
        <input
          type="color"
          value={settings.accent2}
          onChange={(e) => onChange({ accent2: e.target.value })}
        />
      </label>

      <label className="panel-col">
        <span className="panel-label">Glass blur · {settings.blur}px</span>
        <input
          type="range"
          min={0}
          max={30}
          step={1}
          value={settings.blur}
          onChange={(e) => onChange({ blur: Number(e.target.value) })}
        />
      </label>

      <button type="button" className="btn-ghost" onClick={onReset}>
        Reset to default
      </button>
    </div>
  );
}