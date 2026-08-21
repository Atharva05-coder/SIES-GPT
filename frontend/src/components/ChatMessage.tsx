interface ChatMessageProps {
  role: "user" | "ai";
  content: string;
}

function ChatMessage({
  role,
  content,
}: ChatMessageProps) {
  return (
    <div className={`message ${role}`}>

      <div className="message-avatar">
        {role === "user" ? "👤" : "✦"}
      </div>

      <div className="message-content">
        {content}
      </div>

    </div>
  );
}

export default ChatMessage;