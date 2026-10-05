import { useEffect, useRef, useState } from "react";

import "./App.css";

type Source = {
  filename: string;
  page: number;
  url?: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

type ChatSession = {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
};

const EMPTY_MESSAGES: Message[] = [];
const CHAT_HISTORY_KEY = "siesgpt-chat-history";
const ACTIVE_CHAT_KEY = "siesgpt-active-chat";

function readChatHistory(): ChatSession[] {
  try {
    const stored = localStorage.getItem(CHAT_HISTORY_KEY);
    const parsed: unknown = stored ? JSON.parse(stored) : [];
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(
      (chat): chat is ChatSession =>
        chat &&
        typeof chat.id === "string" &&
        typeof chat.title === "string" &&
        Array.isArray(chat.messages) &&
        typeof chat.updatedAt === "number",
    );
  } catch {
    return [];
  }
}

function createChatId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function createChatTitle(text: string): string {
  const title = text.replace(/\s+/g, " ").trim();
  return title.length > 42 ? `${title.slice(0, 39)}...` : title;
}

function App() {
  const [message, setMessage] = useState("");

  const [chats, setChats] = useState<ChatSession[]>(readChatHistory);

  const [activeChatId, setActiveChatId] = useState<string | null>(() =>
    localStorage.getItem(ACTIVE_CHAT_KEY),
  );

  const activeChat = chats.find((chat) => chat.id === activeChatId) ?? null;

  const messages = activeChat?.messages ?? EMPTY_MESSAGES;

  const [loading, setLoading] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [settingsOpen, setSettingsOpen] = useState(false);

  const [apiBase, setApiBase] = useState(
    () => localStorage.getItem("siesgpt-api-url") || "http://127.0.0.1:8000",
  );

  const [apiDraft, setApiDraft] = useState(apiBase);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chats));
      if (activeChatId && chats.some((chat) => chat.id === activeChatId)) {
        localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId);
      } else {
        localStorage.removeItem(ACTIVE_CHAT_KEY);
      }
    } catch (error) {
      console.error("Could not save chat history:", error);
    }
  }, [chats, activeChatId]);

  // -----------------------------------------
  // Auto scroll
  // -----------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [activeChatId, messages, loading]);

  const appendMessageToChat = (
    chatId: string,
    nextMessage: Message,
    initialTitle: string,
  ) => {
    setChats((current) => {
      const updatedAt =
        current.reduce((latest, chat) => Math.max(latest, chat.updatedAt), 0) +
        1;
      const existing = current.find((chat) => chat.id === chatId);
      if (!existing) {
        return [
          {
            id: chatId,
            title: createChatTitle(initialTitle),
            messages: [nextMessage],
            updatedAt,
          },
          ...current,
        ];
      }

      return current
        .map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                title: chat.messages.length
                  ? chat.title
                  : createChatTitle(initialTitle),
                messages: [...chat.messages, nextMessage],
                updatedAt,
              }
            : chat,
        )
        .sort((first, second) => second.updatedAt - first.updatedAt);
    });
  };

  // -----------------------------------------
  // Send message
  // -----------------------------------------

  const handleSend = async () => {
    const userMessage = message.trim();

    if (!userMessage || loading) {
      return;
    }

    const chatId = activeChat?.id ?? createChatId();
    if (!activeChat) setActiveChatId(chatId);

    appendMessageToChat(
      chatId,
      { role: "user", content: userMessage },
      userMessage,
    );

    // Clear input
    setMessage("");

    setLoading(true);

    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/chat`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          message: userMessage,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      appendMessageToChat(
        chatId,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
        },
        userMessage,
      );
    } catch (error) {
      console.error("Chat error:", error);

      appendMessageToChat(
        chatId,
        {
          role: "assistant",
          content:
            "Sorry, I couldn't connect to the Campus AI server. Please make sure the backend is running.",
        },
        userMessage,
      );
    } finally {
      setLoading(false);
    }
  };

  // -----------------------------------------
  // Enter key
  // -----------------------------------------

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  // -----------------------------------------
  // New chat
  // -----------------------------------------

  const handleNewChat = () => {
    setActiveChatId(null);
    setMessage("");
    setSidebarOpen(false);
  };

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId);
    setMessage("");
    setSidebarOpen(false);
  };

  const handleDeleteChat = (chatId: string) => {
    const remaining = chats.filter((chat) => chat.id !== chatId);
    setChats(remaining);
    if (activeChatId === chatId) {
      setActiveChatId(remaining[0]?.id ?? null);
    }
  };

  // -----------------------------------------
  // Suggestion click
  // -----------------------------------------

  const handleSuggestion = (question: string) => {
    setMessage(question);

    setSidebarOpen(false);
  };

  const handleSaveSettings = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedUrl = apiDraft.trim().replace(/\/+$/, "");

    if (!normalizedUrl) {
      return;
    }

    localStorage.setItem("siesgpt-api-url", normalizedUrl);
    setApiBase(normalizedUrl);
    setSettingsOpen(false);
  };

  return (
    <div className="app">
      {/* ================= SIDEBAR ================= */}

      <aside className={`sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">S</div>

          <div>
            <div className="sidebar-logo-text">Campus AI</div>

            <span className="header-subtitle">AI Assistant</span>
          </div>
        </div>

        <button className="new-chat-button" onClick={handleNewChat}>
          <span aria-hidden="true">＋</span>
          New chat
        </button>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Explore SIES</div>

          <button
            className="sidebar-item"
            onClick={() =>
              handleSuggestion(
                "What is the syllabus for my course? Ask me which department and semester if needed.",
              )
            }
          >
            <span>▤</span> Syllabus
          </button>

          <button
            className="sidebar-item"
            onClick={() =>
              handleSuggestion(
                "Show me the latest notices and announcements from SIES GST.",
              )
            }
          >
            <span>◷</span> Notices
          </button>

          <button
            className="sidebar-item"
            onClick={() =>
              handleSuggestion(
                "What college information is available about SIES GST?",
              )
            }
          >
            <span>⌂</span> College information
          </button>
        </div>

        <section className="sidebar-section recent-chats-section">
          <div className="sidebar-section-title">Recent chats</div>
          <div className="recent-chat-list">
            {chats.length === 0 ? (
              <p className="recent-chat-empty">
                Your conversations will appear here
              </p>
            ) : (
              chats.map((chat) => (
                <div className="recent-chat-row" key={chat.id}>
                  <button
                    className={`sidebar-item recent-chat-button ${
                      activeChat?.id === chat.id ? "active" : ""
                    }`}
                    onClick={() => handleSelectChat(chat.id)}
                    title={chat.title}
                  >
                    <span aria-hidden="true">◷</span>
                    <span className="recent-chat-title">{chat.title}</span>
                  </button>
                  <button
                    className="delete-chat-button"
                    onClick={() => handleDeleteChat(chat.id)}
                    disabled={loading}
                    aria-label={`Delete chat: ${chat.title}`}
                    title="Delete chat"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <div className="sidebar-bottom">
          <button
            className="sidebar-item"
            onClick={() => {
              setApiDraft(apiBase);
              setSettingsOpen(true);
              setSidebarOpen(false);
            }}
          >
            <span>⚙</span> Settings
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <button
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        />
      )}

      {/* ================= MAIN ================= */}

      <main className="main-content">
        {/* Header */}

        <header className="header">
          <div className="header-left">
            <button
              className="mobile-menu-button"
              onClick={() => setSidebarOpen((open) => !open)}
              aria-label="Toggle navigation"
              aria-expanded={sidebarOpen}
            >
              ☰
            </button>

            <div>
              <div className="header-title">Campus AI</div>

              <div className="header-subtitle">
                Knowledge Assistant for SIES GST
              </div>
            </div>
          </div>

          <div className="header-right">
            <button
              className="header-icon-button"
              onClick={() => {
                setApiDraft(apiBase);
                setSettingsOpen(true);
              }}
              aria-label="Open settings"
              title="Settings"
            >
              ⚙
            </button>
          </div>
        </header>

        {settingsOpen && (
          <div
            className="settings-backdrop"
            onClick={() => setSettingsOpen(false)}
          >
            <section
              className="settings-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-title"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="settings-heading">
                <h2 id="settings-title">Settings</h2>
                <button
                  className="header-icon-button"
                  onClick={() => setSettingsOpen(false)}
                  aria-label="Close settings"
                >
                  ×
                </button>
              </div>
              <form onSubmit={handleSaveSettings}>
                <label htmlFor="api-url">Backend URL</label>
                <input
                  id="api-url"
                  value={apiDraft}
                  onChange={(event) => setApiDraft(event.target.value)}
                  placeholder="http://127.0.0.1:8000"
                  type="url"
                  required
                />
                <button className="new-chat-button" type="submit">
                  Save settings
                </button>
              </form>
            </section>
          </div>
        )}

        {/* ================= CHAT AREA ================= */}

        <section className="chat-area">
          {/* Welcome screen */}

          {messages.length === 0 && !loading && (
            <div className="welcome-screen">
              <div className="welcome-icon">✦</div>

              <h1 className="welcome-title">Welcome to Campus AI</h1>

              <p className="welcome-description">
                Your AI-powered assistant for SIES Graduate School of
                Technology. Ask questions about academics, syllabus, notices and
                college information.
              </p>

              {/* Suggestions */}

              <div className="suggestions">
                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What is the Third Year Computer Engineering Semester V syllabus?",
                    )
                  }
                >
                  <div className="suggestion-icon">📚</div>

                  <div className="suggestion-title">Syllabus</div>

                  <div className="suggestion-description">
                    Find subjects and syllabus information
                  </div>
                </button>

                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What are the Computer Engineering subjects in Semester V?",
                    )
                  }
                >
                  <div className="suggestion-icon">🎓</div>

                  <div className="suggestion-title">Academics</div>

                  <div className="suggestion-description">
                    Ask about academic information
                  </div>
                </button>

                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What information is available about SIES GST?",
                    )
                  }
                >
                  <div className="suggestion-icon">🏫</div>

                  <div className="suggestion-title">About SIES GST</div>

                  <div className="suggestion-description">
                    Learn about SIES Graduate School of Technology
                  </div>
                </button>

                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion("Show me important SIES GST information.")
                  }
                >
                  <div className="suggestion-icon">📢</div>

                  <div className="suggestion-title">College Information</div>

                  <div className="suggestion-description">
                    Find important college information
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* ================= MESSAGES ================= */}

          {messages.length > 0 && (
            <div className="messages-container">
              {messages.map((msg, index) => (
                <div key={index} className={`message-row ${msg.role}`}>
                  <div className="message-avatar">
                    {msg.role === "user" ? "👤" : "✦"}
                  </div>

                  <div className="message-content-wrapper">
                    <div className="message-name">
                      {msg.role === "user" ? "You" : "Campus AI"}
                    </div>

                    <div className="message-bubble">
                      <div className="message-text">{msg.content}</div>

                      {/* Sources */}

                      {msg.sources && msg.sources.length > 0 && (
                        <div className="sources">
                          <div className="sources-title">📚 Sources</div>

                          {msg.sources.map((source, sourceIndex) => (
                            <a
                              key={sourceIndex}
                              className="source-card"
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <span className="source-icon">📄</span>

                              <div className="source-info">
                                <strong>{source.filename}</strong>

                                <span>Page {source.page}</span>
                              </div>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Loading */}

              {loading && (
                <div className="message-row assistant">
                  <div className="message-avatar">✦</div>

                  <div className="message-content-wrapper">
                    <div className="message-name">Campus AI</div>

                    <div className="message-bubble loading-bubble">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </section>

        {/* ================= INPUT ================= */}

        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <input
              className="chat-input"
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about SIES GST..."
              disabled={loading}
            />

            <button
              className="send-button"
              onClick={handleSend}
              disabled={!message.trim() || loading}
            >
              {loading ? "..." : "➤"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
