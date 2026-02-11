import { useEffect, useRef } from "react";
import type { WsClient } from "../../api/websocket";
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

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length]);

  const handleSend = (text: string) => {
    ws.sendChatMessage(runId, text);
  };

  const isDisabled = runStatus === "running";

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-[var(--text-muted)] text-sm text-center py-8">
            No messages yet. Type below to start chatting.
          </p>
        )}
        {messages.map((msg) => (
          <ChatMessage key={msg.message_id} message={msg} />
        ))}
      </div>
      <ChatInput onSend={handleSend} disabled={isDisabled} />
    </div>
  );
}
