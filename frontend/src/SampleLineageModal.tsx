import { FC, useState } from "react";

export interface LineageNode {
  id: number;
  name: string;
  barcode: string;
  sampleType: "primary_tissue" | "homogenate" | "extract" | "aliquot" | "assay_fraction";
  parentId: number | null;
  volumeUl: number;
  initialVolumeUl: number;
  freezeThawCycles: number;
  status: "available" | "depleted" | "consumed" | "quarantined";
  storageLocation: string;
  createdDate: string;
}

interface SampleLineageModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedSampleId?: number | null;
}

export const SampleLineageModal: FC<SampleLineageModalProps> = ({
  isOpen,
  onClose,
}) => {
  // Rich hierarchical sample genealogy
  const [samples, setSamples] = useState<LineageNode[]>([
    {
      id: 101,
      name: "Tumor Resection Biopsy T-402",
      barcode: "SMP-TUM-0101",
      sampleType: "primary_tissue",
      parentId: null,
      volumeUl: 1000,
      initialVolumeUl: 1000,
      freezeThawCycles: 1,
      status: "available",
      storageLocation: "Cryo Freezer #2 (Shelf 1, Box A1)",
      createdDate: "2026-10-12",
    },
    {
      id: 102,
      name: "Tissue Homogenate Fraction H-1",
      barcode: "SMP-HOM-0102",
      sampleType: "homogenate",
      parentId: 101,
      volumeUl: 650,
      initialVolumeUl: 800,
      freezeThawCycles: 2,
      status: "available",
      storageLocation: "Cryo Freezer #2 (Shelf 1, Box A2)",
      createdDate: "2026-10-14",
    },
    {
      id: 103,
      name: "Total Genomic DNA Extract",
      barcode: "SMP-DNA-0103",
      sampleType: "extract",
      parentId: 102,
      volumeUl: 120,
      initialVolumeUl: 200,
      freezeThawCycles: 2,
      status: "available",
      storageLocation: "-80°C Ultra-Low #1 (Shelf 3, Box C4)",
      createdDate: "2026-10-15",
    },
    {
      id: 104,
      name: "Total RNA Extract (High Purity)",
      barcode: "SMP-RNA-0104",
      sampleType: "extract",
      parentId: 102,
      volumeUl: 40,
      initialVolumeUl: 150,
      freezeThawCycles: 4,
      status: "available",
      storageLocation: "Liquid Nitrogen Dewar (Canister 2, Rack B)",
      createdDate: "2026-10-15",
    },
    {
      id: 105,
      name: "DNA Working Aliquot #1 (50 ng/µL)",
      barcode: "SMP-ALQ-0105",
      sampleType: "aliquot",
      parentId: 103,
      volumeUl: 25,
      initialVolumeUl: 50,
      freezeThawCycles: 1,
      status: "available",
      storageLocation: "-20°C Working Freezer (Rack 4, Box W1)",
      createdDate: "2026-10-18",
    },
    {
      id: 106,
      name: "DNA Working Aliquot #2 (50 ng/µL)",
      barcode: "SMP-ALQ-0106",
      sampleType: "aliquot",
      parentId: 103,
      volumeUl: 0,
      initialVolumeUl: 50,
      freezeThawCycles: 3,
      status: "depleted",
      storageLocation: "Archived / Consumed in NGS Library Prep",
      createdDate: "2026-10-18",
    },
    {
      id: 107,
      name: "RNA cDNA Reverse Transcription Pool",
      barcode: "SMP-CDNA-0107",
      sampleType: "assay_fraction",
      parentId: 104,
      volumeUl: 35,
      initialVolumeUl: 40,
      freezeThawCycles: 2,
      status: "available",
      storageLocation: "-20°C Working Freezer (Rack 2, Box RT)",
      createdDate: "2026-10-22",
    },
  ]);

  const [selectedNode, setSelectedNode] = useState<LineageNode>(samples[2]);
  const [aliquotCount, setAliquotCount] = useState<number>(3);
  const [aliquotVol, setAliquotVol] = useState<number>(20);
  const [notice, setNotice] = useState<string | null>(null);

  if (!isOpen) return null;

  // Derive daughter samples from parent
  const handleSplitAliquot = () => {
    if (!selectedNode || selectedNode.volumeUl < aliquotVol * aliquotCount) {
      alert("Insufficient parent sample volume to create requested aliquots.");
      return;
    }

    const totalNeeded = aliquotVol * aliquotCount;
    const newAliquots: LineageNode[] = [];
    const baseId = Date.now();

    for (let i = 1; i <= aliquotCount; i++) {
      newAliquots.push({
        id: baseId + i,
        name: `${selectedNode.name} - Aliquot #${i}`,
        barcode: `SMP-ALQ-${Math.floor(1000 + Math.random() * 9000)}`,
        sampleType: "aliquot",
        parentId: selectedNode.id,
        volumeUl: aliquotVol,
        initialVolumeUl: aliquotVol,
        freezeThawCycles: 1,
        status: "available",
        storageLocation: "-80°C Biobank (Auto-Assigned Slot)",
        createdDate: new Date().toISOString().slice(0, 10),
      });
    }

    // Deduct volume from parent
    setSamples((prev) =>
      prev
        .map((s) => (s.id === selectedNode.id ? { ...s, volumeUl: s.volumeUl - totalNeeded } : s))
        .concat(newAliquots)
    );

    setSelectedNode((prev) => ({ ...prev, volumeUl: prev.volumeUl - totalNeeded }));
    setNotice(`Successfully spawned ${aliquotCount} daughter aliquots with barcode tracking.`);
    setTimeout(() => setNotice(null), 3500);
  };

  const handleIncrementFreezeThaw = (nodeId: number) => {
    setSamples((prev) =>
      prev.map((s) => (s.id === nodeId ? { ...s, freezeThawCycles: s.freezeThawCycles + 1 } : s))
    );
    if (selectedNode.id === nodeId) {
      setSelectedNode((prev) => ({ ...prev, freezeThawCycles: prev.freezeThawCycles + 1 }));
    }
  };

  const getTypeBadge = (type: LineageNode["sampleType"]) => {
    switch (type) {
      case "primary_tissue":
        return { label: "PRIMARY SPECIMEN", bg: "#f59e0b", color: "#000" };
      case "homogenate":
        return { label: "FRACTION", bg: "#06b6d4", color: "#000" };
      case "extract":
        return { label: "ISOLATE / EXTRACT", bg: "#8b5cf6", color: "#fff" };
      case "aliquot":
        return { label: "WORKING ALIQUOT", bg: "#10b981", color: "#000" };
      case "assay_fraction":
        return { label: "ASSAY POOL", bg: "#ec4899", color: "#fff" };
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content lineage-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">LIMS SAMPLE GENEALOGY & CHAIN-OF-CUSTODY</span>
            <h2>Sample Aliquot Lineage & Freeze-Thaw Integrity DAG</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {notice && <div className="callout callout-success">{notice}</div>}

        <div className="lineage-layout-grid">
          {/* Visual Interactive DAG Tree */}
          <div className="lineage-tree-canvas-panel">
            <div className="panel-subhead">
              <span>Interactive Parent-to-Daughter Genealogy Graph</span>
              <small className="text-muted">Click any node to inspect volume balances & degradation risk</small>
            </div>

            <div className="dag-tree-flow">
              {/* Level 0: Primary Specimen */}
              <div className="lineage-level">
                <span className="level-indicator">TIER 1 • PRIMARY</span>
                {samples
                  .filter((s) => s.parentId === null)
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`lineage-node-card ${selectedNode.id === node.id ? "selected" : ""}`}
                      onClick={() => setSelectedNode(node)}
                    >
                      <div className="node-type-pill" style={{ background: getTypeBadge(node.sampleType).bg, color: getTypeBadge(node.sampleType).color }}>
                        {getTypeBadge(node.sampleType).label}
                      </div>
                      <h4>{node.name}</h4>
                      <div className="node-stats font-mono">
                        <span>{node.barcode}</span> • <span>{node.volumeUl} µL</span>
                      </div>
                    </div>
                  ))}
              </div>

              <div className="tree-arrow-connector">➔</div>

              {/* Level 1: Homogenate / Intermediate */}
              <div className="lineage-level">
                <span className="level-indicator">TIER 2 • FRACTIONATION</span>
                {samples
                  .filter((s) => s.parentId === 101)
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`lineage-node-card ${selectedNode.id === node.id ? "selected" : ""}`}
                      onClick={() => setSelectedNode(node)}
                    >
                      <div className="node-type-pill" style={{ background: getTypeBadge(node.sampleType).bg, color: getTypeBadge(node.sampleType).color }}>
                        {getTypeBadge(node.sampleType).label}
                      </div>
                      <h4>{node.name}</h4>
                      <div className="node-stats font-mono">
                        <span>{node.barcode}</span> • <span>{node.volumeUl} µL</span>
                      </div>
                    </div>
                  ))}
              </div>

              <div className="tree-arrow-connector">➔</div>

              {/* Level 2: Isolates */}
              <div className="lineage-level">
                <span className="level-indicator">TIER 3 • PURIFIED ISOLATE</span>
                {samples
                  .filter((s) => s.parentId === 102)
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`lineage-node-card ${selectedNode.id === node.id ? "selected" : ""}`}
                      onClick={() => setSelectedNode(node)}
                    >
                      <div className="node-type-pill" style={{ background: getTypeBadge(node.sampleType).bg, color: getTypeBadge(node.sampleType).color }}>
                        {getTypeBadge(node.sampleType).label}
                      </div>
                      <h4>{node.name}</h4>
                      <div className="node-stats font-mono">
                        <span>{node.barcode}</span> • <span>{node.volumeUl} µL</span>
                      </div>
                      {node.freezeThawCycles >= 4 && (
                        <span className="warning-chip">⚠️ {node.freezeThawCycles}× Freeze-Thaw</span>
                      )}
                    </div>
                  ))}
              </div>

              <div className="tree-arrow-connector">➔</div>

              {/* Level 3: Working Aliquots */}
              <div className="lineage-level">
                <span className="level-indicator">TIER 4 • WORKING ALIQUOTS</span>
                {samples
                  .filter((s) => s.parentId === 103 || s.parentId === 104)
                  .map((node) => (
                    <div
                      key={node.id}
                      className={`lineage-node-card ${selectedNode.id === node.id ? "selected" : ""} ${node.status === "depleted" ? "depleted-card" : ""}`}
                      onClick={() => setSelectedNode(node)}
                    >
                      <div className="node-type-pill" style={{ background: getTypeBadge(node.sampleType).bg, color: getTypeBadge(node.sampleType).color }}>
                        {getTypeBadge(node.sampleType).label}
                      </div>
                      <h4>{node.name}</h4>
                      <div className="node-stats font-mono">
                        <span>{node.barcode}</span> • <span>{node.volumeUl} / {node.initialVolumeUl} µL</span>
                      </div>
                      {node.status === "depleted" && <span className="depleted-tag">DEPLETED</span>}
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Right Inspector & Aliquot Spawner */}
          <div className="lineage-inspector-panel">
            <div className="inspector-card-header">
              <span className="badge-purple">INSPECTOR & ACTION HUB</span>
              <h3>{selectedNode.name}</h3>
              <p className="font-mono text-cyan">{selectedNode.barcode}</p>
            </div>

            {/* Metrics */}
            <div className="inspector-metrics-grid">
              <div className="metric-box">
                <span className="metric-label">Remaining Volume</span>
                <span className="metric-val text-cyan font-mono">{selectedNode.volumeUl} µL</span>
                <small className="metric-sub">of {selectedNode.initialVolumeUl} µL initial</small>
              </div>

              <div className="metric-box">
                <span className="metric-label">Freeze-Thaw Count</span>
                <span className={`metric-val font-mono ${selectedNode.freezeThawCycles >= 4 ? "text-danger" : "text-emerald"}`}>
                  {selectedNode.freezeThawCycles}×
                </span>
                <small className="metric-sub">
                  {selectedNode.freezeThawCycles >= 4 ? "High degradation risk" : "Optimal molecular integrity"}
                </small>
              </div>
            </div>

            <div className="inspector-field-list">
              <div className="field-row">
                <span>Storage Location:</span>
                <strong>{selectedNode.storageLocation}</strong>
              </div>
              <div className="field-row">
                <span>Sample Category:</span>
                <strong>{selectedNode.sampleType.toUpperCase().replace("_", " ")}</strong>
              </div>
              <div className="field-row">
                <span>Created Date:</span>
                <strong className="font-mono">{selectedNode.createdDate}</strong>
              </div>
              <div className="field-row">
                <span>Status:</span>
                <strong className={selectedNode.status === "available" ? "text-emerald" : "text-amber"}>
                  {selectedNode.status.toUpperCase()}
                </strong>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="inspector-actions">
              <button
                type="button"
                className="button button-outline button-sm full-width"
                onClick={() => handleIncrementFreezeThaw(selectedNode.id)}
              >
                ❄️ Log Freeze-Thaw Cycle (+1)
              </button>
            </div>

            {/* Aliquoting Spawner Tool */}
            <div className="aliquot-spawner-box">
              <h4>Spawn Daughter Aliquots</h4>
              <p className="subtext">Derive child vials with automatically linked parent custody.</p>

              <div className="spawner-inputs">
                <label>
                  Number of Vials:
                  <input
                    type="number"
                    min="1"
                    max="24"
                    value={aliquotCount}
                    onChange={(e) => setAliquotCount(+e.target.value)}
                    className="input-text input-sm"
                  />
                </label>
                <label>
                  Volume per Aliquot (µL):
                  <input
                    type="number"
                    min="1"
                    max={selectedNode.volumeUl}
                    value={aliquotVol}
                    onChange={(e) => setAliquotVol(+e.target.value)}
                    className="input-text input-sm"
                  />
                </label>
              </div>

              <div className="spawner-summary">
                Total Volume to Deduct: <strong>{aliquotCount * aliquotVol} µL</strong> (Balance after:{" "}
                <span className="font-mono text-cyan">{selectedNode.volumeUl - aliquotCount * aliquotVol} µL</span>)
              </div>

              <button
                type="button"
                className="button button-primary button-sm full-width"
                onClick={handleSplitAliquot}
                disabled={selectedNode.volumeUl < aliquotCount * aliquotVol}
              >
                ⚡ Create {aliquotCount} Child Aliquots
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

