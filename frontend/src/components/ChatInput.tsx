interface ChatInputProps {
  message: string;
  setMessage: (message: string) => void;
  onSend: () => void;
}

function ChatInput({
  message,
  setMessage,
  onSend,
}: ChatInputProps) {
  return (
    <div className="chat-input-container">

      <div className="chat-input-wrapper">

        <input
          className="chat-input"
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onSend();
            }
          }}
          placeholder="Ask anything about SIES GST..."
        />

        <button
          className="send-button"
          onClick={onSend}
          disabled={!message.trim()}
        >
          ➤
        </button>

      </div>

    </div>
  );
}

export default ChatInput;