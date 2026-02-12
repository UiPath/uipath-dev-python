import { useEffect, useRef } from "react";
import type { WsClient } from "../../api/websocket";
import { useRunStore } from "../../store/useRunStore";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";

interface ChatMsg {
  message_id: string;
  role: string;
  content: string;
  tool_calls?: { name: string; has_result: boolean }[];
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

  // Track whether user has scrolled away from bottom
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    stickToBottom.current = atBottom;
  };

  // Auto-scroll on any message content change (streaming tokens)
  useEffect(() => {
    if (stickToBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  });

  const handleSend = (text: string) => {
    stickToBottom.current = true;
    // Show the user's message immediately
    addLocalChatMessage(runId, {
      message_id: `local-${Date.now()}`,
      role: "user",
      content: text,
    });
    ws.sendChatMessage(runId, text);
  };

  const isDisabled = runStatus === "running";

  return (
    <div className="flex flex-col h-full">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5"
      >
        {messages.length === 0 && (
          <p className="text-[var(--text-muted)] text-xs text-center py-6">
            No messages yet
          </p>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.message_id} message={msg} />
        ))}
      </div>
      <ChatInput
        onSend={handleSend}
        disabled={isDisabled}
        placeholder={isDisabled ? "Waiting for response..." : "Message..."}
      />
    </div>
  );
}
