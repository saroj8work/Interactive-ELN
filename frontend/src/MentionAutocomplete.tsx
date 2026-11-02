import { FC, useEffect, useState, useRef, useCallback } from "react";
import type { InventoryItem, SampleRecord, Experiment } from "./types";

export interface MentionSuggestion {
  id: number;
  type: "inventory" | "sample" | "experiment";
  name: string;
  detail?: string;
  markdown: string;
}

interface MentionAutocompleteProps {
  textareaId: string;
  inventoryItems: InventoryItem[];
  samples: SampleRecord[];
  experiments: Experiment[];
}

export const MentionAutocomplete: FC<MentionAutocompleteProps> = ({
  textareaId,
  inventoryItems,
  samples,
  experiments,
}) => {
  const [active, setActive] = useState(false);
  const [query, setQuery] = useState("");
  const [trigger, setTrigger] = useState<"@" | "#" | "!" | null>(null);
  const [triggerIndex, setTriggerIndex] = useState(-1);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const popoverRef = useRef<HTMLDivElement | null>(null);

  // Compute suggestions based on trigger and query
  const suggestions: MentionSuggestion[] = useMemoSuggestions(
    trigger,
    query,
    inventoryItems,
    samples,
    experiments
  );

  const applySuggestion = useCallback(
    (item: MentionSuggestion) => {
      const textarea = document.getElementById(textareaId) as HTMLTextAreaElement | null;
      if (!textarea) return;

      const fullText = textarea.value;
      const beforeTrigger = fullText.slice(0, triggerIndex);
      const afterCursor = fullText.slice(textarea.selectionEnd);

      const newText = beforeTrigger + item.markdown + " " + afterCursor;
      textarea.value = newText;

      // Dispatch input event so React state / form notices change
      textarea.dispatchEvent(new Event("input", { bubbles: true }));

      // Set cursor right after the mention
      const newCursor = beforeTrigger.length + item.markdown.length + 1;
      textarea.setSelectionRange(newCursor, newCursor);
      textarea.focus();

      setActive(false);
      setTrigger(null);
    },
    [textareaId, triggerIndex]
  );

  useEffect(() => {
    const textarea = document.getElementById(textareaId) as HTMLTextAreaElement | null;
    if (!textarea) return;

    const handleInput = () => {
      const cursorPos = textarea.selectionStart;
      const text = textarea.value.slice(0, cursorPos);

      // Match trigger right before cursor (e.g. "@aspirin", "#sample", "!study")
      const match = text.match(/(?:^|\s)([@#!])([a-zA-Z0-9_\-.\s]{0,30})$/);

      if (match) {
        const symbol = match[1] as "@" | "#" | "!";
        const q = match[2];
        const matchIdx = text.lastIndexOf(symbol);

        setTrigger(symbol);
        setQuery(q.trim().toLowerCase());
        setTriggerIndex(matchIdx);
        setSelectedIndex(0);
        setActive(true);

        // Approximate position below textarea
        const rect = textarea.getBoundingClientRect();
        setCoords({
          top: rect.bottom + window.scrollY - 30,
          left: Math.min(rect.left + 20, window.innerWidth - 320),
        });
      } else {
        setActive(false);
        setTrigger(null);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!active || suggestions.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % suggestions.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        applySuggestion(suggestions[selectedIndex]);
      } else if (e.key === "Escape") {
        setActive(false);
      }
    };

    textarea.addEventListener("input", handleInput);
    textarea.addEventListener("keydown", handleKeyDown);

    return () => {
      textarea.removeEventListener("input", handleInput);
      textarea.removeEventListener("keydown", handleKeyDown);
    };
  }, [textareaId, active, suggestions, selectedIndex, applySuggestion]);

  if (!active || suggestions.length === 0) return null;

  return (
    <div
      ref={popoverRef}
      className="mention-popover"
      style={{
        position: "fixed",
        top: coords.top,
        left: coords.left,
        zIndex: 9999,
      }}
    >
      <div className="mention-popover-header">
        <span>
          {trigger === "@" && "🧪 Mention Reagent"}
          {trigger === "#" && "🧊 Mention Sample"}
          {trigger === "!" && "📓 Mention Experiment"}
        </span>
        <span className="mention-hint">&uarr;&darr; to navigate &bull; Enter to select</span>
      </div>
      <ul className="mention-list">
        {suggestions.map((item, idx) => (
          <li
            key={`${item.type}-${item.id}`}
            className={`mention-item ${idx === selectedIndex ? "selected" : ""}`}
            onMouseDown={(e) => {
              e.preventDefault();
              applySuggestion(item);
            }}
          >
            <div className="mention-item-name">{item.name}</div>
            {item.detail && <div className="mention-item-detail">{item.detail}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
};

function useMemoSuggestions(
  trigger: "@" | "#" | "!" | null,
  query: string,
  inventoryItems: InventoryItem[],
  samples: SampleRecord[],
  experiments: Experiment[]
): MentionSuggestion[] {
  if (!trigger) return [];

  if (trigger === "@") {
    return inventoryItems
      .filter((inv) => !query || inv.name.toLowerCase().includes(query) || inv.category.toLowerCase().includes(query))
      .slice(0, 7)
      .map((inv) => ({
        id: inv.id,
        type: "inventory",
        name: inv.name,
        detail: `${inv.category} • ${inv.quantity} ${inv.unit}`,
        markdown: `[@${inv.name}](#inv:${inv.id})`,
      }));
  }

  if (trigger === "#") {
    return samples
      .filter((smp) => !query || smp.name.toLowerCase().includes(query) || smp.sample_type.toLowerCase().includes(query))
      .slice(0, 7)
      .map((smp) => ({
        id: smp.id,
        type: "sample",
        name: smp.name,
        detail: `${smp.sample_type} • Location: ${smp.storage_location || "Unassigned"}`,
        markdown: `[#${smp.name}](#smp:${smp.id})`,
      }));
  }

  if (trigger === "!") {
    return experiments
      .filter((exp) => !query || exp.name.toLowerCase().includes(query) || exp.status.toLowerCase().includes(query))
      .slice(0, 7)
      .map((exp) => ({
        id: exp.id,
        type: "experiment",
        name: exp.name,
        detail: `Status: ${exp.status}`,
        markdown: `[!${exp.name}](#exp:${exp.id})`,
      }));
  }

  return [];
}
