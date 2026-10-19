export type Role = "user" | "assistant";

export interface Source {
  url: string;
  title: string;
}

export interface Benchmark {
  totalTime: number;
  ttft?: number;
  tokens?: number;
  tokensPerSecond?: number;
  route?: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  sources: Source[];
  status?: string;
  error?: string;
  streaming?: boolean;
  benchmark?: Benchmark;
}

export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "tool_call"; name: string }
  | { type: "tool_output" }
  | { type: "sources"; sources: Source[] }
  | { type: "done" }
  | { type: "error"; message: string }
  | {
      type: "benchmark";
      total_time?: number;
      ttft?: number;
      tokens?: number;
      tokens_per_sec?: number;
      route?: string;
    };

export interface Health {
  ready: boolean;
  building: boolean;
  pages: number;
  chunks: number;
  pdf_ready?: boolean;
  pdf_chunks?: number;
  error: string | null;
}

export interface PdfStatus {
  ready: boolean;
  cached_chunks: number;
  indexed_chunks: number;
  documents: string[];
}