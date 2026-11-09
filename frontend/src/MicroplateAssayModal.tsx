import { useState, useEffect, useMemo, useCallback } from "react";
import { platesApi, type Microplate, type PlateWell, type HeatmapMatrix } from "./api";

interface MicroplateAssayModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId?: number | null;
  experimentId?: number | null;
  initialPlateId?: number | null;
}

const ROLE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  sample: { bg: "#06b6d4", text: "#083344", label: "Sample" },
  standard: { bg: "#10b981", text: "#022c22", label: "Standard" },
  control_pos: { bg: "#f59e0b", text: "#451a03", label: "Pos Control" },
  control_neg: { bg: "#ef4444", text: "#450a0a", label: "Neg Control" },
  blank: { bg: "#64748b", text: "#0f172a", label: "Blank" },
  empty: { bg: "rgba(255,255,255,0.06)", text: "#94a3b8", label: "Empty" },
};

export function MicroplateAssayModal({
  isOpen,
  onClose,
  projectId,
  experimentId,
  initialPlateId,
}: MicroplateAssayModalProps) {
  const [plates, setPlates] = useState<Microplate[]>([]);
  const [activePlate, setActivePlate] = useState<Microplate | null>(null);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"layout" | "heatmap">("layout");
  const [selectedCoords, setSelectedCoords] = useState<Set<string>>(new Set());
  const [heatmapData, setHeatmapData] = useState<HeatmapMatrix | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("sample");
  const [standardConc, setStandardConc] = useState<string>("10.0");
  const [selectedWellDetail, setSelectedWellDetail] = useState<PlateWell | null>(null);
  const [isCreatingPlate, setIsCreatingPlate] = useState(false);
  const [newPlateName, setNewPlateName] = useState("");
  const [newPlateFormat, setNewPlateFormat] = useState<"96-well" | "384-well">("96-well");
  const [newAssayType, setNewAssayType] = useState("ELISA Absorbance (450nm)");
  const [csvNotice, setCsvNotice] = useState<string | null>(null);

  // Load plates list
  const loadPlates = useCallback(async () => {
    try {
      setLoading(true);
      const list = await platesApi.list(projectId, experimentId);
      setPlates(list);
      if (list.length > 0) {
        const found = initialPlateId ? list.find((p) => p.id === initialPlateId) : list[0];
        setActivePlate(found || list[0]);
      } else {
        setActivePlate(null);
      }
    } catch (err) {
      console.warn("Failed to load microplates:", err);
    } finally {
      setLoading(false);
    }
  }, [projectId, experimentId, initialPlateId]);

  useEffect(() => {
    if (isOpen) {
      loadPlates();
    }
  }, [isOpen, loadPlates]);

  // Load heatmap when switching to heatmap mode
  useEffect(() => {
    if (viewMode === "heatmap" && activePlate) {
      platesApi.getHeatmap(activePlate.id)
        .then(setHeatmapData)
        .catch((e) => console.warn("Heatmap fetch error:", e));
    }
  }, [viewMode, activePlate]);

  // Map of wells by coordinate
  const wellsMap = useMemo(() => {
    const map = new Map<string, PlateWell>();
    if (activePlate?.wells) {
      for (const w of activePlate.wells) {
        map.set(w.coordinate, w);
      }
    }
    return map;
  }, [activePlate]);

  const rowsList = useMemo(() => {
    if (!activePlate) return [];
    const count = activePlate.rows || 8;
    return Array.from({ length: count }, (_, i) => String.fromCharCode(65 + i));
  }, [activePlate]);

  const colsList = useMemo(() => {
    if (!activePlate) return [];
    const count = activePlate.cols || 12;
    return Array.from({ length: count }, (_, i) => i + 1);
  }, [activePlate]);

  // Handle well click / toggle
  const toggleWellSelect = (coord: string, multi: boolean) => {
    const next = new Set(multi ? selectedCoords : []);
    if (next.has(coord)) {
      next.delete(coord);
    } else {
      next.add(coord);
    }
    setSelectedCoords(next);
    setSelectedWellDetail(wellsMap.get(coord) || null);
  };

  // Select entire row
  const selectRow = (r: string) => {
    const next = new Set<string>();
    for (const c of colsList) {
      next.add(`${r}${c}`);
    }
    setSelectedCoords(next);
  };

  // Select entire col
  const selectCol = (c: number) => {
    const next = new Set<string>();
    for (const r of rowsList) {
      next.add(`${r}${c}`);
    }
    setSelectedCoords(next);
  };

  // Batch apply role to selected wells
  const applyRoleToSelected = async () => {
    if (!activePlate || selectedCoords.size === 0) return;
    const updates: Partial<PlateWell>[] = [];
    const conc = selectedRole === "standard" ? parseFloat(standardConc) || null : null;

    selectedCoords.forEach((coord) => {
      updates.push({
        coordinate: coord,
        role: selectedRole as any,
        standard_concentration: conc,
        sample_name: selectedRole === "sample" ? `Sample-${coord}` : "",
      });
    });

    try {
      setLoading(true);
      const updated = await platesApi.updateWells(activePlate.id, updates);
      setActivePlate(updated);
      setSelectedCoords(new Set());
    } catch (err) {
      console.error("Failed to update wells:", err);
    } finally {
      setLoading(false);
    }
  };

  // Calculate quantitation
  const handleCalculate = async () => {
    if (!activePlate) return;
    try {
      setLoading(true);
      await platesApi.calculate(activePlate.id);
      const fresh = await platesApi.get(activePlate.id);
      setActivePlate(fresh);
      setViewMode("heatmap");
    } catch (err) {
      console.error("Calculation failed:", err);
    } finally {
      setLoading(false);
    }
  };

  // CSV Import
  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!activePlate || !e.target.files?.[0]) return;
    const file = e.target.files[0];
    try {
      setLoading(true);
      const res = await platesApi.uploadCsv(activePlate.id, file);
      setCsvNotice(`Successfully imported ${res.updated_wells} well absorbance readings from ${file.name}!`);
      const fresh = await platesApi.get(activePlate.id);
      setActivePlate(fresh);
      setViewMode("heatmap");
    } catch (err) {
      setCsvNotice("Failed to import plate reader CSV. Verify standard 8x12 numerical format.");
    } finally {
      setLoading(false);
    }
  };

  // Create new plate
  const handleCreatePlate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPlateName.trim()) return;
    try {
      setLoading(true);
      const created = await platesApi.create({
        name: newPlateName.trim(),
        plate_format: newPlateFormat,
        assay_type: newAssayType,
        project_id: projectId,
        experiment_id: experimentId,
      });
      setPlates((prev) => [created, ...prev]);
      setActivePlate(created);
      setIsCreatingPlate(false);
      setNewPlateName("");
    } catch (err) {
      console.error("Failed to create plate:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card microplate-modal-card">
        {/* Header */}
        <header className="microplate-header">
          <div className="title-group">
            <span className="badge-core">PHASE 1 ASSAYS</span>
            <h2>🔬 96-Well & 384-Well Microplate & Spectrophotometry Studio</h2>
          </div>
          <button className="button-close" type="button" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </header>

        {/* Top Controls Bar */}
        <div className="microplate-toolbar">
          <div className="plate-select-group">
            <label>Active Plate:</label>
            <select
              value={activePlate?.id || ""}
              onChange={(e) => {
                const found = plates.find((p) => p.id === Number(e.target.value));
                if (found) {
                  setActivePlate(found);
                  setSelectedCoords(new Set());
                  setSelectedWellDetail(null);
                }
              }}
              disabled={loading || plates.length === 0}
            >
              {plates.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.plate_format}) - {p.assay_type}
                </option>
              ))}
            </select>
            <button
              className="button button-small button-outline"
              type="button"
              onClick={() => setIsCreatingPlate(true)}
            >
              + New Plate
            </button>
          </div>

          <div className="view-mode-toggle">
            <button
              type="button"
              className={`button button-small ${viewMode === "layout" ? "button-primary" : "button-outline"}`}
              onClick={() => setViewMode("layout")}
            >
              🎨 Layout & Roles
            </button>
            <button
              type="button"
              className={`button button-small ${viewMode === "heatmap" ? "button-primary" : "button-outline"}`}
              onClick={() => setViewMode("heatmap")}
            >
              🔥 Optical Density Heatmap
            </button>
          </div>

          <div className="csv-upload-group">
            <label className="button button-small button-outline csv-label">
              📥 Import Plate Reader CSV
              <input type="file" accept=".csv,.txt,.tsv" onChange={handleCsvUpload} style={{ display: "none" }} />
            </label>
            <button
              type="button"
              className="button button-small button-primary"
              onClick={handleCalculate}
              disabled={loading || !activePlate}
            >
              ⚡ Run 4PL Quantitation
            </button>
          </div>
        </div>

        {csvNotice && (
          <div className="notice notice-info">
            {csvNotice}
            <button type="button" onClick={() => setCsvNotice(null)}>&times;</button>
          </div>
        )}

        {/* Create Plate Form Dialog */}
        {isCreatingPlate && (
          <form className="create-plate-dialog" onSubmit={handleCreatePlate}>
            <h3>Create New Analytical Microplate</h3>
            <div className="form-row">
              <label>Plate Name:
                <input
                  type="text"
                  required
                  placeholder="e.g., ELISA Dilution Series 01"
                  value={newPlateName}
                  onChange={(e) => setNewPlateName(e.target.value)}
                />
              </label>
              <label>Plate Format:
                <select value={newPlateFormat} onChange={(e: any) => setNewPlateFormat(e.target.value)}>
                  <option value="96-well">96-Well Grid (8 x 12)</option>
                  <option value="384-well">384-Well Grid (16 x 24)</option>
                </select>
              </label>
              <label>Assay Modality:
                <input
                  type="text"
                  value={newAssayType}
                  onChange={(e) => setNewAssayType(e.target.value)}
                />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-primary" type="submit">Create Plate</button>
              <button className="button button-outline" type="button" onClick={() => setIsCreatingPlate(false)}>Cancel</button>
            </div>
          </form>
        )}

        {/* Main Workspace Body */}
        <div className="microplate-body">
          {/* Grid Area */}
          <div className="plate-grid-container">
            {activePlate ? (
              <div className={`microplate-table-wrapper plate-${activePlate.plate_format}`}>
                <table className="microplate-table">
                  <thead>
                    <tr>
                      <th className="corner-th"></th>
                      {colsList.map((c) => (
                        <th key={c} className="col-header-th" onClick={() => selectCol(c)}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rowsList.map((r) => (
                      <tr key={r}>
                        <th className="row-header-th" onClick={() => selectRow(r)}>
                          {r}
                        </th>
                        {colsList.map((c) => {
                          const coord = `${r}${c}`;
                          const well = wellsMap.get(coord);
                          const isSelected = selectedCoords.has(coord);
                          const roleStyle = ROLE_COLORS[well?.role || "empty"];

                          // Heatmap color calculation
                          let cellStyle: React.CSSProperties = {};
                          if (viewMode === "heatmap" && well?.raw_value !== null && well?.raw_value !== undefined) {
                            const minVal = heatmapData?.min_value ?? 0.05;
                            const maxVal = heatmapData?.max_value ?? 2.5;
                            const norm = Math.max(0, Math.min(1, (well.raw_value - minVal) / (maxVal - minVal || 1)));
                            // Gradient: cyan (low) -> amber -> crimson (high)
                            const rVal = Math.round(norm * 240);
                            const gVal = Math.round((1 - Math.abs(norm - 0.5) * 2) * 200);
                            const bVal = Math.round((1 - norm) * 240);
                            cellStyle = {
                              backgroundColor: `rgba(${rVal}, ${gVal}, ${bVal}, 0.85)`,
                              color: norm > 0.4 ? "#fff" : "#000",
                              fontWeight: 700,
                            };
                          } else {
                            cellStyle = {
                              backgroundColor: roleStyle.bg,
                              color: roleStyle.text,
                            };
                          }

                          return (
                            <td
                              key={coord}
                              className={`well-td ${isSelected ? "selected-well" : ""}`}
                              onClick={(e) => toggleWellSelect(coord, e.shiftKey || e.ctrlKey || e.metaKey)}
                              style={cellStyle}
                              title={`${coord}: ${well?.role || "empty"}${well?.raw_value ? ` | OD: ${well.raw_value}` : ""}${well?.calculated_concentration ? ` | Conc: ${well.calculated_concentration.toFixed(2)}` : ""}`}
                            >
                              <div className="well-circle">
                                <span className="well-coord-text">{coord}</span>
                                {viewMode === "heatmap" && well?.raw_value !== null && well?.raw_value !== undefined ? (
                                  <span className="well-value-text">{well.raw_value.toFixed(2)}</span>
                                ) : (
                                  <span className="well-role-badge">
                                    {well?.role === "standard" ? `Std ${well.standard_concentration ?? ""}` : well?.role === "blank" ? "BLK" : well?.role === "control_pos" ? "POS" : well?.role === "control_neg" ? "NEG" : ""}
                                  </span>
                                )}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-plate-hint">
                <p>No microplates configured for this experiment yet.</p>
                <button className="button button-primary" type="button" onClick={() => setIsCreatingPlate(true)}>
                  Create Your First 96-Well Microplate
                </button>
              </div>
            )}
          </div>

          {/* Right Inspector & Batch Actions Drawer */}
          <aside className="microplate-inspector">
            <div className="inspector-card">
              <h4>Role & Batch Configuration</h4>
              <p className="hint-copy">
                {selectedCoords.size > 0
                  ? `${selectedCoords.size} well(s) selected: ${Array.from(selectedCoords).slice(0, 6).join(", ")}${selectedCoords.size > 6 ? "..." : ""}`
                  : "Click wells or click Row/Column headers to select batch."}
              </p>

              <div className="role-selector-radios">
                {Object.entries(ROLE_COLORS).map(([rKey, info]) => (
                  <label key={rKey} className="role-radio-label">
                    <input
                      type="radio"
                      name="role_radio"
                      value={rKey}
                      checked={selectedRole === rKey}
                      onChange={(e) => setSelectedRole(e.target.value)}
                    />
                    <span className="role-chip-indicator" style={{ backgroundColor: info.bg }}></span>
                    {info.label}
                  </label>
                ))}
              </div>

              {selectedRole === "standard" && (
                <div className="standard-conc-input">
                  <label>Standard Concentration (ng/mL):
                    <input
                      type="number"
                      step="any"
                      value={standardConc}
                      onChange={(e) => setStandardConc(e.target.value)}
                    />
                  </label>
                </div>
              )}

              <button
                type="button"
                className="button button-full button-primary"
                onClick={applyRoleToSelected}
                disabled={selectedCoords.size === 0 || loading}
              >
                Apply Role to {selectedCoords.size} Well(s)
              </button>
            </div>

            {/* Well Details Card */}
            {selectedWellDetail && (
              <div className="inspector-card well-detail-card">
                <h4>Well Telemetry: {selectedWellDetail.coordinate}</h4>
                <div className="telemetry-grid">
                  <div><strong>Role:</strong> {selectedWellDetail.role}</div>
                  <div><strong>Raw OD:</strong> {selectedWellDetail.raw_value !== null ? selectedWellDetail.raw_value : "No reading"}</div>
                  <div><strong>Blank Corrected:</strong> {selectedWellDetail.corrected_value !== null ? selectedWellDetail.corrected_value.toFixed(4) : "N/A"}</div>
                  <div><strong>Calc Conc:</strong> {selectedWellDetail.calculated_concentration !== null ? `${selectedWellDetail.calculated_concentration.toFixed(3)} ${selectedWellDetail.concentration_unit}` : "N/A"}</div>
                </div>
              </div>
            )}

            {/* Heatmap Legend */}
            <div className="inspector-card">
              <h4>Spectrophotometric Calibration</h4>
              <div className="heatmap-gradient-legend">
                <span className="legend-label">0.05 OD (Blank)</span>
                <div className="gradient-bar"></div>
                <span className="legend-label">2.50+ OD (Saturated)</span>
              </div>
              <p className="legend-caption">
                Standard ELISA Absorbance at λ = 450 nm. 4-Parameter Logistic (4PL) regression applies automated blank baseline subtraction.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
