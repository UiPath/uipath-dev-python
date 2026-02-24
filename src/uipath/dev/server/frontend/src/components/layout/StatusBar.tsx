import { useState, useRef, useEffect } from "react";
import { useAuthStore } from "../../store/useAuthStore";
import { useConfigStore } from "../../store/useConfigStore";
import { useTheme } from "../../store/useTheme";

export default function StatusBar() {
  const { theme, toggleTheme } = useTheme();
  const { enabled, status, environment, tenants, uipathUrl, setEnvironment, startLogin, selectTenant, logout } = useAuthStore();
  const { projectName, projectVersion, projectAuthors } = useConfigStore();
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState("");
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click
  useEffect(() => {
    if (!popoverOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (
        popoverRef.current && !popoverRef.current.contains(e.target as Node) &&
        triggerRef.current && !triggerRef.current.contains(e.target as Node)
      ) {
        setPopoverOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [popoverOpen]);

  const isAuthenticated = status === "authenticated";
  const isExpired = status === "expired";
  const isPending = status === "pending";
  const needsTenant = status === "needs_tenant";

  // Build label + icon
  let label = "UiPath: Disconnected";
  let dotColor: string | null = null;
  let lockIcon = true;

  if (isAuthenticated) {
    const shortUrl = uipathUrl ? uipathUrl.replace(/^https?:\/\/[^/]+\//, "") : "";
    label = `UiPath: ${shortUrl}`;
    dotColor = "var(--success)";
    lockIcon = false;
  } else if (isExpired) {
    const shortUrl = uipathUrl ? uipathUrl.replace(/^https?:\/\/[^/]+\//, "") : "";
    label = `UiPath: ${shortUrl} (expired)`;
    dotColor = "var(--error)";
    lockIcon = false;
  } else if (isPending) {
    label = "UiPath: Signing in\u2026";
  } else if (needsTenant) {
    label = "UiPath: Select Tenant";
  }

  const handleClick = () => {
    if (isPending) return;
    if (isExpired) {
      startLogin();
    } else {
      setPopoverOpen((v) => !v);
    }
  };

  const itemClass = "flex items-center gap-1 px-1.5 rounded transition-colors";
  const hoverHandlers = {
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => { e.currentTarget.style.background = ""; e.currentTarget.style.color = "var(--text-muted)"; },
  };

  return (
    <div
      className="h-6 flex items-center justify-end gap-3 px-2 text-xs border-t shrink-0"
      style={{
        background: "var(--bg-secondary)",
        color: "var(--text-muted)",
        borderColor: "var(--border)",
        fontSize: "11px",
      }}
    >
      {/* Auth status */}
      {enabled && (
        <div className="relative flex items-center">
          <div
            ref={triggerRef}
            className={`${itemClass} cursor-pointer`}
            onClick={handleClick}
            {...hoverHandlers}
            title={
              isAuthenticated ? uipathUrl ?? ""
              : isExpired ? "Token expired \u2014 click to re-authenticate"
              : isPending ? "Signing in\u2026"
              : needsTenant ? "Select a tenant"
              : "Click to sign in"
            }
          >
            {isPending ? (
              <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
              </svg>
            ) : dotColor ? (
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: dotColor }} />
            ) : lockIcon ? (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 9.9-1" />
              </svg>
            ) : null}
            <span className="truncate max-w-[200px]">{label}</span>
          </div>

          {/* Popover */}
          {popoverOpen && (
            <div
              ref={popoverRef}
              className="absolute bottom-full right-0 mb-1 rounded border shadow-lg p-1 min-w-[180px]"
              style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}
            >
              {(isAuthenticated || isExpired) ? (
                <>
                  <button
                    onClick={() => { if (uipathUrl) window.open(uipathUrl, "_blank", "noopener,noreferrer"); setPopoverOpen(false); }}
                    className="w-full flex items-center gap-2 px-2 py-2 text-[11px] rounded cursor-pointer transition-colors text-left"
                    style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-muted)"; }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                    Go to Platform
                  </button>
                  <button
                    onClick={() => { logout(); setPopoverOpen(false); }}
                    className="w-full flex items-center gap-2 px-2 py-2 text-[11px] rounded cursor-pointer transition-colors text-left"
                    style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-muted)"; }}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                    Sign Out
                  </button>
                </>
              ) : needsTenant ? (
                <div className="p-1">
                  <label className="block text-[10px] font-medium mb-1" style={{ color: "var(--text-muted)" }}>Tenant</label>
                  <select
                    value={selectedTenant}
                    onChange={(e) => setSelectedTenant(e.target.value)}
                    className="w-full rounded px-1.5 py-1 text-[10px] mb-1.5 appearance-auto"
                    style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                  >
                    <option value="">Select&hellip;</option>
                    {tenants.map((t) => (<option key={t} value={t}>{t}</option>))}
                  </select>
                  <button
                    onClick={() => { if (selectedTenant) { selectTenant(selectedTenant); setPopoverOpen(false); } }}
                    disabled={!selectedTenant}
                    className="w-full px-2 py-1 text-[10px] font-medium rounded border border-[var(--border)] bg-transparent cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ color: "var(--text-muted)" }}
                  >
                    Confirm
                  </button>
                </div>
              ) : (
                <div className="p-1">
                  <label className="block text-[10px] font-medium mb-1" style={{ color: "var(--text-muted)" }}>Environment</label>
                  <select
                    value={environment}
                    onChange={(e) => setEnvironment(e.target.value as "cloud" | "staging" | "alpha")}
                    className="w-full rounded px-1.5 py-0.5 text-[10px] mb-1.5 appearance-auto"
                    style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-muted)" }}
                  >
                    <option value="cloud">cloud</option>
                    <option value="staging">staging</option>
                    <option value="alpha">alpha</option>
                  </select>
                  <button
                    onClick={() => { startLogin(); setPopoverOpen(false); }}
                    className="w-full px-2 py-1 text-[10px] font-medium rounded border border-[var(--border)] bg-transparent cursor-pointer transition-colors"
                    style={{ color: "var(--text-muted)" }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.borderColor = "var(--text-muted)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border)"; }}
                  >
                    Sign In
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Project name */}
      {projectName && (
        <span className={itemClass}>Project: {projectName}</span>
      )}

      {/* Project version */}
      {projectVersion && (
        <span className={itemClass}>Version: v{projectVersion}</span>
      )}

      {/* Project author */}
      {projectAuthors && (
        <span className={itemClass}>Author: {projectAuthors}</span>
      )}

      {/* GitHub */}
      <a
        href="https://github.com/UiPath/uipath-dev-python"
        target="_blank"
        rel="noopener noreferrer"
        className={`${itemClass} cursor-pointer no-underline`}
        style={{ color: "var(--text-muted)" }}
        {...hoverHandlers}
        title="View on GitHub"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
        </svg>
        <span>uipath-dev-python</span>
      </a>

      {/* Theme toggle */}
      <div
        className={`${itemClass} cursor-pointer`}
        onClick={toggleTheme}
        {...hoverHandlers}
        title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {theme === "dark" ? (
            <><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></>
          ) : (
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          )}
        </svg>
        <span>{theme === "dark" ? "Dark" : "Light"}</span>
      </div>
    </div>
  );
}
