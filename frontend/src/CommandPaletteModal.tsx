import { FC, useState, useEffect, useRef } from "react";

export interface CommandItem {
  id: string;
  title: string;
  category: "Studios" | "Operations" | "Voice & Bench" | "Navigation";
  shortcut?: string;
  icon: string;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  commands: CommandItem[];
}

export const CommandPaletteModal: FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  commands,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      window.setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const filtered = commands.filter((c) => {
    const q = query.toLowerCase();
    return (
      c.title.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      (c.shortcut && c.shortcut.toLowerCase().includes(q))
    );
  });

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation inside palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action();
        onClose();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div
        className="command-palette-card"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="command-palette-header">
          <span className="command-palette-icon">⌘</span>
          <input
            ref={inputRef}
            type="text"
            className="command-palette-input"
            placeholder="Type a laboratory command or search studio... (e.g. Plates, SMILES, Digest)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className="command-palette-esc" onClick={onClose}>
            ESC
          </span>
        </div>

        <div className="command-palette-list">
          {filtered.length === 0 ? (
            <div className="command-palette-empty">
              No laboratory actions found matching "<strong>{query}</strong>"
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  className={`command-palette-item ${isSelected ? "selected" : ""}`}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => {
                    item.action();
                    onClose();
                  }}
                >
                  <span className="item-icon">{item.icon}</span>
                  <div className="item-meta">
                    <span className="item-title">{item.title}</span>
                    <span className="item-category">{item.category}</span>
                  </div>
                  {item.shortcut && (
                    <span className="item-shortcut">{item.shortcut}</span>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="command-palette-footer">
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> to navigate
          </span>
          <span>
            <kbd>↵</kbd> to execute
          </span>
          <span>
            <kbd>ESC</kbd> to dismiss
          </span>
          <span className="footer-brand">AURA LAB • FUTURISTIC COMMAND CENTER</span>
        </div>
      </div>
    </div>
  );
};

