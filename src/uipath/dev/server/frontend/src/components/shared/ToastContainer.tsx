import { useToastStore } from "../../store/useToastStore";

const typeStyles: Record<string, { color: string; bg: string; border: string }> = {
  success: {
    color: "var(--success)",
    bg: "color-mix(in srgb, var(--success) 10%, var(--bg-elevated))",
    border: "color-mix(in srgb, var(--success) 30%, var(--border))",
  },
  error: {
    color: "var(--error)",
    bg: "color-mix(in srgb, var(--error) 10%, var(--bg-elevated))",
    border: "color-mix(in srgb, var(--error) 30%, var(--border))",
  },
  info: {
    color: "var(--info)",
    bg: "color-mix(in srgb, var(--info) 10%, var(--bg-elevated))",
    border: "color-mix(in srgb, var(--info) 30%, var(--border))",
  },
};

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-8 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => {
        const style = typeStyles[toast.type] ?? typeStyles.info;
        return (
          <div
            key={toast.id}
            className="pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium max-w-xs animate-[slideIn_0.2s_ease-out]"
            style={{
              background: style.bg,
              border: `1px solid ${style.border}`,
              color: style.color,
            }}
          >
            <span className="flex-1">{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 w-5 h-5 flex items-center justify-center rounded cursor-pointer transition-opacity opacity-60 hover:opacity-100"
              style={{ color: style.color, background: "transparent", border: "none" }}
              aria-label="Dismiss"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <line x1="1" y1="1" x2="9" y2="9" />
                <line x1="9" y1="1" x2="1" y2="9" />
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}
