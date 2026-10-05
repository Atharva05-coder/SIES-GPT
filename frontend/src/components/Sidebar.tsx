interface SidebarProps {
  onNewChat: () => void;
}

function Sidebar({ onNewChat }: SidebarProps) {
  return (
    <aside className="sidebar">

      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          S
        </div>

        <div>
          <div className="sidebar-logo-text">
            Campus AI
          </div>

          <span className="header-subtitle">
            AI Assistant
          </span>
        </div>
      </div>

      {/* New Chat */}
      <button
        className="new-chat-button"
        onClick={onNewChat}
      >
        + New Chat
      </button>

      {/* Recent Chats */}
      <div className="sidebar-section">

        <div className="sidebar-section-title">
          Recent Chats
        </div>

        <div className="sidebar-item active">
          📚 Semester 5 Syllabus
        </div>

        <div className="sidebar-item">
          🎓 Data Mining
        </div>

        <div className="sidebar-item">
          📢 College Notices
        </div>

      </div>

      {/* Bottom */}
      <div className="sidebar-bottom">

        <div className="sidebar-item">
          ⚙️ Settings
        </div>

      </div>

    </aside>
  );
}

export default Sidebar;