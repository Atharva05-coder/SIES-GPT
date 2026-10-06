import type { ChatSession } from "../hooks/useChat";

interface SidebarProps {
  chats: ChatSession[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  onDeleteChat: (id: string) => void;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

export function Sidebar({ chats, activeChatId, onSelectChat, onNewChat, onDeleteChat, isOpen, setIsOpen }: SidebarProps) {
  return (
    <>
      <div className={`sidebar-overlay ${isOpen ? 'open' : ''}`} onClick={() => setIsOpen(false)} style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 99, display: isOpen ? 'block' : 'none'
      }} />
      <div className={`sidebar ${isOpen ? 'open' : ''}`} style={{
        position: 'fixed', top: 0, left: 0, bottom: 0, width: '260px', 
        backgroundColor: 'var(--bg)', borderRight: '1px solid var(--glass-strong)',
        zIndex: 100, display: 'flex', flexDirection: 'column',
        transform: isOpen ? 'translateX(0)' : 'translateX(-100%)',
        transition: 'transform 0.3s ease',
        boxShadow: isOpen ? '2px 0 8px rgba(0,0,0,0.1)' : 'none'
      }}>
        <div style={{ padding: '20px', borderBottom: '1px solid var(--glass-strong)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '18px', color: 'var(--text)' }}>Chat History</h2>
          <button onClick={() => setIsOpen(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: 'var(--text)' }}>x</button>
        </div>
        
        <div style={{ padding: '15px' }}>
          <button 
            onClick={() => { onNewChat(); setIsOpen(false); }}
            style={{ 
              width: '100%', padding: '10px', borderRadius: '8px', 
              backgroundColor: 'var(--accent)', color: 'var(--on-accent)',
              border: 'none', cursor: 'pointer', fontWeight: 'bold'
            }}
          >
            + New Chat
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          {chats.map(chat => (
            <div 
              key={chat.id} 
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px', margin: '5px 0', borderRadius: '8px',
                backgroundColor: chat.id === activeChatId ? 'var(--glass)' : 'transparent',
                cursor: 'pointer',
                color: 'var(--text)'
              }}
              onClick={() => { onSelectChat(chat.id); setIsOpen(false); }}
            >
              <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, fontSize: '14px' }}>
                {chat.title}
              </div>
              <button 
                onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', marginLeft: '10px' }}
                title="Delete Chat"
              >
                x
              </button>
            </div>
          ))}
          {chats.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '20px', fontSize: '14px' }}>
              No previous chats.
            </div>
          )}
        </div>
      </div>
    </>
  );
}