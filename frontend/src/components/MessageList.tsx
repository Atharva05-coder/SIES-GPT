import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import { Sources } from "./Sources";

const SUGGESTIONS = [
  "Who are the faculty in Computer Engineering?",
  "What is the program structure and electives for Sem 6?",
  "What are the internship guidelines and policies?",
  "Tell me about the NBA accreditation and IPR team.",
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

function BenchmarkView({ benchmark }: { benchmark: NonNullable<ChatMessage["benchmark"]> }) {
  return (
    <div className="benchmark-bar" aria-label="Response generation benchmark">
      <span className="benchmark-badge" title="Total response latency">
        <svg className="benchmark-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span>{benchmark.totalTime}s</span>
      </span>

      {benchmark.tokensPerSecond ? (
        <span className="benchmark-badge" title="Generation speed">
          <svg className="benchmark-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          <span>{benchmark.tokensPerSecond} tok/s</span>
        </span>
      ) : null}

      {benchmark.tokens ? (
        <span className="benchmark-badge" title="Generated tokens">
          <svg className="benchmark-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span>{benchmark.tokens} tokens</span>
        </span>
      ) : null}

      {benchmark.ttft ? (
        <span className="benchmark-badge subtle" title="Time to first token (TTFT)">
          <span>TTFT: {benchmark.ttft}s</span>
        </span>
      ) : null}

      {benchmark.route ? (
        <span className="benchmark-badge route" title="Engine route">
          <span>{benchmark.route}</span>
        </span>
      ) : null}
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
      {m.benchmark && !m.streaming && <BenchmarkView benchmark={m.benchmark} />}
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
          <p>Answers come from the college website, syllabus, and official documents, with sources.</p>
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