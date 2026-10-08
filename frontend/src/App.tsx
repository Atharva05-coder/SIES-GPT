import { useState } from "react";
import { Composer } from "./components/Composer";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { Notice } from "./components/Notice";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { useHealth } from "./hooks/useHealth";
import { useTheme } from "./theme";

export default function App() {
  const { settings, update, toggleMode, reset } = useTheme();
  const { health, unreachable } = useHealth();
  const { messages, busy, send, stop, clear, mode, setMode, chats, activeChatId, createNewChat, selectChat, deleteChat } = useChat();
  const ready = Boolean(health?.ready) && !unreachable;
  
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <div className="backdrop" aria-hidden="true" />
      <Sidebar 
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={selectChat}
        onNewChat={createNewChat}
        onDeleteChat={deleteChat}
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
      />
      <div className="shell">
        <Header
          settings={settings}
          onThemeChange={update}
          onThemeReset={reset}
          onToggleMode={toggleMode}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <Notice health={health} unreachable={unreachable} />
        
        <div className="segmented-control glass">
          <button 
            className={`segment ${mode === 'website' ? 'active' : ''}`}
            onClick={() => setMode('website')}
          >
            Website (CampusAI)
          </button>
          <button 
            className={`segment ${mode === 'syllabus' ? 'active' : ''}`}
            onClick={() => setMode('syllabus')}
          >
            Syllabus (SIES-GPT)
          </button>
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