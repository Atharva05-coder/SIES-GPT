import type { Health } from "../types";

interface Props {
  health: Health | null;
  unreachable: boolean;
}

export function Notice({ health, unreachable }: Props) {
  let content: React.ReactNode = null;
  let tone = "";

  if (unreachable) {
    tone = "bad";
    content = "Can't reach the server. Make sure the backend is running.";
  } else if (health?.error && !health.building) {
    tone = "bad";
    content = "The knowledge base failed to load. Check the server logs.";
  } else if (health && !health.ready) {
    content = (
      <>
        <span className="spinner small" aria-hidden="true" />
        Getting things ready… the first start can take a minute.
      </>
    );
  }

  if (!content) return null;
  return (
    <div className="container notice-wrap">
      <div className={`notice glass ${tone}`} role="status">
        {content}
      </div>
    </div>
  );
}