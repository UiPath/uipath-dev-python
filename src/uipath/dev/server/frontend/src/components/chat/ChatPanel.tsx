import { useEffect, useMemo, useRef, useState } from "react";
import type { WsClient } from "../../api/websocket";
import { useRunStore, type ChatToolCall } from "../../store/useRunStore";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: ChatToolCall[];
}

interface Props {
  messages: ChatMsg[];
  runId: string;
  runStatus: string;
  ws: WsClient;
}

export default function ChatPanel({ messages, runId, runStatus, ws }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const addLocalChatMessage = useRunStore((s) => s.addLocalChatMessage);
  const setFocusedSpan = useRunStore((s) => s.setFocusedSpan);

  // Precompute per-tool-call occurrence indices across all messages
  const toolCallIndicesMap = useMemo(() => {
    const map = new Map<string, number[]>();
    const counts = new Map<string, number>();
    for (const msg of messages) {
      if (msg.tool_calls) {
        const indices: number[] = [];
        for (const tc of msg.tool_calls) {
          const count = counts.get(tc.name) ?? 0;
          indices.push(count);
          counts.set(tc.name, count + 1);
        }
        map.set(msg.message_id, indices);
      }
    }
    return map;
  }, [messages]);

  // True iff there's a pending confirmation we're waiting on
  const awaitingConfirmation = useMemo(
    () =>
      messages.some((m) =>
        (m.tool_calls ?? []).some(
          (tc) => tc.require_confirmation && !tc.confirmation && !tc.has_result,
        ),
      ),
    [messages],
  );

  const [showScrollTop, setShowScrollTop] = useState(false);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    stickToBottom.current = atBottom;
    setShowScrollTop(el.scrollTop > 100);
  };

  useEffect(() => {
    if (stickToBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  });

  const handleSend = (text: string) => {
    stickToBottom.current = true;
    addLocalChatMessage(runId, {
      message_id: `local-${Date.now()}`,
      role: "user",
      content: text,
    });
    ws.sendChatMessage(runId, text);
  };

  const handleConfirmToolCall = (
    toolCallId: string,
    approved: boolean,
    input?: unknown,
  ) => {
    stickToBottom.current = true;
    ws.sendConfirmToolCall(runId, toolCallId, approved, input);
  };

  const isDisabled = runStatus === "running" || awaitingConfirmation;

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex-1 overflow-hidden">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto px-3 py-2 space-y-0.5"
        >
          {messages.length === 0 && (
            <p className="text-[var(--text-muted)] text-sm text-center py-6">
              No messages yet
            </p>
          )}
          {messages.map((msg) => (
            <ChatMessage
              key={msg.message_id}
              message={msg}
              toolCallIndices={toolCallIndicesMap.get(msg.message_id)}
              onToolCallClick={(name, idx) => setFocusedSpan({ name, index: idx })}
              onConfirmToolCall={handleConfirmToolCall}
            />
          ))}
        </div>
        {showScrollTop && (
          <button
            onClick={() => scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
            className="absolute top-2 right-3 w-6 h-6 flex items-center justify-center rounded-full cursor-pointer transition-opacity opacity-70 hover:opacity-100"
            style={{ background: "var(--bg-tertiary)", color: "var(--text-primary)" }}
            title="Scroll to top"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          </button>
        )}
      </div>
      <ChatInput
        onSend={handleSend}
        disabled={isDisabled}
        placeholder={
          awaitingConfirmation
            ? "Approve or reject the tool call above..."
            : isDisabled
              ? "Waiting for response..."
              : "Message..."
        }
      />
    </div>
  );
}
