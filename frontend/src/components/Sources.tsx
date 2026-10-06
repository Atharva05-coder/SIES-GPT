import { useState } from "react";
import type { Source } from "../types";
import { GlobeIcon } from "./icons";

function originOf(url: string): string {
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Favicon({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  const origin = originOf(url);
  if (!origin || failed) return <GlobeIcon className="favicon" width={16} height={16} />;
  return (
    <img
      className="favicon"
      src={`${origin}/favicon.ico`}
      alt=""
      width={16}
      height={16}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

export function Sources({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="sources">
      <span className="sources-label">Sources</span>
      <ul>
        {sources.map((s) => (
          <li key={s.url}>
            <a className="source glass" href={s.url} target="_blank" rel="noopener noreferrer">
              <Favicon url={s.url} />
              <span className="source-title">{s.title}</span>
              <span className="source-host">{hostOf(s.url)}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}