import { useCallback, useEffect, useRef, useState } from "react";
import { useAgentStore } from "../../store/useAgentStore";
import { useAuthStore } from "../../store/useAuthStore";
import { listAgentModels, listAgentSkills } from "../../api/agent-client";
import { getWs } from "../../store/useWebSocket";
import AgentMessageComponent from "./AgentMessage";
import type { AgentSkill } from "../../types/agent";

export default function AgentChatSidebar() {
  const ws = useRef(getWs()).current;
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const authEnabled = useAuthStore((s) => s.enabled);
  const authStatus = useAuthStore((s) => s.status);
  const isAuthenticated = !authEnabled || authStatus === "authenticated";

  const {
    sessionId,
    status,
    messages,
    models,
    selectedModel,
    modelsLoading,
    skills,
    selectedSkillIds,
    skillsLoading,
    setModels,
    setSelectedModel,
    setModelsLoading,
    setSkills,
    setSelectedSkillIds,
    toggleSkill,
    setSkillsLoading,
    addUserMessage,
    clearSession,
  } = useAgentStore();

  // Load models on mount if authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    if (models.length > 0) return;
    setModelsLoading(true);
    listAgentModels()
      .then((m) => {
        setModels(m);
        if (m.length > 0 && !selectedModel) {
          const claude = m.find((x) => x.model_name.includes("claude"));
          setSelectedModel(claude ? claude.model_name : m[0].model_name);
        }
      })
      .catch(console.error)
      .finally(() => setModelsLoading(false));
  }, [isAuthenticated, models.length, selectedModel, setModels, setSelectedModel, setModelsLoading]);

  // Load skills on mount
  useEffect(() => {
    if (skills.length > 0) return;
    setSkillsLoading(true);
    listAgentSkills()
      .then((s) => {
        setSkills(s);
        setSelectedSkillIds(s.map((sk) => sk.id));
      })
      .catch(console.error)
      .finally(() => setSkillsLoading(false));
  }, [skills.length, setSkills, setSelectedSkillIds, setSkillsLoading]);

  const [showScrollTop, setShowScrollTop] = useState(false);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    stickToBottom.current = atBottom;
    setShowScrollTop(el.scrollTop > 100);
  };

  // Auto-scroll on any message content change (streaming tokens)
  useEffect(() => {
    if (stickToBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  });

  const isBusy = status === "thinking" || status === "executing" || status === "planning";

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || !selectedModel || isBusy) return;
    stickToBottom.current = true;
    addUserMessage(text);
    ws.sendAgentMessage(text, selectedModel, sessionId, selectedSkillIds);
    setInput("");
  }, [input, selectedModel, isBusy, sessionId, selectedSkillIds, addUserMessage, ws]);

  const handleStop = useCallback(() => {
    if (sessionId) ws.sendAgentStop(sessionId);
  }, [sessionId, ws]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = !isBusy && !!selectedModel && input.trim().length > 0;

  // Auth gate
  if (!isAuthenticated) {
    return (
      <div className="flex flex-col h-full" style={{ background: "var(--bg-primary)" }}>
        <Header
          selectedModel={selectedModel}
          models={models}
          modelsLoading={modelsLoading}
          onModelChange={setSelectedModel}
          skills={skills}
          selectedSkillIds={selectedSkillIds}
          skillsLoading={skillsLoading}
          onToggleSkill={toggleSkill}
          onClear={clearSession}
          onStop={handleStop}
          hasMessages={false}
          isBusy={false}
        />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center" style={{ color: "var(--text-muted)" }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-2" strokeLinecap="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <p className="text-sm font-medium mb-1">Sign in to use Agent</p>
            <p className="text-xs">Authentication is required to access the coding agent.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg-primary)" }}>
      <Header
        selectedModel={selectedModel}
        models={models}
        modelsLoading={modelsLoading}
        onModelChange={setSelectedModel}
        skills={skills}
        selectedSkillIds={selectedSkillIds}
        skillsLoading={skillsLoading}
        onToggleSkill={toggleSkill}
        onClear={clearSession}
        onStop={handleStop}
        hasMessages={messages.length > 0}
        isBusy={isBusy}
      />

      {/* Messages */}
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
            <AgentMessageComponent key={msg.id} message={msg} />
          ))}
          {isBusy && (
            <div className="py-1.5">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: "var(--success)" }} />
                <span className="text-[11px] font-semibold" style={{ color: "var(--success)" }}>
                  {status === "thinking" ? "Thinking..." : status === "executing" ? "Executing..." : "Planning..."}
                </span>
              </div>
            </div>
          )}
        </div>
        {showScrollTop && (
          <button
            onClick={() => { stickToBottom.current = false; scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" }); }}
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

      {/* Input — matches ChatInput from debug view */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-t"
        style={{ borderColor: "var(--border)" }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isBusy || !selectedModel}
          placeholder={isBusy ? "Waiting for response..." : "Message..."}
          className="flex-1 bg-transparent text-sm py-1 disabled:opacity-40 placeholder:text-[var(--text-muted)]"
          style={{ color: "var(--text-primary)" }}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className="text-xs font-semibold px-3 py-1.5 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Send message"
          style={{
            color: canSend ? "var(--accent)" : "var(--text-muted)",
            background: "transparent",
          }}
          onMouseEnter={(e) => {
            if (canSend) {
              e.currentTarget.style.background = "color-mix(in srgb, var(--accent) 10%, transparent)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

function Header({
  selectedModel,
  models,
  modelsLoading,
  onModelChange,
  skills,
  selectedSkillIds,
  skillsLoading,
  onToggleSkill,
  onClear,
  onStop,
  hasMessages,
  isBusy,
}: {
  selectedModel: string | null;
  models: { model_name: string; vendor: string | null }[];
  modelsLoading: boolean;
  onModelChange: (model: string) => void;
  skills: AgentSkill[];
  selectedSkillIds: string[];
  skillsLoading: boolean;
  onToggleSkill: (id: string) => void;
  onClear: () => void;
  onStop: () => void;
  hasMessages: boolean;
  isBusy: boolean;
}) {
  const [skillsOpen, setSkillsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!skillsOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setSkillsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [skillsOpen]);

  return (
    <div
      className="shrink-0 flex items-center gap-2 px-3 h-10 border-b"
      style={{ borderColor: "var(--border)", background: "var(--bg-primary)" }}
    >
      <span className="text-[11px] uppercase tracking-wider font-semibold shrink-0" style={{ color: "var(--text-muted)" }}>
        Agent
      </span>
      <select
        value={selectedModel ?? ""}
        onChange={(e) => onModelChange(e.target.value)}
        className="flex-1 text-[11px] rounded px-1.5 py-1 outline-none min-w-0 cursor-pointer"
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          color: "var(--text-primary)",
        }}
        disabled={modelsLoading}
      >
        {modelsLoading && <option value="">Loading models...</option>}
        {!modelsLoading && models.length === 0 && <option value="">No models</option>}
        {models.map((m) => (
          <option key={m.model_name} value={m.model_name}>
            {m.model_name}
          </option>
        ))}
      </select>
      {/* Skills dropdown */}
      {!skillsLoading && skills.length > 0 && (
        <div className="relative shrink-0" ref={dropdownRef}>
          <button
            onClick={() => setSkillsOpen(!skillsOpen)}
            className="text-[11px] font-semibold px-2 py-1 rounded cursor-pointer flex items-center gap-1"
            style={{
              background: selectedSkillIds.length > 0 ? "color-mix(in srgb, var(--accent) 15%, transparent)" : "transparent",
              border: `1px solid ${selectedSkillIds.length > 0 ? "var(--accent)" : "var(--border)"}`,
              color: selectedSkillIds.length > 0 ? "var(--accent)" : "var(--text-muted)",
            }}
            title="Skills"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
            {selectedSkillIds.length > 0 && <span>{selectedSkillIds.length}</span>}
          </button>
          {skillsOpen && (
            <div
              className="absolute top-full right-0 mt-1 rounded shadow-lg z-50 py-1 max-h-64 overflow-y-auto"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", width: "190px" }}
            >
              {skills.map((s) => (
                <button
                  key={s.id}
                  onClick={() => onToggleSkill(s.id)}
                  className="w-full text-left px-2 py-1 text-[11px] flex items-center gap-1.5 cursor-pointer"
                  style={{ color: "var(--text-primary)" }}
                  title={s.description}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-tertiary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <span
                    className="w-3 h-3 rounded border flex items-center justify-center shrink-0"
                    style={{
                      borderColor: selectedSkillIds.includes(s.id) ? "var(--accent)" : "var(--border)",
                      background: selectedSkillIds.includes(s.id) ? "var(--accent)" : "transparent",
                    }}
                  >
                    {selectedSkillIds.includes(s.id) && (
                      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </span>
                  <span className="truncate">{s.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {isBusy && (
        <button
          onClick={onStop}
          className="shrink-0 text-[11px] font-semibold px-2 py-1 rounded cursor-pointer"
          style={{ background: "transparent", border: "1px solid var(--error)", color: "var(--error)" }}
          title="Stop"
          onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--error) 10%, transparent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          Stop
        </button>
      )}
      {hasMessages && !isBusy && (
        <button
          onClick={onClear}
          className="shrink-0 w-6 h-6 flex items-center justify-center rounded cursor-pointer"
          style={{ background: "transparent", border: "none", color: "var(--text-muted)" }}
          title="New session"
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
        </button>
      )}
    </div>
  );
}
