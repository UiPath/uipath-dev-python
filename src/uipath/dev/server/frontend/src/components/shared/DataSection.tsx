import { useCallback, useState } from "react";

export default function DataSection({
  title,
  copyText,
  trailing,
  children,
}: {
  title: string;
  copyText?: string;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    if (!copyText) return;
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [copyText]);

  return (
    <div className="overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <div className="px-3 py-2 flex items-center gap-2" style={{ background: "var(--bg-secondary)" }}>
        <span className="text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>{title}</span>
        {trailing}
        {copyText && (
          <button
            onClick={copy}
            className={`${trailing ? "" : "ml-auto "}text-[10px] cursor-pointer px-1.5 py-0.5 rounded transition-colors`}
            style={{
              color: copied ? "var(--success)" : "var(--text-muted)",
              background: "var(--bg-tertiary)",
              border: "none",
            }}
            onMouseEnter={(e) => { if (!copied) e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = copied ? "var(--success)" : "var(--text-muted)"; }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
