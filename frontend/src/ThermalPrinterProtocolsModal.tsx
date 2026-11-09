import { useState, useEffect } from "react";
import {
  thermalPrinterApi,
  ThermalLabelPreview,
  ProtocolsIoProtocol,
} from "./api";

interface ThermalPrinterProtocolsModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  onInsertIntoNotebook?: (markdown: string) => void;
}

export function ThermalPrinterProtocolsModal({
  isOpen,
  onClose,
  onInsertIntoNotebook,
}: ThermalPrinterProtocolsModalProps) {
  const [activeTab, setActiveTab] = useState<"zpl" | "protocols">("zpl");

  // Thermal printer state
  const [labelType, setLabelType] = useState<string>("cryovial");
  const [sampleName, setSampleName] = useState<string>("HEK293-GFP-Cl.4");
  const [barcodeData, setBarcodeData] = useState<string>("CRYO-2026-0894");
  const [lotNumber, setLotNumber] = useState<string>("LOT-B4-09");
  const [storageTemp, setStorageTemp] = useState<string>("-80°C Cryo");
  const [expiryDate, setExpiryDate] = useState<string>("2028-05-30");
  const [hazardSymbol, setHazardSymbol] = useState<string>("BIOHAZARD");
  const [dpi, setDpi] = useState<number>(203);
  const [labelPreview, setLabelPreview] = useState<ThermalLabelPreview | null>(null);

  // Protocols.io state
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [protocols, setProtocols] = useState<ProtocolsIoProtocol[]>([]);
  const [selectedProtocol, setSelectedProtocol] = useState<ProtocolsIoProtocol | null>(null);

  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    void generateZplPreview();
    void loadProtocols();
  }, [isOpen]);

  async function generateZplPreview() {
    setLoading(true);
    try {
      const res = await thermalPrinterApi.generateZpl({
        label_type: labelType,
        barcode_data: barcodeData,
        sample_name: sampleName,
        lot_number: lotNumber,
        storage_temp: storageTemp,
        expiry_date: expiryDate,
        hazard_symbol: hazardSymbol,
        dpi,
      });
      setLabelPreview(res);
      setError(null);
    } catch (err: any) {
      setError(err?.message || "Failed to generate ZPL label.");
    } finally {
      setLoading(false);
    }
  }

  async function loadProtocols(query?: string) {
    try {
      const list = await thermalPrinterApi.searchProtocols(query);
      setProtocols(list);
      if (list.length > 0 && !selectedProtocol) {
        setSelectedProtocol(list[0]);
      }
    } catch (err) {
      console.error("Failed to search protocols.io", err);
    }
  }

  function handleSelectPreset(presetType: string) {
    setLabelType(presetType);
    if (presetType === "cryovial") {
      setSampleName("HEK293-GFP-Cl.4");
      setBarcodeData("CRYO-2026-0894");
      setStorageTemp("-80°C Cryo");
    } else if (presetType === "microplate") {
      setSampleName("ELISA-PLT-04-SERUM");
      setBarcodeData("PLT-96-04412");
      setStorageTemp("4°C Cold Room");
    } else {
      setSampleName("10x PBST Wash Buffer");
      setBarcodeData("REG-PBST-01");
      setStorageTemp("Room Temp");
      setHazardSymbol("GHS07 Irritant");
    }
  }

  function handleDownloadZpl() {
    if (!labelPreview) return;
    const blob = new Blob([labelPreview.zpl_code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `label-${barcodeData}.zpl`;
    a.click();
    URL.revokeObjectURL(url);
    setNotice(`Downloaded Zebra ZPL file: label-${barcodeData}.zpl`);
    setTimeout(() => setNotice(null), 3000);
  }

  function handleCopyZpl() {
    if (!labelPreview) return;
    navigator.clipboard.writeText(labelPreview.zpl_code);
    setNotice("Copied raw Zebra ZPL II code to clipboard!");
    setTimeout(() => setNotice(null), 2500);
  }

  async function handleImportProtocol(proto: ProtocolsIoProtocol) {
    try {
      await thermalPrinterApi.importProtocol(proto.protocol_id_ext);
      setNotice(`Imported "${proto.title}" into workspace!`);
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Import failed.");
    }
  }

  function handleInsertProtocolMarkdown(proto: ProtocolsIoProtocol) {
    if (!onInsertIntoNotebook) return;
    const stepsList = proto.steps
      .map((s) => `${s.step_num}. **${s.title}** (${s.duration_min} min @ ${s.temp_c}°C): ${s.notes}`)
      .join("\n");
    const md = `
### 🧪 Imported Protocol: ${proto.title}
*Source: Protocols.io (${proto.doi}) • Authors: ${proto.authors}*

${proto.description}

#### Execution Procedure:
${stepsList}
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content thermal-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">HARDWARE & OPEN SCIENCE SUITE</span>
            <h2>Zebra ZPL II Thermal Label Studio & Protocols.io Importer</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Subnav Navigation */}
        <div className="subnav-tabs">
          <button
            className={`tab-btn ${activeTab === "zpl" ? "active" : ""}`}
            onClick={() => setActiveTab("zpl")}
          >
            🏷️ Zebra ZPL II Barcode Label Studio
          </button>
          <button
            className={`tab-btn ${activeTab === "protocols" ? "active" : ""}`}
            onClick={() => setActiveTab("protocols")}
          >
            🌐 Protocols.io Open-Science Importer
          </button>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {notice && <div className="callout callout-success">{notice}</div>}

        {/* Tab 1: Zebra ZPL II Thermal Label Studio */}
        {activeTab === "zpl" && (
          <div className="thermal-body-grid">
            {/* Form Controls */}
            <div className="label-controls-card">
              <h4>Label Specifications & Target Container</h4>

              <div className="preset-pill-list" style={{ marginBottom: 12 }}>
                <button
                  type="button"
                  className={`preset-pill ${labelType === "cryovial" ? "active" : ""}`}
                  onClick={() => {
                    handleSelectPreset("cryovial");
                    setTimeout(() => void generateZplPreview(), 50);
                  }}
                >
                  ❄️ Cryovial (DataMatrix)
                </button>
                <button
                  type="button"
                  className={`preset-pill ${labelType === "microplate" ? "active" : ""}`}
                  onClick={() => {
                    handleSelectPreset("microplate");
                    setTimeout(() => void generateZplPreview(), 50);
                  }}
                >
                  🔬 Plate Skirt (Code 128)
                </button>
                <button
                  type="button"
                  className={`preset-pill ${labelType === "reagent_bottle" ? "active" : ""}`}
                  onClick={() => {
                    handleSelectPreset("reagent_bottle");
                    setTimeout(() => void generateZplPreview(), 50);
                  }}
                >
                  🧪 Reagent Bottle (QR + GHS)
                </button>
              </div>

              <div className="input-field-group">
                <label className="field-label">Sample / Reagent Name</label>
                <input
                  type="text"
                  className="input-text"
                  value={sampleName}
                  onChange={(e) => setSampleName(e.target.value)}
                />
              </div>

              <div className="input-field-group">
                <label className="field-label">Barcode / Tracking ID</label>
                <input
                  type="text"
                  className="input-text font-mono"
                  value={barcodeData}
                  onChange={(e) => setBarcodeData(e.target.value)}
                />
              </div>

              <div className="label-fields-row">
                <div className="input-field-group">
                  <label className="field-label">Batch / Lot #</label>
                  <input
                    type="text"
                    className="input-text"
                    value={lotNumber}
                    onChange={(e) => setLotNumber(e.target.value)}
                  />
                </div>
                <div className="input-field-group">
                  <label className="field-label">Storage Temp</label>
                  <input
                    type="text"
                    className="input-text"
                    value={storageTemp}
                    onChange={(e) => setStorageTemp(e.target.value)}
                  />
                </div>
              </div>

              <div className="label-fields-row">
                <div className="input-field-group">
                  <label className="field-label">Expiration Date</label>
                  <input
                    type="text"
                    className="input-text"
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                  />
                </div>
                <div className="input-field-group">
                  <label className="field-label">Resolution (DPI)</label>
                  <select
                    className="input-text"
                    value={dpi}
                    onChange={(e) => setDpi(Number(e.target.value))}
                  >
                    <option value={203}>203 DPI (Standard)</option>
                    <option value={300}>300 DPI (High-Density Microplate)</option>
                  </select>
                </div>
              </div>

              <button
                className="button button-primary"
                onClick={generateZplPreview}
                style={{ marginTop: 8 }}
                disabled={loading}
              >
                🔄 Refresh ZPL Code & Preview
              </button>
            </div>

            {/* Visual Preview & ZPL Code Output */}
            <div className="label-preview-card">
              <div className="plot-header">
                <h4>Simulated Thermal Label Print Preview</h4>
                <span className="badge-tag">{dpi} DPI Direct Thermal</span>
              </div>

              <div
                className="label-svg-box"
                dangerouslySetInnerHTML={{ __html: labelPreview?.svg_preview || "" }}
              />

              <div className="zpl-output-section">
                <div className="card-header-flex">
                  <h4>Zebra ZPL II Machine Commands</h4>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="button button-outline button-xs" onClick={handleCopyZpl}>
                      Copy ZPL
                    </button>
                    <button className="button button-primary button-xs" onClick={handleDownloadZpl}>
                      Download .zpl
                    </button>
                  </div>
                </div>
                <textarea
                  className="input-text font-mono zpl-textarea"
                  rows={6}
                  readOnly
                  value={labelPreview?.zpl_code || ""}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Protocols.io Open-Science Importer */}
        {activeTab === "protocols" && (
          <div className="protocols-io-layout">
            <div className="protocols-sidebar">
              <input
                type="text"
                className="input-text search-input"
                placeholder="Search Protocols.io by keyword (RNA, PCR, ELISA)..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  void loadProtocols(e.target.value);
                }}
              />

              <div className="protocols-list">
                {protocols.map((p) => (
                  <div
                    key={p.protocol_id_ext}
                    className={`protocol-item-card ${selectedProtocol?.protocol_id_ext === p.protocol_id_ext ? "selected" : ""}`}
                    onClick={() => setSelectedProtocol(p)}
                  >
                    <h4>{p.title}</h4>
                    <p className="protocol-meta">{p.authors} • {p.steps.length} steps</p>
                    <p className="protocol-doi">{p.doi}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="protocol-details-view">
              {selectedProtocol ? (
                <>
                  <div className="protocol-header-card">
                    <div className="card-header-flex">
                      <h3>{selectedProtocol.title}</h3>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          className="button button-secondary button-sm"
                          onClick={() => handleImportProtocol(selectedProtocol)}
                        >
                          💾 Save to Protocols
                        </button>
                        {onInsertIntoNotebook && (
                          <button
                            className="button button-primary button-sm"
                            onClick={() => handleInsertProtocolMarkdown(selectedProtocol)}
                          >
                            📝 Insert in Notebook
                          </button>
                        )}
                      </div>
                    </div>
                    <p className="protocol-authors text-muted">Authored by {selectedProtocol.authors}</p>
                    <p className="protocol-desc">{selectedProtocol.description}</p>
                  </div>

                  <h4>Procedure Execution Steps</h4>
                  <div className="protocol-steps-timeline">
                    {selectedProtocol.steps.map((s) => (
                      <div key={s.step_num} className="timeline-step-card">
                        <div className="step-num-badge">Step {s.step_num}</div>
                        <div className="step-body">
                          <div className="step-title-row">
                            <strong>{s.title}</strong>
                            <span className="badge-tag">{s.duration_min} min @ {s.temp_c}°C</span>
                          </div>
                          <p className="step-notes">{s.notes}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="empty-protocol-hint">
                  <p>Select a protocol from Protocols.io repository to inspect steps.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

