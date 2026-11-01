import React, { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface ScientificContentProps {
  content: string;
  className?: string;
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

export function ScientificContent({
  content,
  className = "scientific-content",
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

      // Plain text: preserve whitespace and line breaks
      const paragraphs = token.value.split("\n\n");
      return (
        <React.Fragment key={index}>
          {paragraphs.map((para, pIdx) => {
            const lines = para.split("\n");
            return (
              <span key={pIdx} className="scientific-text">
                {lines.map((line, lIdx) => (
                  <React.Fragment key={lIdx}>
                    {line}
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
  }, [content]);

  return <div className={className}>{rendered}</div>;
}

