import { useState, useMemo } from "react";
import type { SampleRecord, StorageLocation } from "./types";

interface StorageBoxGridProps {
  location: StorageLocation;
  samples: SampleRecord[];
  onAssignCoordinate?: (sampleId: number, coordinate: string) => Promise<void>;
  onClearCoordinate?: (sampleId: number) => Promise<void>;
  disabled?: boolean;
}

type GridPreset = "9x9" | "8x12" | "10x10" | "6x4";

interface PresetConfig {
  label: string;
  rows: number;
  cols: number;
  description: string;
}

const PRESETS: Record<GridPreset, PresetConfig> = {
  "9x9": {
    label: "9x9 Cryo Box (81 vials)",
    rows: 9,
    cols: 9,
    description: "Standard 81-place cryogenic freezer storage box",
  },
  "8x12": {
    label: "8x12 Microplate (96 wells)",
    rows: 8,
    cols: 12,
    description: "Standard 96-well assay or culture microplate",
  },
  "10x10": {
    label: "10x10 Freezer Box (100 vials)",
    rows: 10,
    cols: 10,
    description: "100-place microcentrifuge tube box",
  },
  "6x4": {
    label: "6x4 Tube Rack (24 tubes)",
    rows: 4,
    cols: 6,
    description: "24-place Falcon / conical tube rack",
  },
};

const ROW_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function getSampleCoordinate(sample: SampleRecord): string | null {
  const text = `${sample.storage_location} ${sample.description}`;
  const bracketMatch = text.match(/\[([A-Z]\d{1,2})\]/i);
  if (bracketMatch) return bracketMatch[1].toUpperCase();

  const slotMatch = text.match(/\b(?:slot|well|pos|coord):\s*([A-Z]\d{1,2})\b/i);
  if (slotMatch) return slotMatch[1].toUpperCase();

  const directMatch = sample.storage_location.trim().match(/^([A-Z]\d{1,2})$/i);
  if (directMatch) return directMatch[1].toUpperCase();

  return null;
}

function getSampleColor(type: string): string {
  const colors: Record<string, string> = {
    dna: "#3b82f6",
    rna: "#06b6d4",
    protein: "#8b5cf6",
    antibody: "#ec4899",
    plasma: "#ef4444",
    cell: "#10b981",
    reagent: "#f59e0b",
    tissue: "#d97706",
    bacterial: "#6366f1",
  };
  const key = type.toLowerCase().trim();
  for (const [k, c] of Object.entries(colors)) {
    if (key.includes(k)) return c;
  }
  return "#64748b";
}

