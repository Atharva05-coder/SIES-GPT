import { Composer } from "./components/Composer";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { Notice } from "./components/Notice";
import { useChat } from "./hooks/useChat";
import { useHealth } from "./hooks/useHealth";
import { useTheme } from "./theme";

export default function App() {
  const { settings, update, toggleMode, reset } = useTheme();
  const { health, unreachable } = useHealth();
  const { messages, busy, send, stop, clear, mode, setMode } = useChat();
  const ready = Boolean(health?.ready) && !unreachable;

  return (
    <>
      <div className="backdrop" aria-hidden="true" />
      <div className="shell">
        <Header
          settings={settings}
          onThemeChange={update}
          onThemeReset={reset}
          onToggleMode={toggleMode}
        />
        <Notice health={health} unreachable={unreachable} />
        
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px', gap: '20px', color: 'var(--text)' }}>
          <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input type="radio" name="mode" value="website" checked={mode === 'website'} onChange={() => setMode('website')} />
            Website (CampusAI)
          </label>
          <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input type="radio" name="mode" value="syllabus" checked={mode === 'syllabus'} onChange={() => setMode('syllabus')} />
            Syllabus (SIES-GPT)
          </label>
        </div>
        <MessageList messages={messages} onPick={send} disabled={!ready || busy} />

        <Composer
          busy={busy}
          ready={ready}
          canClear={messages.length > 0}
          onSend={send}
          onStop={stop}
          onClear={clear}
        />
      </div>
    </>
  );
}