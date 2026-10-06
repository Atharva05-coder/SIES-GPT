import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { SendIcon, StopIcon, TrashIcon } from "./icons";

interface Props {
  busy: boolean;
  ready: boolean;
  canClear: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onClear: () => void;
}

export function Composer({ busy, ready, canClear, onSend, onStop, onClear }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // auto-grow up to ~6 lines
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const submit = () => {
    if (!text.trim() || busy || !ready) return;
    onSend(text);
    setText("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="dock">
      <div className="container">
        <div className="composer glass">
          {canClear && (
            <button
              type="button"
              className="icon-btn"
              onClick={onClear}
              aria-label="Clear chat"
              title="Clear chat"
            >
              <TrashIcon />
            </button>
          )}
          <textarea
            ref={ref}
            rows={1}
            value={text}
            maxLength={4000}
            placeholder={ready ? "Ask about faculty, courses, admissions…" : "Getting ready…"}
            aria-label="Message"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
          />
          {busy ? (
            <button type="button" className="send" onClick={onStop} aria-label="Stop generating">
              <StopIcon />
            </button>
          ) : (
            <button
              type="button"
              className="send"
              onClick={submit}
              disabled={!text.trim() || !ready}
              aria-label="Send message"
            >
              <SendIcon />
            </button>
          )}
        </div>
        <p className="fineprint">Answers come from the SIES GST website and may be incomplete.</p>
      </div>
    </div>
  );
}