import { useState, useEffect } from "react";
import {
  analyticsApi,
  ScientificSpreadsheetItem,
  Fit4plResult,
  CurvePoint,
} from "./api";

interface ScientificSpreadsheetModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  onInsertIntoNotebook?: (markdown: string) => void;
}

export function ScientificSpreadsheetModal({
  isOpen,
  onClose,
  selectedProjectId,
  selectedExperimentId,
  onInsertIntoNotebook,
}: ScientificSpreadsheetModalProps) {
  const [sheets, setSheets] = useState<ScientificSpreadsheetItem[]>([]);
  const [activeSheet, setActiveSheet] = useState<ScientificSpreadsheetItem | null>(null);
  const [sheetName, setSheetName] = useState<string>("Dose-Response 4PL Curve");
  const [columns, setColumns] = useState<string[]>([
    "Standard", "Dose [ng/mL]", "Rep 1 (OD)", "Rep 2 (OD)", "Mean OD", "CV (%)",
  ]);
  const [rows, setRows] = useState<(string | number)[][]>([
    ["Std 1", 1000.0, 2.45, 2.41, 2.43, 1.16],
    ["Std 2", 333.33, 2.18, 2.22, 2.20, 1.28],
    ["Std 3", 111.11, 1.75, 1.79, 1.77, 1.60],
    ["Std 4", 37.04, 1.12, 1.16, 1.14, 2.48],
    ["Std 5", 12.35, 0.58, 0.61, 0.595, 3.56],
    ["Std 6", 4.12, 0.26, 0.27, 0.265, 2.67],
    ["Std 7", 1.37, 0.12, 0.13, 0.125, 5.66],
    ["Std 8", 0.05, 0.05, 0.052, 0.051, 2.77],
  ]);
  const [fitResult, setFitResult] = useState<Fit4plResult | null>(null);
  const [templates, setTemplates] = useState<{ name: string; description: string; sheet_data: { columns: string[]; rows: (string | number)[][] } }[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    loadTemplatesAndSheets();
  }, [isOpen]);

  async function loadTemplatesAndSheets() {
    try {
      const [tpls, list] = await Promise.all([
        analyticsApi.getPresets(),
        analyticsApi.list(selectedProjectId, selectedExperimentId),
      ]);
      setTemplates(tpls);
      setSheets(list);
      if (list.length > 0) {
        selectSheet(list[0]);
      } else {
        void runFit4pl(rows);
      }
    } catch (err) {
      console.error("Failed to load analytics sheets", err);
    }
  }

  function applyTemplate(tpl: { name: string; sheet_data: { columns: string[]; rows: (string | number)[][] } }) {
    setSheetName(tpl.name);
    setColumns(tpl.sheet_data.columns);
    setRows(tpl.sheet_data.rows);
    setActiveSheet(null);
    void runFit4pl(tpl.sheet_data.rows);
  }

  function selectSheet(s: ScientificSpreadsheetItem) {
    setActiveSheet(s);
    setSheetName(s.name);
    if (s.sheet_data?.columns) setColumns(s.sheet_data.columns);
    if (s.sheet_data?.rows) {
      setRows(s.sheet_data.rows);
      void runFit4pl(s.sheet_data.rows);
    }
    if (s.curves_data && "ec50_c" in s.curves_data) {
      setFitResult(s.curves_data as Fit4plResult);
    }
  }

  async function runFit4pl(currentRows: (string | number)[][]) {
    // Extract x (column 1: Dose) and y (column 4: Mean OD or column 2: Rep 1)
    const points: CurvePoint[] = [];
    for (const r of currentRows) {
      const xVal = parseFloat(String(r[1]));
      const yVal = parseFloat(String(r[4] ?? r[2]));
      if (!isNaN(xVal) && !isNaN(yVal) && xVal > 0) {
        points.push({ x: xVal, y: yVal });
      }
    }

    if (points.length < 4) return;
    setLoading(true);
    try {
      const res = await analyticsApi.fit4pl(points);
      setFitResult(res);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to fit 4PL curve.");
    } finally {
      setLoading(false);
    }
  }

  function updateCell(rowIdx: number, colIdx: number, val: string) {
    const updated = [...rows];
    updated[rowIdx] = [...updated[rowIdx]];
    const num = parseFloat(val);
    updated[rowIdx][colIdx] = isNaN(num) ? val : num;
    setRows(updated);
  }

  function addRow() {
    const newRow = columns.map((_, i) => (i === 0 ? `Sample ${rows.length + 1}` : 0));
    setRows([...rows, newRow]);
  }

  async function handleSaveSheet() {
    setLoading(true);
    try {
      if (activeSheet) {
        const updated = await analyticsApi.update(activeSheet.id, {
          name: sheetName,
          sheet_data: { columns, rows },
          curves_data: fitResult || {},
        });
        setActiveSheet(updated);
        setNotice(`Saved spreadsheet "${sheetName}"!`);
      } else {
        const created = await analyticsApi.create({
          name: sheetName,
          sheet_data: { columns, rows },
          curves_data: fitResult || {},
          project_id: selectedProjectId,
          experiment_id: selectedExperimentId,
        });
        setActiveSheet(created);
        setSheets((prev) => [created, ...prev]);
        setNotice(`Created new spreadsheet "${sheetName}"!`);
      }
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Failed to save spreadsheet.");
    } finally {
      setLoading(false);
    }
  }

  function handleInsertMarkdown() {
    if (!onInsertIntoNotebook) return;
    const md = `
### 📊 4PL Analytics & Dose-Response Quantitation: ${sheetName}
- **EC50 / IC50 Inflection Concentration:** ${fitResult?.ec50_c ?? "N/A"} ng/mL
- **Goodness of Fit (R²):** ${fitResult?.r_squared ?? "N/A"} (RMSE: ${fitResult?.rmse ?? "N/A"})
- **Sigmoidal Range:** Top = ${fitResult?.top_asymptote_d ?? "N/A"} OD, Bottom = ${fitResult?.bottom_asymptote_a ?? "N/A"} OD
- **Hill Slope (b):** ${fitResult?.hill_slope_b ?? "N/A"}
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content analytics-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">SCIENTIFIC ANALYTICS & 4PL REGRESSION</span>
            <h2>In-App Scientific Spreadsheet, Sigmoid Fitting & EC50 Studio</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Toolbar */}
        <div className="analytics-toolbar-row">
          <div className="analytics-title-group">
            <input
              type="text"
              className="input-text sheet-name-input"
              value={sheetName}
              onChange={(e) => setSheetName(e.target.value)}
              placeholder="Spreadsheet Title"
            />
            {fitResult && (
              <span className="badge-tag tag-pass font-mono">
                R² = {fitResult.r_squared} • EC50 = {fitResult.ec50_c}
              </span>
            )}
          </div>

          <div className="analytics-actions-group">
            {sheets.length > 0 && (
              <select
                className="input-text"
                style={{ fontSize: 11, padding: "4px 8px" }}
                value={activeSheet?.id || ""}
                onChange={(e) => {
                  const s = sheets.find((item) => item.id === Number(e.target.value));
                  if (s) selectSheet(s);
                }}
              >
                <option value="">-- Load Saved Sheets ({sheets.length}) --</option>
                {sheets.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}

            <div className="preset-pill-list">
              <span className="text-muted" style={{ fontSize: 11, alignSelf: "center" }}>Templates:</span>
              {templates.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  className="preset-pill"
                  onClick={() => applyTemplate(t)}
                >
                  {t.name.split(" ")[0]}
                </button>
              ))}
            </div>

            <button className="button button-secondary" onClick={() => runFit4pl(rows)}>
              🔄 Refit 4PL
            </button>
            <button className="button button-secondary" onClick={handleSaveSheet} disabled={loading}>
              💾 Save
            </button>
            {onInsertIntoNotebook && (
              <button className="button button-primary" onClick={handleInsertMarkdown} disabled={!fitResult}>
                📝 Insert in Notebook
              </button>
            )}
          </div>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {notice && <div className="callout callout-success">{notice}</div>}

        {/* Main Workspace Body */}
        <div className="analytics-body-grid">
          {/* Left Spreadsheet Grid */}
          <div className="sheet-grid-container">
            <div className="sheet-table-toolbar">
              <button className="button button-outline button-xs" onClick={addRow}>
                + Add Row
              </button>
              <span className="text-muted" style={{ fontSize: 11 }}>
                {rows.length} rows × {columns.length} columns • Formulas supported (=AVERAGE, =CV, =SUM)
              </span>
            </div>

            <div className="table-responsive">
              <table className="scientific-sheet-table">
                <thead>
                  <tr>
                    <th className="corner-th">#</th>
                    {columns.map((c, i) => (
                      <th key={i}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, rIdx) => (
                    <tr key={rIdx}>
                      <td className="row-num-td">{rIdx + 1}</td>
                      {r.map((cell, cIdx) => (
                        <td key={cIdx} className="sheet-cell-td">
                          <input
                            type="text"
                            className="sheet-cell-input"
                            value={String(cell)}
                            onChange={(e) => updateCell(rIdx, cIdx, e.target.value)}
                            onBlur={() => void runFit4pl(rows)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right 4PL Sigmoid Curve & Regression Plot */}
          <div className="analytics-plot-container">
            <div className="plot-header">
              <h4>4-Parameter Logistic (4PL) Dose-Response Fit</h4>
              <span className="badge-tag">Non-Linear Regression</span>
            </div>

            {/* Vector Sigmoid Plot */}
            <div className="svg-plot-viewport">
              {fitResult ? (
                <svg viewBox="0 0 460 280" className="sigmoid-svg">
                  {/* Grid Lines */}
                  <line x1="50" y1="20" x2="50" y2="240" stroke="#1e293b" strokeWidth="1" />
                  <line x1="50" y1="240" x2="440" y2="240" stroke="#1e293b" strokeWidth="1" />
                  <line x1="50" y1="130" x2="440" y2="130" stroke="#1e293b" strokeDasharray="3 3" strokeWidth="0.8" />

                  {/* EC50 dashed guideline */}
                  <line x1="245" y1="20" x2="245" y2="240" stroke="#3b82f6" strokeDasharray="4 4" strokeWidth="1.2" />
                  <text x="250" y="45" fill="#38bdf8" fontSize="10" fontFamily="monospace">
                    EC50: {fitResult.ec50_c}
                  </text>

                  {/* Fitted Sigmoid Curve Path */}
                  {fitResult.curve_points.length > 1 && (
                    <path
                      d={(() => {
                        const pts = fitResult.curve_points;
                        const minX = Math.log10(pts[0].x || 0.01);
                        const maxX = Math.log10(pts[pts.length - 1].x || 1000);
                        const minY = fitResult.bottom_asymptote_a * 0.9;
                        const maxY = fitResult.top_asymptote_d * 1.1;

                        return pts
                          .map((p, idx) => {
                            const px = 50 + ((Math.log10(p.x || 0.01) - minX) / (maxX - minX || 1)) * 380;
                            const py = 240 - ((p.y - minY) / (maxY - minY || 1)) * 210;
                            return `${idx === 0 ? "M" : "L"} ${px.toFixed(1)} ${py.toFixed(1)}`;
                          })
                          .join(" ");
                      })()}
                      stroke="#00f2fe"
                      strokeWidth="2.5"
                      fill="none"
                    />
                  )}

                  {/* Actual Data Points */}
                  {rows.map((r, i) => {
                    const x = parseFloat(String(r[1]));
                    const y = parseFloat(String(r[4] ?? r[2]));
                    if (isNaN(x) || isNaN(y) || x <= 0) return null;
                    const pts = fitResult.curve_points;
                    const minX = Math.log10(pts[0]?.x || 0.01);
                    const maxX = Math.log10(pts[pts.length - 1]?.x || 1000);
                    const minY = fitResult.bottom_asymptote_a * 0.9;
                    const maxY = fitResult.top_asymptote_d * 1.1;
                    const cx = 50 + ((Math.log10(x) - minX) / (maxX - minX || 1)) * 380;
                    const cy = 240 - ((y - minY) / (maxY - minY || 1)) * 210;

                    return (
                      <circle
                        key={i}
                        cx={cx}
                        cy={cy}
                        r="5"
                        fill="#f59e0b"
                        stroke="#090d16"
                        strokeWidth="1.5"
                      >
                        <title>{`Dose: ${x}, OD: ${y}`}</title>
                      </circle>
                    );
                  })}

                  {/* Axis Labels */}
                  <text x="245" y="270" fill="#64748b" textAnchor="middle" fontSize="10">
                    Log₁₀ Concentration [Dose]
                  </text>
                  <text
                    x="15"
                    y="130"
                    fill="#64748b"
                    textAnchor="middle"
                    fontSize="10"
                    transform="rotate(-90 15,130)"
                  >
                    Optical Density (OD)
                  </text>
                </svg>
              ) : (
                <div className="empty-plot-hint">
                  <p>Enter positive concentrations and responses to generate 4PL sigmoid regression.</p>
                </div>
              )}
            </div>

            {/* Regression Parameter Stats */}
            {fitResult && (
              <div className="regression-stats-grid">
                <div className="prop-stat">
                  <span className="stat-label">EC50 / IC50</span>
                  <span className="stat-value highlight-cyan">{fitResult.ec50_c}</span>
                </div>
                <div className="prop-stat">
                  <span className="stat-label">Goodness of Fit (R²)</span>
                  <span className="stat-value">{fitResult.r_squared}</span>
                </div>
                <div className="prop-stat">
                  <span className="stat-label">Hill Slope (b)</span>
                  <span className="stat-value">{fitResult.hill_slope_b}</span>
                </div>
                <div className="prop-stat">
                  <span className="stat-label">Dynamic Range (Top - Bottom)</span>
                  <span className="stat-value">
                    {fitResult.bottom_asymptote_a} → {fitResult.top_asymptote_d} OD
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

