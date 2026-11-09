import { FC, useState } from "react";

export interface CellLineRecord {
  id: number;
  name: string;
  organism: string;
  tissueSource: string;
  biosafetyLevel: number;
  currentPassage: number;
  maxRecommendedPassage: number;
  growthMedium: string;
  doublingTimeHours: number;
  viabilityPercent: number;
  seedingDensity: string;
  splitRatio: string;
  mycoplasmaStatus: "negative" | "positive" | "pending";
  lastPassagedDate: string;
  storageVialsCount: number;
  status: "active_culture" | "cryopreserved" | "quarantined";
}

interface CellCultureModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CellCultureModal: FC<CellCultureModalProps> = ({ isOpen, onClose }) => {
  const [cellLines, setCellLines] = useState<CellLineRecord[]>([
    {
      id: 1,
      name: "HEK293T (Human Embryonic Kidney)",
      organism: "Homo sapiens",
      tissueSource: "Embryonic Kidney (SV40 Large T Ag)",
      biosafetyLevel: 2,
      currentPassage: 14,
      maxRecommendedPassage: 25,
      growthMedium: "DMEM High Glucose + 10% FBS + 1% Pen-Strep",
      doublingTimeHours: 24.2,
      viabilityPercent: 97.4,
      seedingDensity: "2.0 × 10⁵ cells/mL",
      splitRatio: "1:6",
      mycoplasmaStatus: "negative",
      lastPassagedDate: "2026-11-04",
      storageVialsCount: 18,
      status: "active_culture",
    },
    {
      id: 2,
      name: "CHO-K1 (Chinese Hamster Ovary)",
      organism: "Cricetulus griseus",
      tissueSource: "Ovary (Biologics Expression Host)",
      biosafetyLevel: 1,
      currentPassage: 8,
      maxRecommendedPassage: 30,
      growthMedium: "F-12K Medium + 10% Dialyzed FBS + 2mM L-Glutamine",
      doublingTimeHours: 18.5,
      viabilityPercent: 98.9,
      seedingDensity: "3.5 × 10⁵ cells/mL",
      splitRatio: "1:8",
      mycoplasmaStatus: "negative",
      lastPassagedDate: "2026-11-05",
      storageVialsCount: 24,
      status: "active_culture",
    },
    {
      id: 3,
      name: "Jurkat Clone E6-1 (T Lymphocyte)",
      organism: "Homo sapiens",
      tissueSource: "Peripheral Blood (Acute T Cell Leukemia)",
      biosafetyLevel: 1,
      currentPassage: 26,
      maxRecommendedPassage: 25,
      growthMedium: "RPMI-1640 + 10% Heat-Inactivated FBS + 10mM HEPES",
      doublingTimeHours: 32.0,
      viabilityPercent: 91.2,
      seedingDensity: "1.0 × 10⁵ cells/mL",
      splitRatio: "1:4",
      mycoplasmaStatus: "negative",
      lastPassagedDate: "2026-11-02",
      storageVialsCount: 6,
      status: "active_culture",
    },
    {
      id: 4,
      name: "Human iPSC Line AURA-004",
      organism: "Homo sapiens",
      tissueSource: "Dermal Fibroblast Reprogrammed",
      biosafetyLevel: 1,
      currentPassage: 6,
      maxRecommendedPassage: 20,
      growthMedium: "mTeSR Plus on Matrigel Matrix",
      doublingTimeHours: 36.8,
      viabilityPercent: 95.8,
      seedingDensity: "5.0 × 10⁴ colonies/well",
      splitRatio: "1:3 (ReLeSR Gentle Enzyme)",
      mycoplasmaStatus: "negative",
      lastPassagedDate: "2026-11-03",
      storageVialsCount: 12,
      status: "active_culture",
    },
  ]);

  const [selectedCellLine, setSelectedCellLine] = useState<CellLineRecord>(cellLines[0]);
  const [activeTab, setActiveTab] = useState<"active" | "calculator" | "cryo">("active");
  const [notice, setNotice] = useState<string | null>(null);

  // Split calculation state
  const [currentViableCount, setCurrentViableCount] = useState<number>(4.8); // x10^6 cells
  const [targetDensity, setTargetDensity] = useState<number>(0.3); // x10^6 cells/mL
  const [flaskVolume, setFlaskVolume] = useState<number>(20); // mL T75 flask

  if (!isOpen) return null;

  // Handle passaging split
  const handlePassageCulture = () => {
    const nextP = selectedCellLine.currentPassage + 1;
    const updated = cellLines.map((c) =>
      c.id === selectedCellLine.id
        ? {
            ...c,
            currentPassage: nextP,
            lastPassagedDate: new Date().toISOString().slice(0, 10),
          }
        : c
    );
    setCellLines(updated);
    setSelectedCellLine((prev) => ({
      ...prev,
      currentPassage: nextP,
      lastPassagedDate: new Date().toISOString().slice(0, 10),
    }));
    setNotice(`Passage complete: ${selectedCellLine.name} advanced to P${nextP}.`);
    setTimeout(() => setNotice(null), 3500);
  };

