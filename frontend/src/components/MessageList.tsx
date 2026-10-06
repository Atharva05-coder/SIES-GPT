import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import { Sources } from "./Sources";

const SUGGESTIONS = [
  "Who are the faculty in Computer Engineering?",
  "What undergraduate courses does SIES GST offer?",
  "Tell me about placements and recruiters.",
  "How can I apply for admission?",
];

/** Removes a trailing "Sources:" block if the model wrote one anyway
 *  (the UI renders its own sources footer). */
function stripSourcesTail(text: string): string {
  const re = /\n[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?sources?(?:\*\*)?[ \t]*(?::|\n|$)/gi;
  let last: RegExpExecArray | null = null;
  for (let m = re.exec(text); m; m = re.exec(text)) last = m;
  return last && text.length - last.index < 800 ? text.slice(0, last.index).trimEnd() : text;
}

function Status({ text }: { text: string }) {
  return (
    <div className="status" role="status">
      <span className="spinner" aria-hidden="true" />
      <span className="status-text">{text}…</span>
    </div>
  );
}

function Assistant({ m }: { m: ChatMessage }) {
  const text = m.sources.length > 0 ? stripSourcesTail(m.content) : m.content;
  const showStatus = m.streaming && (Boolean(m.status) || !m.content);

  return (
    <div className="answer">
      {text && (
        <div className="markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: (props) => (
                <a href={props.href} target="_blank" rel="noopener noreferrer">
                  {props.children}
                </a>
              ),
              table: (props) => (
                <div className="table-scroll">
                  <table>{props.children}</table>
                </div>
              ),
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
      )}

      {showStatus && <Status text={m.status ?? "Thinking"} />}
      {m.error && <p className="error" role="alert">{m.error}</p>}
      {!m.streaming && !m.content && !m.error && <p className="muted">No response.</p>}
      <Sources sources={m.sources} />
    </div>
  );
}

interface Props {
  messages: ChatMessage[];
  onPick: (text: string) => void;
  disabled: boolean;
}

export function MessageList({ messages, onPick, disabled }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="scroller">
        <div className="container empty">
          <h2>Ask anything about SIES GST</h2>
          <p>Answers come from the college website, with sources.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className="suggestion glass"
                disabled={disabled}
                onClick={() => onPick(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="scroller" ref={scrollRef} onScroll={onScroll}>
      <div className="container thread" aria-live="polite">
        {messages.map((m) =>
          m.role === "user" ? (
            <div className="msg user" key={m.id}>
              <div className="user-bubble">{m.content}</div>
            </div>
          ) : (
            <div className="msg" key={m.id}>
              <Assistant m={m} />
            </div>
          ),
        )}
      </div>
    </div>
  );
}