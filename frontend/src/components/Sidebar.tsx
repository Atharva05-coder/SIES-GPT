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
      <div 
        className={`sidebar-overlay ${isOpen ? 'open' : ''}`} 
        onClick={() => setIsOpen(false)} 
      />
      <div className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h2>Chat History</h2>
          <button className="sidebar-close" onClick={() => setIsOpen(false)}>&times;</button>
        </div>
        
        <div>
          <button 
            className="sidebar-new-btn"
            onClick={() => { onNewChat(); setIsOpen(false); }}
          >
            + New Chat
          </button>
        </div>

        <div className="chat-list">
          {chats.map(chat => (
            <div 
              key={chat.id} 
              className={`chat-item ${chat.id === activeChatId ? 'active' : ''}`}
              onClick={() => { onSelectChat(chat.id); setIsOpen(false); }}
            >
              <div className="chat-item-title">
                {chat.title}
              </div>
              <button 
                className="chat-item-delete"
                onClick={(e) => { e.stopPropagation(); onDeleteChat(chat.id); }}
                title="Delete Chat"
              >
                &times;
              </button>
            </div>
          ))}
          {chats.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '20px', fontSize: '14px' }}>
              No previous chats.
            </div>
          )}
        </div>

        <div className="sidebar-footer" style={{ padding: '16px', borderTop: '1px solid var(--border)', fontSize: '12px', color: 'var(--text-muted)' }}>
          <div style={{ fontWeight: 600, marginBottom: '6px', color: 'var(--text)' }}>Active Knowledge Bases</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span>📚 Syllabus & Labs RAG</span>
            <span>🌐 Website Pages & Faculty</span>
            <span>📄 Official Documents & Policies</span>
          </div>
        </div>
      </div>
    </>
  );
}