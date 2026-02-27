import type { ReactNode } from "react";
import type { Section } from "../../hooks/useHashRoute";

interface Props {
  section: Section;
  onSectionChange: (section: Section) => void;
}

const icons: { section: Section; label: string; icon: ReactNode }[] = [
  {
    section: "debug",
    label: "Developer Console",
    icon: (
      // Bug icon
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="8" y="6" width="8" height="14" rx="4" />
        <path d="M6 10H4" />
        <path d="M6 18H4" />
        <path d="M18 10h2" />
        <path d="M18 18h2" />
        <path d="M8 14h8" />
        <path d="M9 6l-1.5-2" />
        <path d="M15 6l1.5-2" />
        <path d="M6 14H4" />
        <path d="M18 14h2" />
      </svg>
    ),
  },
  {
    section: "evals",
    label: "Evals",
    icon: (
      // Beaker/flask icon
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 3h6" />
        <path d="M10 3v6.5L5 20a1 1 0 0 0 .9 1.4h12.2a1 1 0 0 0 .9-1.4L14 9.5V3" />
        <path d="M8.5 14h7" />
      </svg>
    ),
  },
  {
    section: "evaluators",
    label: "Evaluators",
    icon: (
      // Shield-check icon
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l7 4v5c0 5.25-3.5 9.74-7 11-3.5-1.26-7-5.75-7-11V6l7-4z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    section: "explorer",
    label: "Explorer",
    icon: (
      // VS Code codicon "files" — exact icon from microsoft/vscode-codicons
      <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
        <path d="M7.5 22.5H17.595C17.07 23.4 16.11 24 15 24H7.5C4.185 24 1.5 21.315 1.5 18V6C1.5 4.89 2.1 3.93 3 3.405V18C3 20.475 5.025 22.5 7.5 22.5ZM21 8.121V18C21 19.6545 19.6545 21 18 21H7.5C5.8455 21 4.5 19.6545 4.5 18V3C4.5 1.3455 5.8455 0 7.5 0H12.879C13.4715 0 14.0505 0.24 14.4705 0.6585L20.3415 6.5295C20.766 6.954 21 7.5195 21 8.121ZM13.5 6.75C13.5 7.164 13.8375 7.5 14.25 7.5H19.1895L13.5 1.8105V6.75ZM19.5 18V9H14.25C13.0095 9 12 7.9905 12 6.75V1.5H7.5C6.672 1.5 6 2.1735 6 3V18C6 18.8265 6.672 19.5 7.5 19.5H18C18.828 19.5 19.5 18.8265 19.5 18Z" />
      </svg>
    ),
  },
];

export default function ActivityBar({ section, onSectionChange }: Props) {
  return (
    <div
      className="w-12 flex flex-col items-center shrink-0 border-r"
      style={{
        background: "var(--activity-bar-bg)",
        borderColor: "var(--border)",
      }}
    >
      {/* Section icons */}
      <div className="flex flex-col items-center gap-1 pt-2">
        {icons.map((item) => {
          const active = section === item.section;
          return (
            <button
              key={item.section}
              onClick={() => onSectionChange(item.section)}
              className="w-10 h-10 flex items-center justify-center rounded cursor-pointer transition-colors relative"
              style={{
                color: active ? "var(--text-primary)" : "var(--text-muted)",
                background: active ? "var(--bg-hover)" : "transparent",
                border: "none",
              }}
              title={item.label}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.color = "var(--text-secondary)";
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.color = "var(--text-muted)";
              }}
            >
              {active && (
                <div
                  className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r"
                  style={{ background: "var(--accent)" }}
                />
              )}
              {item.icon}
            </button>
          );
        })}
      </div>
    </div>
  );
}
