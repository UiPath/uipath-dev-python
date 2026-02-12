import { useMemo } from "react";

interface Token {
  type: "key" | "string" | "number" | "boolean" | "null" | "punctuation";
  text: string;
}

const TOKEN_COLORS: Record<Token["type"], string> = {
  key: "var(--info)",
  string: "var(--success)",
  number: "var(--warning)",
  boolean: "var(--accent)",
  null: "var(--accent)",
  punctuation: "var(--text-muted)",
};

// Tokenize a pre-formatted JSON string into colored spans
function tokenize(json: string): Token[] {
  const tokens: Token[] = [];
  // Match JSON tokens: strings, numbers, booleans, null, punctuation
  const re = /("(?:[^"\\]|\\.)*")\s*:|("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b|(true|false)\b|(null)\b|([{}[\]:,])/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(json)) !== null) {
    // Whitespace between tokens
    if (m.index > lastIndex) {
      tokens.push({ type: "punctuation", text: json.slice(lastIndex, m.index) });
    }

    if (m[1] !== undefined) {
      // Key (string followed by colon)
      tokens.push({ type: "key", text: m[1] });
      // Find the colon after the key
      const colonIdx = json.indexOf(":", m.index + m[1].length);
      if (colonIdx !== -1) {
        // Add any whitespace between key and colon
        if (colonIdx > m.index + m[1].length) {
          tokens.push({ type: "punctuation", text: json.slice(m.index + m[1].length, colonIdx) });
        }
        tokens.push({ type: "punctuation", text: ":" });
        re.lastIndex = colonIdx + 1;
      }
    } else if (m[2] !== undefined) {
      tokens.push({ type: "string", text: m[2] });
    } else if (m[3] !== undefined) {
      tokens.push({ type: "number", text: m[3] });
    } else if (m[4] !== undefined) {
      tokens.push({ type: "boolean", text: m[4] });
    } else if (m[5] !== undefined) {
      tokens.push({ type: "null", text: m[5] });
    } else if (m[6] !== undefined) {
      tokens.push({ type: "punctuation", text: m[6] });
    }

    lastIndex = re.lastIndex;
  }

  // Trailing whitespace
  if (lastIndex < json.length) {
    tokens.push({ type: "punctuation", text: json.slice(lastIndex) });
  }

  return tokens;
}

interface Props {
  json: string;
  className?: string;
  style?: React.CSSProperties;
}

export default function JsonHighlight({ json, className, style }: Props) {
  const tokens = useMemo(() => tokenize(json), [json]);

  return (
    <pre className={className} style={style}>
      {tokens.map((t, i) => (
        <span key={i} style={{ color: TOKEN_COLORS[t.type] }}>
          {t.text}
        </span>
      ))}
    </pre>
  );
}