export function StorageBoxGrid({
  location,
  samples,
  onAssignCoordinate,
  onClearCoordinate,
  disabled = false,
}: StorageBoxGridProps) {
  const [preset, setPreset] = useState<GridPreset>("8x12");
  const [selectedCoord, setSelectedCoord] = useState<string | null>(null);
  const [selectedCoords, setSelectedCoords] = useState<Set<string>>(new Set());
  const [assigningSampleId, setAssigningSampleId] = useState<number | "">("");
  const [isSaving, setIsSaving] = useState(false);
  const [batchNotice, setBatchNotice] = useState("");

  const config = PRESETS[preset];

  const { coordMap, unassignedSamples } = useMemo(() => {
    const locSamples = samples.filter((s) => s.storage_location_id === location.id);
    const map = new Map<string, SampleRecord>();
    const unassigned: SampleRecord[] = [];

    for (const sample of locSamples) {
      const coord = getSampleCoordinate(sample);
      if (coord) {
        map.set(coord, sample);
      } else {
        unassigned.push(sample);
      }
    }

    return { coordMap: map, locationSamples: locSamples, unassignedSamples: unassigned };
  }, [samples, location.id]);

  const totalCells = config.rows * config.cols;
  const occupiedCount = coordMap.size;
  const occupancyPct = Math.round((occupiedCount / totalCells) * 100);

  const selectedSample = selectedCoord ? coordMap.get(selectedCoord) ?? null : null;

  // Single cell selection or multi-toggle
  function handleCellClick(coord: string, shiftKey: boolean) {
    if (shiftKey || selectedCoords.size > 0) {
      const next = new Set(selectedCoords);
      if (next.has(coord)) {
        next.delete(coord);
      } else {
        next.add(coord);
      }
      setSelectedCoords(next);
      setSelectedCoord(coord);
    } else {
      setSelectedCoord(coord);
      setSelectedCoords(new Set([coord]));
    }
  }

  // Row header selection (e.g. click "A" to select A1..A12)
  function handleRowClick(rowLetter: string) {
    const next = new Set(selectedCoords);
    const rowCoords = Array.from({ length: config.cols }, (_, c) => `${rowLetter}${c + 1}`);
    const allSelected = rowCoords.every((c) => next.has(c));

    for (const c of rowCoords) {
      if (allSelected) {
        next.delete(c);
      } else {
        next.add(c);
      }
    }
    setSelectedCoords(next);
    if (!allSelected) setSelectedCoord(rowCoords[0]);
  }

  // Column header selection (e.g. click "1" to select A1..H1)
  function handleColClick(colNum: number) {
    const next = new Set(selectedCoords);
    const colCoords = Array.from({ length: config.rows }, (_, r) => `${ROW_LABELS[r]}${colNum}`);
    const allSelected = colCoords.every((c) => next.has(c));

    for (const c of colCoords) {
      if (allSelected) {
        next.delete(c);
      } else {
        next.add(c);
      }
    }
    setSelectedCoords(next);
    if (!allSelected) setSelectedCoord(colCoords[0]);
  }

  function selectAllEmpty() {
    const next = new Set<string>();
    for (let r = 0; r < config.rows; r++) {
      for (let c = 1; c <= config.cols; c++) {
        const coord = `${ROW_LABELS[r]}${c}`;
        if (!coordMap.has(coord)) {
          next.add(coord);
        }
      }
    }
    setSelectedCoords(next);
    setBatchNotice(`Selected ${next.size} empty wells.`);
  }

  function selectAllOccupied() {
    const next = new Set<string>(coordMap.keys());
    setSelectedCoords(next);
    setBatchNotice(`Selected ${next.size} occupied wells.`);
  }

  function clearSelection() {
    setSelectedCoords(new Set());
    setSelectedCoord(null);
    setBatchNotice("");
  }

  async function handleAssignSlot() {
    if (!selectedCoord || !assigningSampleId || !onAssignCoordinate) return;
    try {
      setIsSaving(true);
      await onAssignCoordinate(Number(assigningSampleId), selectedCoord);
      setAssigningSampleId("");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClearSlot() {
    if (!selectedSample || !onClearCoordinate) return;
    try {
      setIsSaving(true);
      await onClearCoordinate(selectedSample.id);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleBatchClear() {
    if (!onClearCoordinate || selectedCoords.size === 0) return;
    setIsSaving(true);
    setBatchNotice(`Clearing ${selectedCoords.size} wells...`);
    try {
      let count = 0;
      for (const coord of selectedCoords) {
        const s = coordMap.get(coord);
        if (s) {
          await onClearCoordinate(s.id);
          count++;
        }
      }
      setSelectedCoords(new Set());
      setBatchNotice(`Cleared ${count} samples from selected wells.`);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleBatchAssignSequence() {
    if (!onAssignCoordinate || selectedCoords.size === 0 || unassignedSamples.length === 0) return;
    setIsSaving(true);
    setBatchNotice("Assigning samples in sequence...");
    try {
      const emptyCoords = Array.from(selectedCoords)
        .filter((c) => !coordMap.has(c))
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

      const toAssign = Math.min(emptyCoords.length, unassignedSamples.length);
      for (let i = 0; i < toAssign; i++) {
        await onAssignCoordinate(unassignedSamples[i].id, emptyCoords[i]);
      }
      setSelectedCoords(new Set());
      setBatchNotice(`Successfully placed ${toAssign} samples into coordinate wells.`);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="storage-box-grid-container" style={{ marginTop: "1rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          marginBottom: "0.75rem",
        }}
      >
        <div>
          <h4 style={{ margin: 0 }}>
            {location.name} ({location.code}) &mdash; 2D Grid Visualizer
          </h4>
          <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
            {config.description} | {occupiedCount} / {totalCells} slots occupied ({occupancyPct}%)
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Grid Layout:</label>
          <select
            value={preset}
            onChange={(e) => {
              setPreset(e.target.value as GridPreset);
              setSelectedCoords(new Set());
              setSelectedCoord(null);
            }}
            style={{ padding: "0.25rem 0.5rem", borderRadius: "4px" }}
          >
            {Object.entries(PRESETS).map(([key, val]) => (
              <option key={key} value={key}>
                {val.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Occupancy Progress Bar */}
      <div
        style={{
          width: "100%",
          height: "6px",
          backgroundColor: "#e2e8f0",
          borderRadius: "3px",
          overflow: "hidden",
          marginBottom: "0.75rem",
        }}
      >
        <div
          style={{
            width: `${occupancyPct}%`,
            height: "100%",
            backgroundColor: occupancyPct > 90 ? "#ef4444" : occupancyPct > 70 ? "#f59e0b" : "#10b981",
            transition: "width 0.3s ease",
          }}
        />
      </div>

      {/* Multi-Well Batch Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          flexWrap: "wrap",
          padding: "6px 12px",
          borderRadius: "6px",
          background: "var(--card-bg, #f8fafc)",
          border: "1px solid var(--border-color, #e2e8f0)",
          marginBottom: "0.75rem",
          fontSize: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700, color: "var(--text-primary, #334155)" }}>
            ⚡ Multi-Well Batch Mode:
          </span>
          <button className="button button-outline button-small" type="button" onClick={selectAllEmpty}>
            Select All Empty
          </button>
          <button className="button button-outline button-small" type="button" onClick={selectAllOccupied}>
            Select All Occupied
          </button>
          {selectedCoords.size > 0 && (
            <button className="button button-outline button-small" type="button" onClick={clearSelection}>
              Deselect ({selectedCoords.size})
            </button>
          )}
        </div>

        {selectedCoords.size > 1 && !disabled && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontWeight: 600, color: "#2563eb" }}>
              {selectedCoords.size} wells selected
            </span>
            {unassignedSamples.length > 0 && onAssignCoordinate && (
              <button
                className="button button-primary button-small"
                type="button"
                onClick={() => void handleBatchAssignSequence()}
                disabled={isSaving}
              >
                Batch Fill Sequence ({Math.min(selectedCoords.size, unassignedSamples.length)})
              </button>
            )}
            {onClearCoordinate && (
              <button
                className="button button-outline button-small"
                type="button"
                onClick={() => void handleBatchClear()}
                disabled={isSaving}
                style={{ color: "#ef4444", borderColor: "#fca5a5" }}
              >
                Batch Clear
              </button>
            )}
          </div>
        )}
      </div>

      {batchNotice && (
        <div style={{ padding: "4px 10px", marginBottom: "8px", borderRadius: 4, background: "#ecfdf5", color: "#065f46", fontSize: 11 }}>
          {batchNotice}
        </div>
      )}

      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        {/* 2D Grid Table */}
        <div style={{ overflowX: "auto", flex: "1 1 500px" }}>
          <div
            style={{
              display: "inline-block",
              background: "var(--card-bg, #ffffff)",
              padding: "1rem",
              borderRadius: "8px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              border: "1px solid var(--border-color, #cbd5e1)",
            }}
          >
            <table
              style={{
                borderCollapse: "separate",
                borderSpacing: "4px",
                margin: "0 auto",
              }}
            >
              <thead>
                <tr>
                  <th style={{ width: "24px", height: "24px", fontSize: "0.75rem", color: "#94a3b8" }}></th>
                  {Array.from({ length: config.cols }).map((_, c) => (
                    <th
                      key={c}
                      onClick={() => handleColClick(c + 1)}
                      title={`Click to select entire Column ${c + 1}`}
                      style={{
                        width: "36px",
                        height: "24px",
                        textAlign: "center",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "var(--text-secondary, #475569)",
                        cursor: "pointer",
                        borderRadius: "3px",
                      }}
                    >
                      {c + 1}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: config.rows }).map((_, r) => {
                  const rowLetter = ROW_LABELS[r];
                  return (
                    <tr key={rowLetter}>
                      <td
                        onClick={() => handleRowClick(rowLetter)}
                        title={`Click to select entire Row ${rowLetter}`}
                        style={{
                          width: "24px",
                          textAlign: "center",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          color: "var(--text-secondary, #475569)",
                          cursor: "pointer",
                          paddingRight: "4px",
                          borderRadius: "3px",
                        }}
                      >
                        {rowLetter}
                      </td>
                      {Array.from({ length: config.cols }).map((_, c) => {
                        const coord = `${rowLetter}${c + 1}`;
                        const sample = coordMap.get(coord);
                        const isMultiSelected = selectedCoords.has(coord);
                        const isPrimarySelected = selectedCoord === coord;
                        const sampleColor = sample ? getSampleColor(sample.sample_type) : undefined;

                        return (
                          <td
                            key={coord}
                            onClick={(e) => handleCellClick(coord, e.shiftKey)}
                            title={
                              sample
                                ? `${coord}: ${sample.name} (${sample.sample_type})\nID: ${sample.external_id || "None"}\nStatus: ${sample.status}`
                                : `${coord}: Empty slot (click to select or Shift+click for batch)`
                            }
                            style={{
                              width: "36px",
                              height: "36px",
                              padding: 0,
                              cursor: "pointer",
                              textAlign: "center",
                              verticalAlign: "middle",
                            }}
                          >
                            <div
                              style={{
                                width: "36px",
                                height: "36px",
                                borderRadius: preset === "8x12" ? "50%" : "6px",
                                border: isMultiSelected
                                  ? "2px solid #2563eb"
                                  : sample
                                  ? `1px solid ${sampleColor}`
                                  : "1px dashed var(--border-color, #cbd5e1)",
                                backgroundColor: isMultiSelected
                                  ? "#dbeafe"
                                  : sample
                                  ? `${sampleColor}25`
                                  : "var(--cell-bg, #f8fafc)",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                transition: "all 0.15s ease",
                                transform: isPrimarySelected ? "scale(1.10)" : isMultiSelected ? "scale(1.04)" : "none",
                                boxShadow: isMultiSelected ? "0 0 6px rgba(37,99,235,0.4)" : "none",
                              }}
                            >
                              {sample ? (
                                <div
                                  style={{
                                    width: "14px",
                                    height: "14px",
                                    borderRadius: "50%",
                                    backgroundColor: sampleColor,
                                    boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
                                  }}
                                />
                              ) : (
                                <span style={{ fontSize: "0.6rem", color: isMultiSelected ? "#1d4ed8" : "#94a3b8", userSelect: "none" }}>
                                  {coord}
                                </span>
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Slot Inspector Panel */}
        <div
          style={{
            flex: "1 1 260px",
            minWidth: "260px",
            background: "var(--card-bg, #ffffff)",
            padding: "1rem",
            borderRadius: "8px",
            border: "1px solid var(--border-color, #cbd5e1)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h5 style={{ margin: "0 0 0.5rem 0", borderBottom: "1px solid var(--border-color, #e2e8f0)", paddingBottom: "0.5rem" }}>
            {selectedCoords.size > 1
              ? `Batch Selection (${selectedCoords.size} wells)`
              : selectedCoord
              ? `Slot Details: ${selectedCoord}`
              : "Select a Well / Slot"}
          </h5>

          {selectedCoords.size > 1 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary, #64748b)" }}>
                <strong>{selectedCoords.size}</strong> wells currently selected across grid.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", maxHeight: "100px", overflowY: "auto" }}>
                {Array.from(selectedCoords).map((c) => (
                  <span key={c} style={{ fontSize: "0.75rem", padding: "2px 6px", borderRadius: 4, background: "#dbeafe", color: "#1e40af" }}>
                    {c}
                  </span>
                ))}
              </div>
              {!disabled && unassignedSamples.length > 0 && onAssignCoordinate && (
                <button
                  className="button button-primary"
                  type="button"
                  onClick={() => void handleBatchAssignSequence()}
                  disabled={isSaving}
                  style={{ width: "100%" }}
                >
                  {isSaving ? "Assigning..." : `Fill ${Math.min(selectedCoords.size, unassignedSamples.length)} Samples in Sequence`}
                </button>
              )}
              {!disabled && onClearCoordinate && (
                <button
                  className="button button-outline"
                  type="button"
                  onClick={() => void handleBatchClear()}
                  disabled={isSaving}
                  style={{ width: "100%", color: "#ef4444", borderColor: "#fca5a5" }}
                >
                  {isSaving ? "Clearing..." : "Clear Occupants from Selected"}
                </button>
              )}
            </div>
          ) : selectedCoord ? (
            selectedSample ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "0.2rem 0.5rem",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: "#ffffff",
                      backgroundColor: getSampleColor(selectedSample.sample_type),
                    }}
                  >
                    {selectedSample.sample_type}
                  </span>
                  <h4 style={{ margin: "0.35rem 0 0.15rem 0" }}>{selectedSample.name}</h4>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>
                    ID: <code>{selectedSample.external_id || "None"}</code>
                  </div>
                </div>

                <div style={{ fontSize: "0.8rem" }}>
                  <strong>Status:</strong> {selectedSample.status}
                </div>
                {selectedSample.description && (
                  <div style={{ fontSize: "0.8rem", color: "#475569" }}>
                    <strong>Note:</strong> {selectedSample.description}
                  </div>
                )}

                {!disabled && onClearCoordinate && (
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleClearSlot()}
                    disabled={isSaving}
                    style={{ marginTop: "0.5rem", color: "#ef4444", borderColor: "#fca5a5" }}
                  >
                    {isSaving ? "Clearing..." : "Remove from Slot"}
                  </button>
                )}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#64748b" }}>
                  Slot <strong>{selectedCoord}</strong> is currently empty.
                </p>

                {!disabled && onAssignCoordinate && (
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                      Assign Sample to {selectedCoord}:
                    </label>
                    <select
                      value={assigningSampleId}
                      onChange={(e) => setAssigningSampleId(e.target.value ? Number(e.target.value) : "")}
                      style={{ width: "100%", padding: "0.35rem", fontSize: "0.85rem", marginBottom: "0.5rem" }}
                    >
                      <option value="">-- Choose unassigned sample --</option>
                      {unassignedSamples.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.sample_type})
                        </option>
                      ))}
                    </select>
                    <button
                      className="button button-primary"
                      type="button"
                      onClick={() => void handleAssignSlot()}
                      disabled={!assigningSampleId || isSaving}
                      style={{ width: "100%" }}
                    >
                      {isSaving ? "Placing..." : `Place in ${selectedCoord}`}
                    </button>
                  </div>
                )}
              </div>
            )
          ) : (
            <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: 0 }}>
              Click any coordinate cell or drag/Shift+click to batch-select multiple wells.
            </p>
          )}

          {unassignedSamples.length > 0 && (
            <div style={{ marginTop: "1.25rem", borderTop: "1px solid var(--border-color, #e2e8f0)", paddingTop: "0.75rem" }}>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#64748b" }}>
                Unplaced in this container: {unassignedSamples.length}
              </span>
              <ul style={{ margin: "0.35rem 0 0 0", paddingLeft: "1.2rem", fontSize: "0.8rem", color: "#475569" }}>
                {unassignedSamples.slice(0, 5).map((s) => (
                  <li key={s.id}>
                    {s.name} ({s.sample_type})
                  </li>
                ))}
                {unassignedSamples.length > 5 && (
                  <li style={{ color: "#94a3b8" }}>+{unassignedSamples.length - 5} more</li>
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
