export type Role = "user" | "assistant";

export interface Source {
  url: string;
  title: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  sources: Source[];
  status?: string;
  error?: string;
  streaming?: boolean;
}

export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "tool_call"; name: string }
  | { type: "tool_output" }
  | { type: "sources"; sources: Source[] }
  | { type: "done" }
  | { type: "error"; message: string };

export interface Health {
  ready: boolean;
  building: boolean;
  pages: number;
  chunks: number;
  error: string | null;
}