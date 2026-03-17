import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { getWs } from "../../store/useWebSocket";
import { registerTerminalWriter, unregisterTerminalWriter } from "../../api/cli-terminal-bridge";

interface Props {
  sessionId: string;
}

export default function CliAgentTerminal({ sessionId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const ws = useRef(getWs()).current;

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace",
      theme: {
        background: "#0f172a",
        foreground: "#e2e8f0",
        cursor: "#7dd3fc",
        selectionBackground: "#334155",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    // Register writer for WebSocket PTY output
    registerTerminalWriter(sessionId, (data) => term.write(data));

    // Clipboard support:
    // - Cmd+C / Ctrl+C (with selection) = copy
    // - Cmd+V / Ctrl+V = paste
    // - Ctrl+Shift+C/V = also copy/paste (Linux convention)
    // - Ctrl+C with no selection = send SIGINT (default terminal behavior)
    const isMac = navigator.platform.startsWith("Mac");
    term.attachCustomKeyEventHandler((ev) => {
      const mod = isMac ? ev.metaKey : ev.ctrlKey;

      // Copy: Cmd/Ctrl+C or Ctrl+Shift+C
      if ((mod && ev.key === "c") || (ev.ctrlKey && ev.shiftKey && ev.key === "C")) {
        const sel = term.getSelection();
        if (sel) {
          navigator.clipboard.writeText(sel);
          return false;
        }
        // No selection + Ctrl+C on non-Mac: let it through as SIGINT
        if (!isMac) return true;
        return false;
      }

      // Paste: Cmd/Ctrl+V or Ctrl+Shift+V
      if ((mod && ev.key === "v") || (ev.ctrlKey && ev.shiftKey && ev.key === "V")) {
        navigator.clipboard.readText().then((text) => {
          if (text) ws.sendCliAgentInput(sessionId, text);
        });
        return false;
      }

      return true;
    });

    // Forward user keystrokes to backend
    term.onData((data) => {
      ws.sendCliAgentInput(sessionId, data);
    });

    // Handle resize
    const observer = new ResizeObserver(() => {
      fit.fit();
      ws.sendCliAgentResize(sessionId, term.cols, term.rows);
    });
    observer.observe(containerRef.current);

    // Send initial size
    ws.sendCliAgentResize(sessionId, term.cols, term.rows);

    return () => {
      unregisterTerminalWriter(sessionId);
      observer.disconnect();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [sessionId, ws]);

  return (
    <div
      ref={containerRef}
      className="flex-1 min-h-0"
      style={{ padding: "4px" }}
    />
  );
}
