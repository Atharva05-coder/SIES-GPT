import { useCallback, useRef, useState, useEffect } from "react";
import { streamChat } from "../api";
import type { ChatMessage, StreamEvent } from "../types";

export type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
};

const CHAT_HISTORY_KEY = "campusai-chat-history";
const ACTIVE_CHAT_KEY = "campusai-active-chat";

let seq = 0;
const nextId = () => `m${Date.now()}-${seq++}`;
const createChatId = () => `c${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

const MAX_HISTORY = 12;

const statusFor = (tool: string) =>
  tool === "read_page" ? "Reading page" : "Searching the website";

function readChatHistory(): ChatSession[] {
  try {
    const stored = localStorage.getItem(CHAT_HISTORY_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export function useChat() {
  const [mode, setMode] = useState<"website" | "syllabus">("syllabus");
  const [chats, setChats] = useState<ChatSession[]>(readChatHistory);
  const [activeChatId, setActiveChatId] = useState<string | null>(() => localStorage.getItem(ACTIVE_CHAT_KEY));
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(chats));
      if (activeChatId && chats.some(c => c.id === activeChatId)) {
        localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId);
      } else {
        localStorage.removeItem(ACTIVE_CHAT_KEY);
      }
    } catch (e) {
      console.error(e);
    }
  }, [chats, activeChatId]);

  const activeChat = chats.find(c => c.id === activeChatId);
  const messages = activeChat?.messages ?? [];

  const patchLast = useCallback((fn: (m: ChatMessage) => ChatMessage) => {
    setChats(prev => {
      const chatIndex = prev.findIndex(c => c.id === activeChatId);
      if (chatIndex === -1) return prev;
      
      const newChats = [...prev];
      const chat = newChats[chatIndex];
      if (chat.messages.length === 0) return prev;
      
      const updatedMessages = [...chat.messages];
      updatedMessages[updatedMessages.length - 1] = fn(updatedMessages[updatedMessages.length - 1]);
      
      newChats[chatIndex] = { ...chat, messages: updatedMessages, updatedAt: Date.now() };
      return newChats;
    });
  }, [activeChatId]);

  const createNewChat = useCallback(() => {
    const newChat: ChatSession = {
      id: createChatId(),
      title: "New Chat",
      messages: [],
      updatedAt: Date.now(),
    };
    setChats(prev => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    return newChat.id;
  }, []);

  const selectChat = useCallback((id: string) => {
    if (busy) return;
    setActiveChatId(id);
  }, [busy]);

  const deleteChat = useCallback((id: string) => {
    setChats(prev => prev.filter(c => c.id !== id));
    if (activeChatId === id) {
      setActiveChatId(null);
    }
  }, [activeChatId]);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || busy) return;

      let currentChatId = activeChatId;
      if (!currentChatId || !chats.find(c => c.id === currentChatId)) {
        currentChatId = createNewChat();
      }

      const activeMsgs = chats.find(c => c.id === currentChatId)?.messages ?? [];

      const history = [
        ...activeMsgs.filter((m) => m.content && !m.error),
        { role: "user" as const, content },
      ]
        .slice(-MAX_HISTORY)
        .map((m) => ({ role: m.role, content: m.content }));

      setChats(prev => {
        const chatIndex = prev.findIndex(c => c.id === currentChatId);
        if (chatIndex === -1) return prev;
        
        const newChats = [...prev];
        const chat = newChats[chatIndex];
        
        const isFirstMessage = chat.messages.length === 0;
        let title = chat.title;
        if (isFirstMessage) {
           title = content.length > 30 ? content.slice(0, 27) + "..." : content;
        }

        newChats[chatIndex] = {
          ...chat,
          title,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            { id: nextId(), role: "user", content, sources: [] },
            { id: nextId(), role: "assistant", content: "", sources: [], streaming: true },
          ]
        };
        return newChats;
      });
      
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const onEvent = (e: StreamEvent) => {
        switch (e.type) {
          case "token":
            patchLast((m) => ({ ...m, content: m.content + e.text, status: undefined }));
            break;
          case "tool_call":
            patchLast((m) => ({ ...m, status: statusFor(e.name) }));
            break;
          case "tool_output":
            patchLast((m) => ({ ...m, status: "Reviewing results" }));
            break;
          case "sources":
            patchLast((m) => ({ ...m, sources: e.sources }));
            break;
          case "error":
            patchLast((m) => ({ ...m, error: e.message }));
            break;
          default:
            break;
        }
      };

      try {
        await streamChat(history, onEvent, controller.signal, mode);
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        if (!aborted) {
          const message = err instanceof Error ? err.message : "Request failed.";
          patchLast((m) => ({ ...m, error: message }));
        }
      } finally {
        patchLast((m) => ({ ...m, streaming: false, status: undefined }));
        setBusy(false);
        abortRef.current = null;
      }
    },
    [chats, activeChatId, busy, patchLast, createNewChat, mode],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const clear = useCallback(() => {
    if (activeChatId) {
      setChats(prev => {
        const chatIndex = prev.findIndex(c => c.id === activeChatId);
        if (chatIndex === -1) return prev;
        const newChats = [...prev];
        newChats[chatIndex] = { ...newChats[chatIndex], messages: [] };
        return newChats;
      });
    }
  }, [activeChatId]);

  return { 
    messages, 
    busy, 
    send, 
    stop, 
    clear, 
    mode, 
    setMode,
    chats,
    activeChatId,
    createNewChat,
    selectChat,
    deleteChat
  };
}