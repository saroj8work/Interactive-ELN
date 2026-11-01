import React, { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

export interface ScientificContentProps {
  content: string;
  className?: string;
  onNavigate?: (kind: "inventory" | "sample" | "experiment", id: number) => void;
}

type Token =
  | { type: "block-math"; value: string }
  | { type: "inline-math"; value: string }
  | { type: "text"; value: string };

function tokenizeScientificContent(text: string): Token[] {
  const tokens: Token[] = [];
  // Regex to match block math $$...$$ first, then inline math $...$
  const regex = /(\$\$[\s\S]*?\$\$|\$(?:\\.|[^\$\\\n])+\$)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    const tokenStr = match[0];
    if (tokenStr.startsWith("$$") && tokenStr.endsWith("$$")) {
      tokens.push({
        type: "block-math",
        value: tokenStr.slice(2, -2).trim(),
      });
    } else if (tokenStr.startsWith("$") && tokenStr.endsWith("$")) {
      tokens.push({
        type: "inline-math",
        value: tokenStr.slice(1, -1).trim(),
      });
    }
    lastIndex = match.index + tokenStr.length;
  }

  if (lastIndex < text.length) {
    tokens.push({ type: "text", value: text.slice(lastIndex) });
  }

  return tokens;
}

// Helper to render text with inline @inventory, #sample, !experiment links
function renderTextWithMentions(
  line: string,
  onNavigate?: (kind: "inventory" | "sample" | "experiment", id: number) => void
) {
  // Regex to match [@Name](#inv:123), [#Name](#smp:123), [!Name](#exp:123)
  const mentionRegex = /\[([@#!])([^\]]+)\]\(#(inv|smp|exp):(\d+)\)/g;
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let m: RegExpExecArray | null;

  while ((m = mentionRegex.exec(line)) !== null) {
    if (m.index > lastIdx) {
      parts.push(line.slice(lastIdx, m.index));
    }
    const prefix = m[1];
    const label = m[2];
    const targetType = m[3];
    const targetId = parseInt(m[4], 10);

    let kind: "inventory" | "sample" | "experiment" = "inventory";
    let icon = "🧪";
    let pillClass = "mention-pill-inventory";

    if (prefix === "#" || targetType === "smp") {
      kind = "sample";
      icon = "🧬";
      pillClass = "mention-pill-sample";
    } else if (prefix === "!" || targetType === "exp") {
      kind = "experiment";
      icon = "📓";
      pillClass = "mention-pill-exp";
    }

    parts.push(
      <span
        key={`mention-${m.index}`}
        className={`mention-pill ${pillClass}`}
        title={`Click to open ${kind} #${targetId}`}
        onClick={() => onNavigate?.(kind, targetId)}
        role="button"
        tabIndex={0}
      >
        <span>{icon}</span>
        <span>{label}</span>
      </span>
    );
    lastIdx = m.index + m[0].length;
  }

  if (lastIdx < line.length) {
    parts.push(line.slice(lastIdx));
  }

  return parts;
}

export function ScientificContent({
  content,
  className = "scientific-content",
  onNavigate,
}: ScientificContentProps) {
  const rendered = useMemo(() => {
    if (!content.trim()) {
      return <p className="empty-hint">No content to display.</p>;
    }

    const tokens = tokenizeScientificContent(content);

    return tokens.map((token, index) => {
      if (token.type === "block-math") {
        try {
          const html = katex.renderToString(token.value, {
            displayMode: true,
            throwOnError: false,
          });
          return (
            <div
              key={index}
              className="scientific-math-block"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        } catch {
          return (
            <pre key={index} className="math-error">
              $${token.value}$$
            </pre>
          );
        }
      }

      if (token.type === "inline-math") {
        try {
          const html = katex.renderToString(token.value, {
            displayMode: false,
            throwOnError: false,
          });
          return (
            <span
              key={index}
              className="scientific-math-inline"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        } catch {
          return (
            <code key={index} className="math-error">
              ${token.value}$
            </code>
          );
        }
      }

      // Plain text: preserve whitespace, line breaks, and parse @/#/! mentions
      const paragraphs = token.value.split("\n\n");
      return (
        <React.Fragment key={index}>
          {paragraphs.map((para, pIdx) => {
            const lines = para.split("\n");
            return (
              <span key={pIdx} className="scientific-text">
                {lines.map((line, lIdx) => (
                  <React.Fragment key={lIdx}>
                    {renderTextWithMentions(line, onNavigate)}
                    {lIdx < lines.length - 1 && <br />}
                  </React.Fragment>
                ))}
                {pIdx < paragraphs.length - 1 && <br className="paragraph-break" />}
              </span>
            );
          })}
        </React.Fragment>
      );
    });
  }, [content, onNavigate]);

  return <div className={className}>{rendered}</div>;
}
