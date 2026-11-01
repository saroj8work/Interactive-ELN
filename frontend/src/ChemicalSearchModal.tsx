import { useState, useMemo } from "react";
import type { InventoryItem, Experiment, NotebookEntry } from "./types";
import {
  COMMON_FUNCTIONAL_GROUPS,
  isSubstructure,
  calculateTanimotoSimilarity,
  type ChemicalSearchResult,
} from "./chemicalSearchUtils";

interface ChemicalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectResult: (type: "experiment" | "entry" | "inventory", id: number) => void;
  inventoryItems: InventoryItem[];
  experiments?: Experiment[];
  entries: NotebookEntry[];
}

export function ChemicalSearchModal({
  isOpen,
  onClose,
  onSelectResult,
  inventoryItems,
  entries,
}: ChemicalSearchModalProps) {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"substructure" | "similarity">("substructure");
  const [similarityThreshold, setSimilarityThreshold] = useState(40); // 40%

  const results: ChemicalSearchResult[] = useMemo(() => {
    const trimmed = query.trim();
    if (!trimmed) return [];

    const matches: ChemicalSearchResult[] = [];

    // Search Inventory items
    inventoryItems.forEach((item) => {
      const candidates = [
        item.name,
        item.catalog_number,
        item.notes,
        ...Object.values(item.custom_fields || {}),
      ];

      for (const text of candidates) {
        if (!text) continue;
        const subMatch = isSubstructure(trimmed, text);
        const sim = calculateTanimotoSimilarity(trimmed, text) * 100;

        if (
          (searchMode === "substructure" && subMatch) ||
          (searchMode === "similarity" && sim >= similarityThreshold)
        ) {
          matches.push({
            id: `inv-${item.id}`,
            type: "inventory",
            title: item.name,
            formula: item.catalog_number ? `Cat #${item.catalog_number}` : undefined,
            isSubstructureMatch: subMatch,
            similarityScore: Math.round(sim),
            referenceId: item.id,
          });
          break;
        }
      }
    });

    // Search Experiment Entries
    entries.forEach((entry) => {
      const text = `${entry.title || ""} ${entry.content || ""}`;
      const subMatch = isSubstructure(trimmed, text);
      const sim = calculateTanimotoSimilarity(trimmed, text) * 100;

      if (
        (searchMode === "substructure" && subMatch) ||
        (searchMode === "similarity" && sim >= similarityThreshold)
      ) {
        matches.push({
          id: `entry-${entry.id}`,
          type: "entry",
          title: entry.title || `Entry #${entry.id}`,
          isSubstructureMatch: subMatch,
          similarityScore: Math.round(sim),
          referenceId: entry.experiment_id,
        });
      }
    });

    // Sort: Substructure matches first, then highest similarity score
    return matches.sort((a, b) => {
      if (a.isSubstructureMatch && !b.isSubstructureMatch) return -1;
      if (!a.isSubstructureMatch && b.isSubstructureMatch) return 1;
      return b.similarityScore - a.similarityScore;
    });
  }, [query, searchMode, similarityThreshold, inventoryItems, entries]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="chem-search-title">
      <div className="modal" style={{ maxWidth: 640 }}>
        <header className="modal-header">
          <div>
            <h2 id="chem-search-title" style={{ display: "flex", alignItems: "center", gap: 8, margin: 0, color: "#3F1899" }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              Chemical Substructure & Similarity Search
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "#6b5f88" }}>
              Find molecules, functional groups, and similar chemical structures across entries and inventory.
            </p>
          </div>
          <button className="button-icon" type="button" onClick={onClose} aria-label="Close search">
            ✕
          </button>
        </header>

        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Query input */}
          <div>
            <label htmlFor="chem-query-input" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#3F1899", marginBottom: 6 }}>
              Query Structure (SMILES, Formula, or Group)
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                id="chem-query-input"
                type="text"
                placeholder="e.g. c1ccccc1, C(=O)O, C6H6, or Benzene"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1, padding: "8px 12px", border: "1px solid #d8c8f7", borderRadius: 6 }}
                autoFocus
              />
              {query && (
                <button
                  type="button"
                  className="button button-outline"
                  onClick={() => setQuery("")}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Quick Functional Group Filter Chips */}
          <div>
            <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "#6b5f88", textTransform: "uppercase" }}>
              Quick Functional Groups:
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
              {COMMON_FUNCTIONAL_GROUPS.map((fg) => (
                <button
                  key={fg.name}
                  type="button"
                  className="tag-badge"
                  style={{
                    cursor: "pointer",
                    background: query.toLowerCase() === fg.smiles.toLowerCase() ? "#3F1899" : "#ece5fc",
                    color: query.toLowerCase() === fg.smiles.toLowerCase() ? "#ffffff" : "#3F1899",
                    border: "1px solid #d8c8f7",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontSize: "0.78rem",
                  }}
                  onClick={() => setQuery(fg.smiles)}
                  title={fg.description}
                >
                  {fg.name}
                </button>
              ))}
            </div>
          </div>

          {/* Search Mode & Threshold */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#fbf9ff",
            padding: "8px 12px",
            border: "1px solid #e8e0f7",
            borderRadius: 6,
          }}>
            <div style={{ display: "flex", gap: 12 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.82rem", cursor: "pointer", color: "#1f1538" }}>
                <input
                  type="radio"
                  name="chemSearchMode"
                  checked={searchMode === "substructure"}
                  onChange={() => setSearchMode("substructure")}
                />
                Substructure Match
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.82rem", cursor: "pointer", color: "#1f1538" }}>
                <input
                  type="radio"
                  name="chemSearchMode"
                  checked={searchMode === "similarity"}
                  onChange={() => setSearchMode("similarity")}
                />
                Tanimoto Similarity
              </label>
            </div>

            {searchMode === "similarity" && (
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: "0.75rem", color: "#6b5f88" }}>Threshold: {similarityThreshold}%</span>
                <input
                  type="range"
                  min="20"
                  max="90"
                  step="5"
                  value={similarityThreshold}
                  onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
                  style={{ width: 80 }}
                />
              </div>
            )}
          </div>

          {/* Results List */}
          <div style={{ minHeight: 180, maxHeight: 300, overflowY: "auto", display: "grid", gap: 8 }}>
            {!query.trim() ? (
              <p style={{ textAlign: "center", color: "#6b5f88", fontSize: "0.85rem", marginTop: 40 }}>
                Type a SMILES formula or click a functional group above to search.
              </p>
            ) : results.length === 0 ? (
              <p style={{ textAlign: "center", color: "#6b5f88", fontSize: "0.85rem", marginTop: 40 }}>
                No matching chemical structures found in active entries or inventory items.
              </p>
            ) : (
              results.map((res) => (
                <div
                  key={res.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: "#ffffff",
                    border: "1px solid #d8c8f7",
                    borderRadius: 6,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      background: res.type === "inventory" ? "#ece5fc" : "#fdf5e6",
                      color: res.type === "inventory" ? "#3F1899" : "#92540c",
                    }}>
                      {res.type === "inventory" ? "🧪 Inventory" : "📓 Entry"}
                    </span>
                    <div>
                      <strong style={{ fontSize: "0.9rem", color: "#1f1538" }}>{res.title}</strong>
                      {res.formula && (
                        <div style={{ fontSize: "0.75rem", color: "#6b5f88" }}>{res.formula}</div>
                      )}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {res.isSubstructureMatch ? (
                      <span style={{ fontSize: "0.75rem", color: "#22c55e", fontWeight: 700 }}>
                        ✓ Substructure
                      </span>
                    ) : (
                      <span style={{ fontSize: "0.75rem", color: "#3F1899", fontWeight: 600 }}>
                        {res.similarityScore}% Sim
                      </span>
                    )}

                    <button
                      type="button"
                      className="button button-primary button-small"
                      onClick={() => {
                        onSelectResult(res.type, res.referenceId);
                        onClose();
                      }}
                    >
                      View
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <footer className="modal-footer" style={{ borderTop: "1px solid #e8e0f7", padding: "12px 16px", display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="button button-outline" onClick={onClose}>
            Close
          </button>
        </footer>
      </div>
    </div>
  );
}
