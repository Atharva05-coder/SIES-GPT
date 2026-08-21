import { useState } from "react";
import "./App.css";

import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import WelcomeScreen from "./components/WelcomeScreen";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";

interface Message {
  role: "user" | "ai";
  content: string;
}

function App() {

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState<Message[]>([]);


 const handleSend = async () => {
  if (!message.trim()) return;

  const userMessage = message.trim();

  setMessages((prev) => [
    ...prev,
    {
      role: "user",
      content: userMessage,
    },
  ]);

  setMessage("");

  try {
    const response = await fetch(
      "http://localhost:8000/chat",
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
      throw new Error("Failed to get response");
    }

    const data = await response.json();

    setMessages((prev) => [
      ...prev,
      {
        role: "ai",
        content: data.answer,
      },
    ]);

  } catch (error) {

    console.error(error);

    setMessages((prev) => [
      ...prev,
      {
        role: "ai",
        content:
          "Sorry, I couldn't connect to the SIES GPT server.",
      },
    ]);
  }
};


  const handleNewChat = () => {
    setMessages([]);
    setMessage("");
  };


  const handleSuggestionClick = (question: string) => {
    setMessage(question);
  };


  return (
    <div className="app">

      {/* SIDEBAR */}

      <Sidebar
        onNewChat={handleNewChat}
      />


      {/* MAIN */}

      <main className="main-content">

        {/* HEADER */}

        <Header
          onMenuClick={() => {}}
        />


        {/* CHAT */}

        <section className="chat-area">

          {messages.length === 0 ? (

            <WelcomeScreen
              onSuggestionClick={handleSuggestionClick}
            />

          ) : (

            <div className="messages">

              {messages.map((msg, index) => (

                <ChatMessage
                  key={index}
                  role={msg.role}
                  content={msg.content}
                />

              ))}

            </div>

          )}

        </section>


        {/* INPUT */}

        <ChatInput
          message={message}
          setMessage={setMessage}
          onSend={handleSend}
        />

      </main>

    </div>
  );
}

export default App;