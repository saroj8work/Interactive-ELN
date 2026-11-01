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

// Helper to extract coordinate from sample storage string or description
function getSampleCoordinate(sample: SampleRecord): string | null {
  const text = `${sample.storage_location} ${sample.description}`;
  // Look for patterns like [A1], (B12), slot: C4, or standalone A1..Z99
  const bracketMatch = text.match(/\[([A-Z]\d{1,2})\]/i);
  if (bracketMatch) return bracketMatch[1].toUpperCase();

  const slotMatch = text.match(/\b(?:slot|well|pos|coord):\s*([A-Z]\d{1,2})\b/i);
  if (slotMatch) return slotMatch[1].toUpperCase();

  // If storage_location is directly the coordinate
  const directMatch = sample.storage_location.trim().match(/^([A-Z]\d{1,2})$/i);
  if (directMatch) return directMatch[1].toUpperCase();

  return null;
}

// Generate color from string for sample types
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
  const [preset, setPreset] = useState<GridPreset>("9x9");
  const [selectedCoord, setSelectedCoord] = useState<string | null>(null);
  const [assigningSampleId, setAssigningSampleId] = useState<number | "">("");
  const [isSaving, setIsSaving] = useState(false);

  const config = PRESETS[preset];

  // Map coordinates to samples for this specific location
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

  return (
    <div className="storage-box-grid-container" style={{ marginTop: "1rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        <div>
          <h4 style={{ margin: 0 }}>
            {location.name} ({location.code}) - 2D Grid Visualizer
          </h4>
          <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
            {config.description} | {occupiedCount} / {totalCells} slots occupied ({occupancyPct}%)
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Grid Layout:</label>
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value as GridPreset)}
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
          marginBottom: "1.25rem",
        }}
      >
        <div
          style={{
            width: `${Math.min(100, occupancyPct)}%`,
            height: "100%",
            backgroundColor: occupancyPct > 90 ? "#ef4444" : occupancyPct > 70 ? "#f59e0b" : "#10b981",
            transition: "width 0.3s ease",
          }}
        />
      </div>

      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        {/* 2D Grid Table */}
        <div style={{ overflowX: "auto", flex: "1 1 500px" }}>
          <div
            style={{
              display: "inline-block",
              background: "#ffffff",
              padding: "1rem",
              borderRadius: "8px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              border: "1px solid #cbd5e1",
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
                      style={{
                        width: "36px",
                        height: "24px",
                        textAlign: "center",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: "#475569",
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
                        style={{
                          width: "24px",
                          textAlign: "center",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          color: "#475569",
                          paddingRight: "4px",
                        }}
                      >
                        {rowLetter}
                      </td>
                      {Array.from({ length: config.cols }).map((_, c) => {
                        const coord = `${rowLetter}${c + 1}`;
                        const sample = coordMap.get(coord);
                        const isSelected = selectedCoord === coord;
                        const sampleColor = sample ? getSampleColor(sample.sample_type) : undefined;

                        return (
                          <td
                            key={coord}
                            onClick={() => setSelectedCoord(coord)}
                            title={
                              sample
                                ? `${coord}: ${sample.name} (${sample.sample_type})\nID: ${sample.external_id || "None"}\nStatus: ${sample.status}`
                                : `${coord}: Empty slot (click to assign)`
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
                                border: isSelected
                                  ? "2px solid #2563eb"
                                  : sample
                                  ? `1px solid ${sampleColor}`
                                  : "1px dashed #cbd5e1",
                                backgroundColor: isSelected
                                  ? "#dbeafe"
                                  : sample
                                  ? `${sampleColor}25`
                                  : "#f8fafc",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                transition: "all 0.15s ease",
                                transform: isSelected ? "scale(1.08)" : "none",
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
                                <span style={{ fontSize: "0.6rem", color: "#94a3b8", userSelect: "none" }}>
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
            background: "#ffffff",
            padding: "1rem",
            borderRadius: "8px",
            border: "1px solid #cbd5e1",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h5 style={{ margin: "0 0 0.5rem 0", borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
            {selectedCoord ? `Slot Details: ${selectedCoord}` : "Select a Well / Slot"}
          </h5>

          {selectedCoord ? (
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
              Click any coordinate cell in the grid above to view sample details or assign an unassigned sample to that slot.
            </p>
          )}

          {unassignedSamples.length > 0 && (
            <div style={{ marginTop: "1.25rem", borderTop: "1px solid #e2e8f0", paddingTop: "0.75rem" }}>
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
