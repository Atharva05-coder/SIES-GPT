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


function App() {

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState<Message[]>([]);

  const [loading, setLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);


  // -----------------------------------------
  // Auto scroll
  // -----------------------------------------

  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });

  }, [messages, loading]);


  // -----------------------------------------
  // Send message
  // -----------------------------------------

  const handleSend = async () => {

    const userMessage = message.trim();

    if (!userMessage || loading) {
      return;
    }


    // Show user message
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: userMessage,
      },
    ]);


    // Clear input
    setMessage("");

    setLoading(true);


    try {

      const response = await fetch(
        "http://127.0.0.1:8000/chat",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            message: userMessage,
          }),
        }
      );


      if (!response.ok) {

        throw new Error(
          "Failed to get response from server"
        );

      }


      const data = await response.json();


      // Add AI response
      setMessages((prev) => [
        ...prev,

        {
          role: "assistant",

          content: data.answer,

          sources: data.sources || [],
        },
      ]);

    } catch (error) {

      console.error(
        "Chat error:",
        error
      );


      setMessages((prev) => [
        ...prev,

        {
          role: "assistant",

          content:
            "Sorry, I couldn't connect to the SIES GPT server. Please make sure the backend is running.",
        },
      ]);

    } finally {

      setLoading(false);

    }
  };


  // -----------------------------------------
  // Enter key
  // -----------------------------------------

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>
  ) => {

    if (e.key === "Enter") {
      handleSend();
    }

  };


  // -----------------------------------------
  // New chat
  // -----------------------------------------

  const handleNewChat = () => {

    setMessages([]);

    setMessage("");

  };


  // -----------------------------------------
  // Suggestion click
  // -----------------------------------------

  const handleSuggestion = (
    question: string
  ) => {

    setMessage(question);

  };


  return (

    <div className="app">

      {/* ================= SIDEBAR ================= */}

      <aside className="sidebar">

        <div className="sidebar-logo">

          <div className="sidebar-logo-icon">
            S
          </div>

          <div>

            <div className="sidebar-logo-text">
              SIES GPT
            </div>

            <span className="header-subtitle">
              AI Assistant
            </span>

          </div>

        </div>


        <button
          className="new-chat-button"
          onClick={handleNewChat}
        >
          + New Chat
        </button>


        <div className="sidebar-section">

          <div className="sidebar-section-title">
            Recent Chats
          </div>


          <div className="sidebar-item active">
            📚 SIES GPT Chat
          </div>


          <div className="sidebar-item">
            🎓 Academics
          </div>


          <div className="sidebar-item">
            📢 College Information
          </div>

        </div>


        <div className="sidebar-bottom">

          <div className="sidebar-item">
            ⚙️ Settings
          </div>

        </div>

      </aside>


      {/* ================= MAIN ================= */}

      <main className="main-content">


        {/* Header */}

        <header className="header">

          <div className="header-left">

            <button className="mobile-menu-button">
              ☰
            </button>

            <div>

              <div className="header-title">
                SIES GPT
              </div>

              <div className="header-subtitle">
                Knowledge Assistant for SIES GST
              </div>

            </div>

          </div>


          <div className="header-right">

            <button className="header-icon-button">
              👤
            </button>

          </div>

        </header>


        {/* ================= CHAT AREA ================= */}

        <section className="chat-area">


          {/* Welcome screen */}

          {messages.length === 0 && !loading && (

            <div className="welcome-screen">

              <div className="welcome-icon">
                ✦
              </div>


              <h1 className="welcome-title">
                Welcome to SIES GPT
              </h1>


              <p className="welcome-description">
                Your AI-powered assistant for
                SIES Graduate School of Technology.
                Ask questions about academics,
                syllabus, notices and college
                information.
              </p>


              {/* Suggestions */}

              <div className="suggestions">


                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What is the Third Year Computer Engineering Semester V syllabus?"
                    )
                  }
                >

                  <div className="suggestion-icon">
                    📚
                  </div>

                  <div className="suggestion-title">
                    Syllabus
                  </div>

                  <div className="suggestion-description">
                    Find subjects and syllabus information
                  </div>

                </button>


                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What are the Computer Engineering subjects in Semester V?"
                    )
                  }
                >

                  <div className="suggestion-icon">
                    🎓
                  </div>

                  <div className="suggestion-title">
                    Academics
                  </div>

                  <div className="suggestion-description">
                    Ask about academic information
                  </div>

                </button>


                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "What information is available about SIES GST?"
                    )
                  }
                >

                  <div className="suggestion-icon">
                    🏫
                  </div>

                  <div className="suggestion-title">
                    About SIES GST
                  </div>

                  <div className="suggestion-description">
                    Learn about SIES Graduate School of Technology
                  </div>

                </button>


                <button
                  className="suggestion-card"
                  onClick={() =>
                    handleSuggestion(
                      "Show me important SIES GST information."
                    )
                  }
                >

                  <div className="suggestion-icon">
                    📢
                  </div>

                  <div className="suggestion-title">
                    College Information
                  </div>

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

              {messages.map(
                (msg, index) => (

                  <div
                    key={index}
                    className={`message-row ${msg.role}`}
                  >

                    <div className="message-avatar">

                      {msg.role === "user"
                        ? "👤"
                        : "✦"}

                    </div>


                    <div className="message-content-wrapper">

                      <div className="message-name">

                        {msg.role === "user"
                          ? "You"
                          : "SIES GPT"}

                      </div>


                      <div className="message-bubble">

                        <div className="message-text">
                          {msg.content}
                        </div>


                        {/* Sources */}

                        {msg.sources &&
                          msg.sources.length > 0 && (

                            <div className="sources">

                              <div className="sources-title">
                                📚 Sources
                              </div>


                              {msg.sources.map(
                                (
                                  source,
                                  sourceIndex
                                ) => (

                                  <a
                                    key={sourceIndex}
                                    className="source-card"
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                  >

                                    <span className="source-icon">
                                      📄
                                    </span>


                                    <div className="source-info">

                                      <strong>
                                        {source.filename}
                                      </strong>

                                      <span>
                                        Page {source.page}
                                      </span>

                                    </div>

                                  </a>

                                )
                              )}

                            </div>

                          )}

                      </div>

                    </div>

                  </div>

                )
              )}


              {/* Loading */}

              {loading && (

                <div className="message-row assistant">

                  <div className="message-avatar">
                    ✦
                  </div>

                  <div className="message-content-wrapper">

                    <div className="message-name">
                      SIES GPT
                    </div>

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
              onChange={(e) =>
                setMessage(e.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about SIES GST..."
              disabled={loading}
            />


            <button
              className="send-button"
              onClick={handleSend}
              disabled={
                !message.trim() || loading
              }
            >

              {loading
                ? "..."
                : "➤"}

            </button>

          </div>

        </div>

      </main>

    </div>

  );
}


export default App;