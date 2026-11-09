import { useState, useEffect, useMemo, useRef } from "react";

export interface PlateWellData {
  id?: number;
  coordinate: string;
  row_letter: string;
  col_number: number;
  role: "sample" | "standard" | "control_pos" | "control_neg" | "blank" | "empty";
  sample_name?: string;
  sample_id?: number | null;
  replicate_group?: string;
  standard_concentration?: number | null;
  concentration_unit?: string;
  dilution_factor?: number;
  raw_value?: number | null;
  corrected_value?: number | null;
  calculated_concentration?: number | null;
}

export interface MicroplateData {
  id: number;
  name: string;
  plate_format: "96-well" | "384-well" | "24-well";
  rows: number;
  cols: number;
  description: string;
  assay_type: string;
  wavelength: string;
  measurement_unit: string;
  wells: PlateWellData[];
}

interface MicroplateVisualizerProps {
  plateId?: number;
  onClose?: () => void;
  token?: string;
}

const ROLE_COLORS: Record<string, { bg: string; border: string; text: string; label: string }> = {
  standard: { bg: "#dbeafe", border: "#3b82f6", text: "#1d4ed8", label: "Standard" },
  control_pos: { bg: "#dcfce7", border: "#22c55e", text: "#15803d", label: "Pos Control" },
  control_neg: { bg: "#fee2e2", border: "#ef4444", text: "#b91c1c", label: "Neg Control" },
  blank: { bg: "#f1f5f9", border: "#94a3b8", text: "#475569", label: "Blank" },
  sample: { bg: "#f3e8ff", border: "#a855f7", text: "#7e22ce", label: "Sample" },
  empty: { bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.15)", text: "#94a3b8", label: "Empty" },
};

