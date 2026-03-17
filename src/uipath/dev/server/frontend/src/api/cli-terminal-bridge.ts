/**
 * Module-level registry for routing WebSocket PTY output to xterm instances.
 * The CliAgentTerminal component registers its writer on mount and
 * deregisters on unmount.
 */

type TerminalWriter = (data: Uint8Array) => void;

const writers = new Map<string, TerminalWriter>();

export function registerTerminalWriter(sessionId: string, writer: TerminalWriter): void {
  writers.set(sessionId, writer);
}

export function unregisterTerminalWriter(sessionId: string): void {
  writers.delete(sessionId);
}

export function getTerminalWriter(sessionId: string): TerminalWriter | undefined {
  return writers.get(sessionId);
}