  // Calculate required seeding volume
  const totalCellsNeeded = targetDensity * flaskVolume; // x10^6 cells
  const requiredCultureVolume = currentViableCount > 0 ? (totalCellsNeeded / currentViableCount) * 10 : 0; // mL
  const freshMediaVolume = Math.max(0, flaskVolume - requiredCultureVolume);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content cell-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">IN VITRO BIOLOGY & CELL BANKING</span>
            <h2>Cell Culture & In Vitro Passage Lineage Tracker</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Tab Controls */}
        <div className="subnav-tabs">
          <button
            className={`tab-btn ${activeTab === "active" ? "active" : ""}`}
            onClick={() => setActiveTab("active")}
          >
            🧫 Active Cultures ({cellLines.length})
          </button>
          <button
            className={`tab-btn ${activeTab === "calculator" ? "active" : ""}`}
            onClick={() => setActiveTab("calculator")}
          >
            🧮 Split & Doubling Time Calculator
          </button>
          <button
            className={`tab-btn ${activeTab === "cryo" ? "active" : ""}`}
            onClick={() => setActiveTab("cryo")}
          >
            🧊 Liquid Nitrogen Biobank Vials
          </button>
        </div>

        {notice && <div className="callout callout-success">{notice}</div>}

        {activeTab === "active" && (
          <div className="cell-culture-grid-layout">
            {/* Left Cell Line List */}
            <div className="cell-lines-list-col">
              {cellLines.map((line) => {
                const isOverPassage = line.currentPassage >= line.maxRecommendedPassage;
                return (
                  <div
                    key={line.id}
                    className={`cell-line-card ${selectedCellLine.id === line.id ? "selected" : ""}`}
                    onClick={() => setSelectedCellLine(line)}
                  >
                    <div className="card-top-row">
                      <span className="organism-tag">{line.organism}</span>
                      <span className="bsl-tag">BSL-{line.biosafetyLevel}</span>
                      <span className={`passage-pill ${isOverPassage ? "passage-alert" : ""}`}>
                        P{line.currentPassage}
                      </span>
                    </div>
                    <h4>{line.name}</h4>
                    <p className="card-media font-mono">{line.growthMedium.slice(0, 48)}...</p>
                    <div className="card-stats-row">
                      <span>Viability: <strong className="text-emerald">{line.viabilityPercent}%</strong></span>
                      <span>Doubling: <strong>{line.doublingTimeHours}h</strong></span>
                      <span>Vials: <strong>{line.storageVialsCount}</strong></span>
                    </div>
                    {isOverPassage && (
                      <div className="high-passage-warning">
                        ⚠️ High Passage Alert: Exceeds P{line.maxRecommendedPassage} recommended threshold. Risk of genetic drift.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Right Active Culture Hub */}
            <div className="cell-culture-hub-col">
              <div className="hub-header">
                <div>
                  <span className="badge-purple">CULTURE VESSEL DETAILS</span>
                  <h2>{selectedCellLine.name}</h2>
                  <p className="text-muted">{selectedCellLine.tissueSource}</p>
                </div>
                <div className="hub-passage-badge">
                  <span className="p-num">P{selectedCellLine.currentPassage}</span>
                  <small>Max Safe: P{selectedCellLine.maxRecommendedPassage}</small>
                </div>
              </div>

              {selectedCellLine.currentPassage >= selectedCellLine.maxRecommendedPassage && (
                <div className="callout callout-warning">
                  <strong>⚠️ Phenotypic Drift Warning:</strong> This culture has reached Passage {selectedCellLine.currentPassage}. Cellular morphology, karyotype stability, and recombinant protein expression kinetics should be verified via karyotyping or a fresh cryovial should be thawed.
                </div>
              )}

              {/* Vital Growth Metrics */}
              <div className="growth-metrics-row">
                <div className="metric-card">
                  <span className="metric-title">Viability (Trypan Blue)</span>
                  <span className="metric-value text-emerald">{selectedCellLine.viabilityPercent}%</span>
                  <small className="metric-hint">Automated cell counter verified</small>
                </div>
                <div className="metric-card">
                  <span className="metric-title">Doubling Time (T_d)</span>
                  <span className="metric-value text-cyan">{selectedCellLine.doublingTimeHours} hrs</span>
                  <small className="metric-hint">Calculated across last 3 splits</small>
                </div>
                <div className="metric-card">
                  <span className="metric-title">Mycoplasma PCR QA</span>
                  <span className="metric-value text-emerald">NEGATIVE</span>
                  <small className="metric-hint">Certificate on file (21 CFR Part 11)</small>
                </div>
                <div className="metric-card">
                  <span className="metric-title">LN2 Backup Stock</span>
                  <span className="metric-value text-purple">{selectedCellLine.storageVialsCount} Vials</span>
                  <small className="metric-hint">Vapor phase LN2 (-196°C)</small>
                </div>
              </div>

              {/* Maintenance Specs */}
              <div className="culture-specs-card">
                <h4>Formulation & Seeding Protocols</h4>
                <div className="specs-row">
                  <span>Growth Medium Recipe:</span>
                  <strong className="font-mono text-cyan">{selectedCellLine.growthMedium}</strong>
                </div>
                <div className="specs-row">
                  <span>Optimal Seeding Density:</span>
                  <strong>{selectedCellLine.seedingDensity}</strong>
                </div>
                <div className="specs-row">
                  <span>Standard Split Ratio:</span>
                  <strong>{selectedCellLine.splitRatio}</strong>
                </div>
                <div className="specs-row">
                  <span>Last Passaged Timestamp:</span>
                  <strong className="font-mono">{selectedCellLine.lastPassagedDate}</strong>
                </div>
              </div>

              {/* Passaging Action Controls */}
              <div className="passage-action-bar">
                <button
                  type="button"
                  className="button button-primary button-lg"
                  onClick={handlePassageCulture}
                >
                  🧪 Passage Culture (Advance to P{selectedCellLine.currentPassage + 1})
                </button>
                <button
                  type="button"
                  className="button button-outline button-lg"
                  onClick={() => alert(`Thaw protocol initiated for ${selectedCellLine.name}. Reserve biosafety hood.`)}
                >
                  Thaw Fresh Backup Vial
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Split Dilution & Seeding Calculator */}
        {activeTab === "calculator" && (
          <div className="cell-calculator-layout">
            <div className="calc-inputs-card">
              <h3>Passaging Dilution & Seeding Mass Balance Calculator</h3>
              <p className="subtext">
                Automatically calculates the exact harvest suspension volume and fresh medium volume needed for target density.
              </p>

              <div className="calc-form">
                <label className="field-label">
                  Harvested Viable Cell Count (×10⁶ cells/mL):
                  <input
                    type="number"
                    step="0.1"
                    value={currentViableCount}
                    onChange={(e) => setCurrentViableCount(+e.target.value)}
                    className="input-text"
                  />
                </label>

                <label className="field-label">
                  Target Seeding Density (×10⁶ cells/mL):
                  <input
                    type="number"
                    step="0.05"
                    value={targetDensity}
                    onChange={(e) => setTargetDensity(+e.target.value)}
                    className="input-text"
                  />
                </label>

                <label className="field-label">
                  Target Vessel Total Volume (mL, e.g. T75 = 20mL, T175 = 50mL):
                  <input
                    type="number"
                    value={flaskVolume}
                    onChange={(e) => setFlaskVolume(+e.target.value)}
                    className="input-text"
                  />
                </label>
              </div>
            </div>

            <div className="calc-results-card">
              <h3>Calculated Passaging Volumes</h3>
              <div className="result-display-box">
                <div className="result-item">
                  <span className="res-label">Inoculum Cell Suspension</span>
                  <span className="res-number text-cyan">{requiredCultureVolume.toFixed(2)} mL</span>
                </div>
                <div className="plus-sign">+</div>
                <div className="result-item">
                  <span className="res-label">Fresh Pre-Warmed Medium</span>
                  <span className="res-number text-emerald">{freshMediaVolume.toFixed(2)} mL</span>
                </div>
                <div className="equals-sign">=</div>
                <div className="result-item">
                  <span className="res-label">Total Culture Volume</span>
                  <span className="res-number text-purple">{flaskVolume.toFixed(1)} mL</span>
                </div>
              </div>

              <div className="calc-summary-notes">
                <p>
                  ✓ Total cells seeded: <strong>{(targetDensity * flaskVolume).toFixed(2)} × 10⁶ cells</strong>  
                  <br />
                  ✓ Predicted 80% confluence date: <strong>in ~48 hours ({selectedCellLine.doublingTimeHours}h doubling time)</strong>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Cryovial Biobank */}
        {activeTab === "cryo" && (
          <div className="cryo-vials-view">
            <h3>Liquid Nitrogen Storage Lineage ({selectedCellLine.name})</h3>
            <p className="subtext">
              Master & Working Cell Bank inventory stored at -196°C in vapor-phase LN2.
            </p>
            <div className="cryo-vials-grid">
              {Array.from({ length: selectedCellLine.storageVialsCount }).map((_, i) => (
                <div key={i} className="cryo-vial-item">
                  <span className="vial-icon">❄️</span>
                  <strong>Vial #{i + 1}</strong>
                  <span className="font-mono text-cyan">P{Math.max(2, selectedCellLine.currentPassage - (i % 5))}</span>
                  <small className="text-muted">LN2 Tank 1 (Rack 2, Box C{i + 1})</small>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