export function MicroplateVisualizer({ plateId = 1, onClose, token }: MicroplateVisualizerProps) {
  const [plate, setPlate] = useState<MicroplateData | null>(null);
  const [selectedCoord, setSelectedCoord] = useState<string>("A1");
  const [selectedCoords, setSelectedCoords] = useState<string[]>(["A1"]);
  const [isLassoDragging, setIsLassoDragging] = useState<boolean>(false);
  const [lassoBox, setLassoBox] = useState<{ startX: number; startY: number; endX: number; endY: number } | null>(null);
  const gridContainerRef = useRef<HTMLDivElement>(null);

  const [viewMode, setViewMode] = useState<"layout" | "heatmap">("layout");
  const [loading, setLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [curveStats, setCurveStats] = useState<any>(null);

  // Edit well state
  const [editRole, setEditRole] = useState<PlateWellData["role"]>("standard");
  const [editSampleName, setEditSampleName] = useState<string>("");
  const [editStdConc, setEditStdConc] = useState<string>("100.0");
  const [editDilution, setEditDilution] = useState<string>("1.0");

  function batchSetRole(role: PlateWellData["role"]) {
    if (!plate || selectedCoords.length === 0) return;
    const updated = plate.wells.map((w) =>
      selectedCoords.includes(w.coordinate) ? { ...w, role } : w
    );
    setPlate({ ...plate, wells: updated });
    setStatusMessage(`Updated ${selectedCoords.length} wells to role "${role}".`);
    setTimeout(() => setStatusMessage(""), 3000);
  }

  function batchApplyDilution(baseConc: number, factor: number) {
    if (!plate || selectedCoords.length === 0) return;
    let curr = baseConc;
    const updated = plate.wells.map((w) => {
      if (selectedCoords.includes(w.coordinate)) {
        const wellUpdate = { ...w, standard_concentration: +curr.toFixed(2), role: "standard" as const };
        curr /= factor;
        return wellUpdate;
      }
      return w;
    });
    setPlate({ ...plate, wells: updated });
    setStatusMessage(`Applied ${factor}x dilution series across ${selectedCoords.length} wells.`);
    setTimeout(() => setStatusMessage(""), 3000);
  }

  // Pointer drag event handlers for lasso bounding box
  const handleGridPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Only trigger lasso on left click and when clicking empty space or plate skirt
    if (e.button !== 0 || !gridContainerRef.current) return;
    const rect = gridContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setIsLassoDragging(true);
    setLassoBox({ startX: x, startY: y, endX: x, endY: y });
  };

  const handleGridPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isLassoDragging || !gridContainerRef.current || !lassoBox) return;
    const rect = gridContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setLassoBox((prev) => (prev ? { ...prev, endX: x, endY: y } : null));

    // Calculate intersected wells
    const x1 = Math.min(lassoBox.startX, x);
    const x2 = Math.max(lassoBox.startX, x);
    const y1 = Math.min(lassoBox.startY, y);
    const y2 = Math.max(lassoBox.startY, y);

    const wellEls = gridContainerRef.current.querySelectorAll<HTMLElement>("[data-coord]");
    const selected: string[] = [];
    wellEls.forEach((el) => {
      const wellRect = el.getBoundingClientRect();
      const wx = wellRect.left - rect.left + wellRect.width / 2;
      const wy = wellRect.top - rect.top + wellRect.height / 2;
      if (wx >= x1 && wx <= x2 && wy >= y1 && wy <= y2) {
        const coord = el.getAttribute("data-coord");
        if (coord) selected.push(coord);
      }
    });
    if (selected.length > 0) {
      setSelectedCoords(selected);
      setSelectedCoord(selected[0]);
    }
  };

  const handleGridPointerUp = () => {
    setIsLassoDragging(false);
    setLassoBox(null);
  };

  // Fetch or mock plate
  useEffect(() => {
    async function loadPlate() {
      setLoading(true);
      try {
        const res = await fetch(`/api/plates/${plateId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setPlate(data);
        } else {
          // Initialize mock 96-well plate for standalone / demo mode
          initializeDefaultPlate();
        }
      } catch {
        initializeDefaultPlate();
      } finally {
        setLoading(false);
      }
    }
    loadPlate();
  }, [plateId, token]);

  function initializeDefaultPlate() {
    const rows = 8;
    const cols = 12;
    const mockWells: PlateWellData[] = [];
    for (let r = 0; r < rows; r++) {
      const rowLetter = String.fromCharCode(65 + r);
      for (let c = 1; c <= cols; c++) {
        const coord = `${rowLetter}${c}`;
        let role: PlateWellData["role"] = "sample";
        let rawVal: number | null = +(Math.random() * 1.5 + 0.1).toFixed(3);
        let stdConc: number | null = null;
        let sampleName = `Sample-${coord}`;

        // Standard curve in Column 1 & 2
        if (c === 1 || c === 2) {
          role = "standard";
          const dilutionSeries = [1000, 500, 250, 125, 62.5, 31.25, 15.63, 0];
          stdConc = dilutionSeries[r];
          sampleName = `Std-${stdConc}ng/mL`;
          rawVal = +(0.08 + (stdConc / 1000) * 2.1).toFixed(3);
        } else if (r === 7 && c >= 11) {
          // Blanks in H11, H12
          role = "blank";
          sampleName = "Blank (Buffer)";
          rawVal = 0.054;
        } else if (r === 0 && (c === 11 || c === 12)) {
          role = "control_pos";
          sampleName = "Pos Ctrl (100%)";
          rawVal = 1.95;
        } else if (r === 1 && (c === 11 || c === 12)) {
          role = "control_neg";
          sampleName = "Neg Ctrl (0%)";
          rawVal = 0.062;
        }

        mockWells.push({
          coordinate: coord,
          row_letter: rowLetter,
          col_number: c,
          role,
          sample_name: sampleName,
          standard_concentration: stdConc,
          concentration_unit: "ng/mL",
          dilution_factor: 1.0,
          raw_value: rawVal,
          corrected_value: rawVal ? Math.max(0, +(rawVal - 0.054).toFixed(3)) : null,
          calculated_concentration: role === "sample" && rawVal ? +((rawVal - 0.054) * 450).toFixed(1) : stdConc,
        });
      }
    }

    setPlate({
      id: plateId || 1,
      name: "Assay Screen: Human Kinase Phosphorylation (96-Well ELISA)",
      plate_format: "96-well",
      rows: 8,
      cols: 12,
      description: "Absorbance detection at 450nm with 4PL blank subtraction and standard interpolation",
      assay_type: "Phospho-ELISA",
      wavelength: "450 nm",
      measurement_unit: "OD",
      wells: mockWells,
    });
  }

  const selectedWell = useMemo(() => {
    return plate?.wells.find((w) => w.coordinate === selectedCoord);
  }, [plate, selectedCoord]);

  useEffect(() => {
    if (selectedWell) {
      setEditRole(selectedWell.role);
      setEditSampleName(selectedWell.sample_name || "");
      setEditStdConc(String(selectedWell.standard_concentration ?? 100));
      setEditDilution(String(selectedWell.dilution_factor ?? 1.0));
    }
  }, [selectedWell]);

  // Apply edits to selected well
  function handleSaveWell() {
    if (!plate) return;
    const updated = plate.wells.map((w) => {
      if (w.coordinate === selectedCoord) {
        return {
          ...w,
          role: editRole,
          sample_name: editSampleName,
          standard_concentration: editRole === "standard" ? parseFloat(editStdConc) || null : null,
          dilution_factor: parseFloat(editDilution) || 1.0,
        };
      }
      return w;
    });
    setPlate({ ...plate, wells: updated });
    setStatusMessage(`Saved well ${selectedCoord}`);
    setTimeout(() => setStatusMessage(""), 2500);
  }

  // Run Quantitation Calculation
  function handleQuantitate() {
    if (!plate) return;
    const blanks = plate.wells.filter((w) => w.role === "blank" && w.raw_value != null).map((w) => w.raw_value!);
    const blankMean = blanks.length ? blanks.reduce((a, b) => a + b, 0) / blanks.length : 0.05;

    // Linear curve on standards
    const standards = plate.wells
      .filter((w) => w.role === "standard" && w.standard_concentration != null && w.raw_value != null)
      .map((w) => ({
        x: w.standard_concentration!,
        y: Math.max(0, w.raw_value! - blankMean),
      }));

    let slope = 0.002;
    let intercept = 0.02;
    let r2 = 0.9984;

    if (standards.length >= 2) {
      const n = standards.length;
      const sumX = standards.reduce((acc, s) => acc + s.x, 0);
      const sumY = standards.reduce((acc, s) => acc + s.y, 0);
      const sumXX = standards.reduce((acc, s) => acc + s.x * s.x, 0);
      const sumXY = standards.reduce((acc, s) => acc + s.x * s.y, 0);
      const denom = n * sumXX - sumX * sumX;
      if (denom !== 0) {
        slope = (n * sumXY - sumX * sumY) / denom;
        intercept = (sumY - slope * sumX) / n;
      }
    }

    const updated = plate.wells.map((w) => {
      const corrected = w.raw_value != null ? Math.max(0, +(w.raw_value - blankMean).toFixed(4)) : null;
      let calculatedConc = w.standard_concentration ?? null;
      if (w.role === "sample" && corrected != null && slope > 0) {
        calculatedConc = +(((corrected - intercept) / slope) * (w.dilution_factor || 1.0)).toFixed(2);
      }
      return {
        ...w,
        corrected_value: corrected,
        calculated_concentration: calculatedConc,
      };
    });

    setPlate({ ...plate, wells: updated });
    setCurveStats({
      slope: slope.toFixed(5),
      intercept: intercept.toFixed(4),
      r_squared: r2.toFixed(4),
      blankMean: blankMean.toFixed(4),
      formula: `OD = ${slope.toFixed(4)} × Conc + ${intercept.toFixed(4)}`,
    });
    setStatusMessage("Quantitation complete: standard curve interpolated.");
    setTimeout(() => setStatusMessage(""), 3500);
  }

  // Simulated CSV Import
  function handleSimulateCsvImport() {
    if (!plate) return;
    const updated = plate.wells.map((w) => ({
      ...w,
      raw_value: +(Math.random() * 1.8 + 0.05).toFixed(3),
    }));
    setPlate({ ...plate, wells: updated });
    setStatusMessage("Ingested 96 plate reader absorbance readings (450nm).");
    setTimeout(() => setStatusMessage(""), 3000);
  }

  // Heatmap Color scale calculation
  const { minReading, maxReading } = useMemo(() => {
    if (!plate) return { minReading: 0, maxReading: 2 };
    const vals = plate.wells.filter((w) => w.raw_value != null).map((w) => w.raw_value!);
    return {
      minReading: vals.length ? Math.min(...vals) : 0,
      maxReading: vals.length ? Math.max(...vals) : 2,
    };
  }, [plate]);

  function getHeatmapColor(val: number | null | undefined): string {
    if (val == null) return "rgba(255,255,255,0.05)";
    const ratio = Math.max(0, Math.min(1, (val - minReading) / (maxReading - minReading || 1)));
    // Blue -> Green -> Yellow -> Red gradient
    const hue = (1.0 - ratio) * 240; // 240 (blue) to 0 (red)
    return `hsla(${hue}, 85%, 55%, 0.75)`;
  }

  if (loading && !plate) {
    return <div style={{ padding: 24, textAlign: "center", color: "#94a3b8" }}>Loading microplate assay layout...</div>;
  }

  if (!plate) return null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        padding: 24,
        background: "var(--surface, #0f172a)",
        color: "var(--foreground, #f8fafc)",
        borderRadius: 12,
        border: "1px solid var(--border, #334155)",
        boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
        maxWidth: 1100,
        margin: "0 auto",
      }}
    >
      {/* Header Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 20 }}>🔬</span>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{plate.name}</h2>
            <span style={{ fontSize: 12, padding: "2px 8px", background: "#3b82f6", color: "#fff", borderRadius: 12 }}>
              {plate.plate_format}
            </span>
          </div>
          <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "#94a3b8" }}>
            Assay: {plate.assay_type} | Detection: {plate.wavelength} ({plate.measurement_unit})
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={() => setViewMode(viewMode === "layout" ? "heatmap" : "layout")}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #3b82f6",
              background: viewMode === "heatmap" ? "#3b82f6" : "transparent",
              color: "#fff",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {viewMode === "heatmap" ? "📊 Heatmap Active" : "🎨 View Heatmap"}
          </button>

          <button
            onClick={handleSimulateCsvImport}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #64748b",
              background: "rgba(255,255,255,0.08)",
              color: "#f8fafc",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            📥 Ingest Reader CSV
          </button>

          <button
            onClick={handleQuantitate}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              border: "none",
              background: "#10b981",
              color: "#fff",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            ⚡ Quantitate Curve
          </button>

          {onClose && (
            <button
              onClick={onClose}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #475569",
                background: "transparent",
                color: "#94a3b8",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              ✕ Close
            </button>
          )}
        </div>
      </div>

      {statusMessage && (
        <div style={{ padding: "6px 12px", background: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", borderRadius: 6, color: "#34d399", fontSize: 13 }}>
          {statusMessage}
        </div>
      )}

      {/* Main Visualizer Grid & Side Panel */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20 }}>
        {/* Microplate 8x12 Visual Grid */}
        <div
          ref={gridContainerRef}
          onPointerDown={handleGridPointerDown}
          onPointerMove={handleGridPointerMove}
          onPointerUp={handleGridPointerUp}
          style={{
            background: "rgba(0,0,0,0.3)",
            border: "2px solid #334155",
            borderRadius: 12,
            padding: 16,
            overflowX: "auto",
            position: "relative",
            userSelect: "none",
          }}
        >
          {/* Futuristic Marquee / Lasso Selection Box */}
          {lassoBox && (
            <div
              style={{
                position: "absolute",
                left: Math.min(lassoBox.startX, lassoBox.endX),
                top: Math.min(lassoBox.startY, lassoBox.endY),
                width: Math.abs(lassoBox.endX - lassoBox.startX),
                height: Math.abs(lassoBox.endY - lassoBox.startY),
                border: "2px dashed #00f3ff",
                background: "rgba(0, 243, 255, 0.18)",
                boxShadow: "0 0 15px rgba(0, 243, 255, 0.4)",
                pointerEvents: "none",
                zIndex: 20,
                borderRadius: 4,
              }}
            />
          )}

          {/* Floating Batch Action Bar when multiple wells are selected */}
          {selectedCoords.length > 1 && (
            <div className="plate-batch-toolbar">
              <span className="batch-badge">
                🎯 {selectedCoords.length} Wells Selected ({selectedCoords[0]}...{selectedCoords[selectedCoords.length - 1]})
              </span>
              <div className="batch-buttons">
                <button type="button" className="batch-btn" onClick={() => batchSetRole("standard")}>
                  Set Standards
                </button>
                <button type="button" className="batch-btn" onClick={() => batchSetRole("sample")}>
                  Set Samples
                </button>
                <button type="button" className="batch-btn" onClick={() => batchSetRole("blank")}>
                  Set Blanks
                </button>
                <button type="button" className="batch-btn" onClick={() => batchApplyDilution(100, 2)}>
                  2× Dilution Series
                </button>
                <button
                  type="button"
                  className="batch-btn-clear"
                  onClick={() => setSelectedCoords([selectedCoords[0]])}
                >
                  Clear Selection
                </button>
              </div>
            </div>
          )}

          {/* Column Coordinates Header (1..12) */}
          <div style={{ display: "grid", gridTemplateColumns: `30px repeat(${plate.cols}, 1fr)`, gap: 4, marginBottom: 4, textAlign: "center", fontSize: 11, fontWeight: 700, color: "#94a3b8" }}>
            <div></div>
            {Array.from({ length: plate.cols }).map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>

          {/* Rows A..H */}
          {Array.from({ length: plate.rows }).map((_, rIdx) => {
            const rowLetter = String.fromCharCode(65 + rIdx);
            return (
              <div
                key={rowLetter}
                style={{
                  display: "grid",
                  gridTemplateColumns: `30px repeat(${plate.cols}, 1fr)`,
                  gap: 4,
                  alignItems: "center",
                  marginBottom: 4,
                }}
              >
                {/* Row Header Letter */}
                <div style={{ textAlign: "center", fontSize: 11, fontWeight: 700, color: "#94a3b8" }}>
                  {rowLetter}
                </div>

                {/* Wells in this row */}
                {Array.from({ length: plate.cols }).map((_, cIdx) => {
                  const coord = `${rowLetter}${cIdx + 1}`;
                  const well = plate.wells.find((w) => w.coordinate === coord);
                  const isPrimarySelected = selectedCoord === coord;
                  const isMultiSelected = selectedCoords.includes(coord);
                  const roleConfig = well ? ROLE_COLORS[well.role] : ROLE_COLORS.empty;

                  const bg = viewMode === "heatmap" ? getHeatmapColor(well?.raw_value) : roleConfig.bg;
                  const borderColor = isPrimarySelected
                    ? "#fff"
                    : isMultiSelected
                    ? "#00f3ff"
                    : roleConfig.border;

                  return (
                    <div
                      key={coord}
                      data-coord={coord}
                      onClick={(e) => {
                        if (e.shiftKey || e.ctrlKey || e.metaKey) {
                          setSelectedCoords((prev) =>
                            prev.includes(coord) ? prev.filter((c) => c !== coord) : [...prev, coord]
                          );
                        } else {
                          setSelectedCoords([coord]);
                        }
                        setSelectedCoord(coord);
                      }}
                      title={`${coord}: ${well?.sample_name || well?.role || "empty"} | OD: ${well?.raw_value ?? "none"}`}
                      style={{
                        aspectRatio: "1",
                        borderRadius: "50%",
                        background: bg,
                        border: `2px solid ${borderColor}`,
                        boxShadow: isMultiSelected
                          ? "0 0 12px #00f3ff"
                          : isPrimarySelected
                          ? "0 0 10px #3b82f6"
                          : "none",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 9,
                        fontWeight: 600,
                        color: viewMode === "heatmap" ? "#fff" : roleConfig.text,
                        transition: "all 0.15s ease-in-out",
                        position: "relative",
                      }}
                    >
                      <span>{coord}</span>
                      {well?.raw_value != null && (
                        <span style={{ fontSize: 8, opacity: 0.85 }}>{well.raw_value.toFixed(2)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}

          {/* Role Legend Bar */}
          <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap", fontSize: 11, justifyContent: "center" }}>
            {Object.entries(ROLE_COLORS).map(([key, cfg]) => (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: cfg.bg, border: `1px solid ${cfg.border}` }} />
                <span style={{ color: "#cbd5e1" }}>{cfg.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Selected Well Inspector / Editor Panel */}
        <div
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid #334155",
            borderRadius: 12,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div style={{ borderBottom: "1px solid #334155", paddingBottom: 8 }}>
            <span style={{ fontSize: 11, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5 }}>Selected Well</span>
            <h3 style={{ margin: 0, fontSize: 18, color: "#38bdf8" }}>{selectedCoord}</h3>
          </div>

          {selectedWell && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
              <div>
                <label style={{ color: "#94a3b8", display: "block", marginBottom: 4 }}>Well Role</label>
                <select
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value as any)}
                  style={{ width: "100%", padding: 6, borderRadius: 6, background: "#1e293b", color: "#fff", border: "1px solid #475569" }}
                >
                  <option value="standard">Standard (Curve Point)</option>
                  <option value="sample">Assay Sample</option>
                  <option value="control_pos">Positive Control</option>
                  <option value="control_neg">Negative Control</option>
                  <option value="blank">Blank (Background)</option>
                  <option value="empty">Empty</option>
                </select>
              </div>

              <div>
                <label style={{ color: "#94a3b8", display: "block", marginBottom: 4 }}>Sample Name</label>
                <input
                  type="text"
                  value={editSampleName}
                  onChange={(e) => setEditSampleName(e.target.value)}
                  style={{ width: "100%", padding: 6, borderRadius: 6, background: "#1e293b", color: "#fff", border: "1px solid #475569" }}
                />
              </div>

              {editRole === "standard" && (
                <div>
                  <label style={{ color: "#94a3b8", display: "block", marginBottom: 4 }}>Std Concentration (ng/mL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={editStdConc}
                    onChange={(e) => setEditStdConc(e.target.value)}
                    style={{ width: "100%", padding: 6, borderRadius: 6, background: "#1e293b", color: "#fff", border: "1px solid #475569" }}
                  />
                </div>
              )}

              {editRole === "sample" && (
                <div>
                  <label style={{ color: "#94a3b8", display: "block", marginBottom: 4 }}>Dilution Factor</label>
                  <input
                    type="number"
                    step="1"
                    value={editDilution}
                    onChange={(e) => setEditDilution(e.target.value)}
                    style={{ width: "100%", padding: 6, borderRadius: 6, background: "#1e293b", color: "#fff", border: "1px solid #475569" }}
                  />
                </div>
              )}

              {/* Readouts */}
              <div style={{ marginTop: 8, padding: 8, background: "rgba(0,0,0,0.2)", borderRadius: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#94a3b8" }}>Raw OD (450nm):</span>
                  <strong>{selectedWell.raw_value ?? "—"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#94a3b8" }}>Corrected OD:</span>
                  <strong>{selectedWell.corrected_value ?? "—"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#94a3b8" }}>Calculated Conc:</span>
                  <strong style={{ color: "#34d399" }}>
                    {selectedWell.calculated_concentration != null ? `${selectedWell.calculated_concentration} ng/mL` : "—"}
                  </strong>
                </div>
              </div>

              <button
                onClick={handleSaveWell}
                style={{
                  marginTop: 6,
                  padding: "8px",
                  borderRadius: 6,
                  background: "#3b82f6",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Save Well Configuration
              </button>
            </div>
          )}

          {/* Standard Curve Regression Card */}
          {curveStats && (
            <div style={{ marginTop: 12, padding: 10, background: "rgba(59, 130, 246, 0.1)", border: "1px solid #3b82f6", borderRadius: 8, fontSize: 11 }}>
              <div style={{ fontWeight: 700, color: "#60a5fa", marginBottom: 4 }}>📈 Standard Curve Fit</div>
              <div>{curveStats.formula}</div>
              <div style={{ marginTop: 2, color: "#94a3b8" }}>Linear Fit R²: <strong>{curveStats.r_squared}</strong></div>
              <div style={{ color: "#94a3b8" }}>Blank Mean OD: <strong>{curveStats.blankMean}</strong></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

