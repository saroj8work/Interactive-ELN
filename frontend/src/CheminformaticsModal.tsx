import { useState, useEffect } from "react";
import {
  cheminformaticsApi,
  ChemicalCompound,
  ChemicalAnalysis,
  ChemicalPreset,
} from "./api";
import { ChemicalCanvas } from "./ChemicalCanvas";

interface CheminformaticsModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  onInsertIntoNotebook?: (markdown: string) => void;
}

export function CheminformaticsModal({
  isOpen,
  onClose,
  selectedProjectId,
  selectedExperimentId,
  onInsertIntoNotebook,
}: CheminformaticsModalProps) {
  const [smilesInput, setSmilesInput] = useState<string>("CC(=O)Oc1ccccc1C(=O)O"); // Default Aspirin
  const [compoundName, setCompoundName] = useState<string>("Aspirin (Acetylsalicylic Acid)");
  const [analysis, setAnalysis] = useState<ChemicalAnalysis | null>(null);
  const [presets, setPresets] = useState<ChemicalPreset[]>([]);
  const [compoundsList, setCompoundsList] = useState<ChemicalCompound[]>([]);
  const [activeTab, setActiveTab] = useState<"analyzer" | "draw" | "library">("analyzer");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>("");

  useEffect(() => {
    if (!isOpen) return;
    loadPresets();
    loadLibrary();
    handleAnalyze(smilesInput, compoundName);
  }, [isOpen]);

  async function loadPresets() {
    try {
      const data = await cheminformaticsApi.getPresets();
      setPresets(data);
    } catch (err) {
      console.error("Failed to load presets:", err);
    }
  }

  async function loadLibrary() {
    try {
      const data = await cheminformaticsApi.list(selectedProjectId, selectedExperimentId, searchFilter);
      setCompoundsList(data);
    } catch (err) {
      console.error("Failed to load compounds library:", err);
    }
  }

  async function handleAnalyze(smiles: string, name?: string) {
    if (!smiles.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await cheminformaticsApi.analyze(smiles.trim(), name || compoundName);
      setAnalysis(res);
    } catch (err: any) {
      setError(err?.message || "Invalid or unsupported SMILES string syntax.");
    } finally {
      setLoading(false);
    }
  }

  function handleSelectPreset(preset: ChemicalPreset) {
    setSmilesInput(preset.smiles);
    setCompoundName(preset.name);
    void handleAnalyze(preset.smiles, preset.name);
  }

  async function handleSaveCompound() {
    if (!analysis) return;
    try {
      await cheminformaticsApi.save({
        name: compoundName || analysis.name,
        smiles: analysis.smiles,
        project_id: selectedProjectId,
        experiment_id: selectedExperimentId,
      });
      setSuccessMsg(`Saved "${compoundName || analysis.name}" to Chemical Registry!`);
      setTimeout(() => setSuccessMsg(null), 3000);
      void loadLibrary();
    } catch (err: any) {
      setError(err?.message || "Failed to save compound.");
    }
  }

  function handleInsertMarkdown() {
    if (!analysis || !onInsertIntoNotebook) return;
    const md = `
### 🧪 Chemical Structure: ${compoundName || analysis.name}
- **Formula:** ${analysis.formula}
- **SMILES:** \`${analysis.smiles}\`
- **Molecular Weight:** ${analysis.molecular_weight} g/mol
- **LogP:** ${analysis.logp}
- **TPSA:** ${analysis.tpsa} Å²
- **Lipinski Violations:** ${analysis.rule_of_five_violations} (Drug-likeness: ${Math.round(analysis.drug_likeness_score * 100)}%)
- **GHS Hazards:** ${analysis.ghs_hazard_codes || "None reported"}
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  async function handleDeleteCompound(id: number) {
    if (!confirm("Are you sure you want to remove this compound from the registry?")) return;
    try {
      await cheminformaticsApi.delete(id);
      void loadLibrary();
    } catch (err: any) {
      setError(err?.message || "Failed to delete compound.");
    }
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content chemical-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">CHEMINFORMATICS SUITE</span>
            <h2>Molecular Structure & Drug-Likeness Engine</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Tab Controls */}
        <div className="subnav-tabs">
          <button
            className={`tab-btn ${activeTab === "analyzer" ? "active" : ""}`}
            onClick={() => setActiveTab("analyzer")}
          >
            🔬 Structure Analyzer & 2D Vector View
          </button>
          <button
            className={`tab-btn ${activeTab === "draw" ? "active" : ""}`}
            onClick={() => setActiveTab("draw")}
          >
            ✏️ Draw Molecule (Interactive 2D Canvas)
          </button>
          <button
            className={`tab-btn ${activeTab === "library" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("library");
              void loadLibrary();
            }}
          >
            📚 Chemical Registry ({compoundsList.length})
          </button>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {successMsg && <div className="callout callout-success">{successMsg}</div>}

        {activeTab === "draw" && (
          <div className="chemical-draw-layout">
            <div className="draw-header-desc">
              <h3>Interactive 2D Vector Bond Canvas</h3>
              <p>Place atoms, connect single/double/triple bonds, or stamp rings. Click <strong>⚡ Analyze Structure</strong> to calculate molecular weight, Lipinski Rule of 5 properties, and generate vector depictions.</p>
            </div>
            <ChemicalCanvas
              onGenerateSmiles={(smiles) => {
                setSmilesInput(smiles);
                setCompoundName("Custom Drawn Molecule");
                void handleAnalyze(smiles, "Custom Drawn Molecule");
                setActiveTab("analyzer");
              }}
            />
          </div>
        )}

        {activeTab === "analyzer" ? (
          <div className="chemical-analyzer-layout">
            {/* Left Controls & Presets */}
            <div className="chemical-controls-col">
              <div className="input-field-group">
                <label className="field-label">Compound Name</label>
                <input
                  type="text"
                  className="input-text"
                  value={compoundName}
                  onChange={(e) => setCompoundName(e.target.value)}
                  placeholder="e.g. Aspirin, Doxorubicin"
                />
              </div>

              <div className="input-field-group">
                <label className="field-label">Simplified Molecular Input Line Entry (SMILES)</label>
                <div className="smiles-input-row">
                  <input
                    type="text"
                    className="input-text font-mono"
                    value={smilesInput}
                    onChange={(e) => setSmilesInput(e.target.value)}
                    placeholder="Enter SMILES e.g. CC(=O)Oc1ccccc1C(=O)O"
                  />
                  <button
                    className="button button-primary"
                    onClick={() => handleAnalyze(smilesInput, compoundName)}
                    disabled={loading}
                  >
                    {loading ? "Parsing..." : "Analyze"}
                  </button>
                </div>
              </div>

              {/* Presets library */}
              <div className="presets-block">
                <label className="field-label">Quick Lab Presets:</label>
                <div className="preset-pill-list">
                  {presets.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      className="preset-pill"
                      onClick={() => handleSelectPreset(p)}
                      title={p.description}
                    >
                      {p.name.split(" ")[0]}
                    </button>
                  ))}
                </div>
              </div>

              {/* 2D Molecular SVG Depiction View */}
              <div className="molecule-canvas-card">
                <div className="canvas-header">
                  <h4>2D Molecular Structure Depiction</h4>
                  <span className="badge-dim">Auto Force-Directed Spring Layout</span>
                </div>
                <div
                  className="svg-viewer-container"
                  dangerouslySetInnerHTML={{ __html: analysis?.svg_depiction || "" }}
                />
              </div>

              {/* Action Buttons */}
              <div className="chemical-actions-row">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handleSaveCompound}
                  disabled={!analysis}
                >
                  💾 Save to Chemical Registry
                </button>
                {onInsertIntoNotebook && (
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={handleInsertMarkdown}
                    disabled={!analysis}
                  >
                    📝 Insert Summary into Notebook
                  </button>
                )}
              </div>
            </div>

            {/* Right Property Inspector & Lipinski Scorecard */}
            <div className="chemical-inspector-col">
              {analysis ? (
                <>
                  {/* Molecular Formula & Masses */}
                  <div className="prop-card">
                    <h4>Molecular Descriptors</h4>
                    <div className="prop-grid">
                      <div className="prop-stat">
                        <span className="stat-label">Hill Formula</span>
                        <span className="stat-value font-mono highlight-cyan">{analysis.formula}</span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Molecular Weight</span>
                        <span className="stat-value">{analysis.molecular_weight} <small>g/mol</small></span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Calculated LogP</span>
                        <span className="stat-value">{analysis.logp}</span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Polar Surface Area (TPSA)</span>
                        <span className="stat-value">{analysis.tpsa} <small>Å²</small></span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Rotatable Bonds</span>
                        <span className="stat-value">{analysis.rotatable_bonds}</span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Monoisotopic Mass</span>
                        <span className="stat-value">{analysis.monoisotopic_mass.toFixed(3)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Lipinski Rule of 5 Evaluation */}
                  <div className="prop-card">
                    <div className="card-header-flex">
                      <h4>Lipinski's Rule of 5 (Drug-Likeness)</h4>
                      <span
                        className={`badge-tag ${
                          analysis.rule_of_five_violations === 0
                            ? "tag-pass"
                            : analysis.rule_of_five_violations === 1
                            ? "tag-warning"
                            : "tag-fail"
                        }`}
                      >
                        {analysis.rule_of_five_violations === 0
                          ? "COMPLIANT (0 Violations)"
                          : `${analysis.rule_of_five_violations} Violation(s)`}
                      </span>
                    </div>

                    <table className="lipinski-table">
                      <thead>
                        <tr>
                          <th>Criterion</th>
                          <th>Threshold</th>
                          <th>Calculated</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Molecular Weight (MW)</td>
                          <td>≤ 500 Da</td>
                          <td>{analysis.molecular_weight} Da</td>
                          <td>
                            <span className={analysis.molecular_weight <= 500 ? "status-pass" : "status-fail"}>
                              {analysis.molecular_weight <= 500 ? "✓ Pass" : "✕ Exceeded"}
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>Lipophilicity (LogP)</td>
                          <td>≤ 5.0</td>
                          <td>{analysis.logp}</td>
                          <td>
                            <span className={analysis.logp <= 5.0 ? "status-pass" : "status-fail"}>
                              {analysis.logp <= 5.0 ? "✓ Pass" : "✕ Exceeded"}
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>H-Bond Donors (HBD)</td>
                          <td>≤ 5</td>
                          <td>{analysis.hbd}</td>
                          <td>
                            <span className={analysis.hbd <= 5 ? "status-pass" : "status-fail"}>
                              {analysis.hbd <= 5 ? "✓ Pass" : "✕ Exceeded"}
                            </span>
                          </td>
                        </tr>
                        <tr>
                          <td>H-Bond Acceptors (HBA)</td>
                          <td>≤ 10</td>
                          <td>{analysis.hba}</td>
                          <td>
                            <span className={analysis.hba <= 10 ? "status-pass" : "status-fail"}>
                              {analysis.hba <= 10 ? "✓ Pass" : "✕ Exceeded"}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>

                    <div className="score-bar-container">
                      <div className="score-label-row">
                        <span>Overall Drug-Likeness Confidence Score:</span>
                        <span className="score-val">{Math.round(analysis.drug_likeness_score * 100)}%</span>
                      </div>
                      <div className="score-track">
                        <div
                          className="score-fill"
                          style={{
                            width: `${Math.round(analysis.drug_likeness_score * 100)}%`,
                            backgroundColor:
                              analysis.drug_likeness_score >= 0.75
                                ? "#10b981"
                                : analysis.drug_likeness_score >= 0.5
                                ? "#f59e0b"
                                : "#ef4444",
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* GHS Hazard Descriptors & Safety Warnings */}
                  <div className="prop-card">
                    <h4>GHS Safety Descriptors & HazMat Class</h4>
                    <div className="hazard-badges-row">
                      {analysis.ghs_pictograms ? (
                        analysis.ghs_pictograms.split(",").map((pic) => (
                          <div key={pic} className="ghs-badge">
                            <span className="ghs-icon">⚠️</span>
                            <span className="ghs-code">{pic}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-muted">No hazardous moieties detected.</span>
                      )}
                    </div>
                    {analysis.ghs_hazard_codes && (
                      <p className="hazard-notes">
                        Associated Hazard Statements: <code className="font-mono">{analysis.ghs_hazard_codes}</code>
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <div className="empty-analysis-hint">
                  <p>Enter a SMILES sequence or choose a preset to evaluate molecular properties.</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Library Tab */
          <div className="chemical-library-view">
            <div className="library-toolbar">
              <input
                type="text"
                className="input-text search-input"
                placeholder="Search registry by compound name, formula, or SMILES..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
              />
              <button className="button button-secondary" onClick={loadLibrary}>
                Refresh
              </button>
            </div>

            {compoundsList.length === 0 ? (
              <div className="empty-library">
                <p>No chemical structures registered in this project yet.</p>
              </div>
            ) : (
              <div className="compound-cards-grid">
                {compoundsList.map((comp) => (
                  <div key={comp.id} className="compound-item-card">
                    <div className="item-svg" dangerouslySetInnerHTML={{ __html: comp.svg_depiction }} />
                    <div className="item-info">
                      <h4>{comp.name}</h4>
                      <p className="item-formula font-mono">{comp.formula} • {comp.molecular_weight} g/mol</p>
                      <p className="item-smiles font-mono" title={comp.smiles}>
                        {comp.smiles.length > 36 ? comp.smiles.slice(0, 36) + "..." : comp.smiles}
                      </p>
                      <div className="item-meta-row">
                        <span className="badge-tag">LogP: {comp.logp}</span>
                        <span className={`badge-tag ${comp.rule_of_five_violations === 0 ? "tag-pass" : "tag-warning"}`}>
                          Ro5: {comp.rule_of_five_violations} viol.
                        </span>
                      </div>
                      <div className="item-actions-row">
                        <button
                          className="button-link"
                          onClick={() => {
                            setSmilesInput(comp.smiles);
                            setCompoundName(comp.name);
                            setActiveTab("analyzer");
                            void handleAnalyze(comp.smiles, comp.name);
                          }}
                        >
                          Inspect & Edit
                        </button>
                        <button
                          className="button-link text-danger"
                          onClick={() => handleDeleteCompound(comp.id)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
