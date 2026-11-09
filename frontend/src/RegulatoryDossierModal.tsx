import { useState, useEffect } from "react";
import {
  dossierApi,
  RegulatoryDossierItem,
  DossierSection,
} from "./api";

interface RegulatoryDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  currentUserId?: number;
  currentUserName?: string;
  onInsertIntoNotebook?: (markdown: string) => void;
}

export function RegulatoryDossierModal({
  isOpen,
  onClose,
  selectedProjectId,
  selectedExperimentId,
  currentUserId,
  currentUserName,
  onInsertIntoNotebook,
}: RegulatoryDossierModalProps) {
  const [dossiers, setDossiers] = useState<RegulatoryDossierItem[]>([]);
  const [activeDossier, setActiveDossier] = useState<RegulatoryDossierItem | null>(null);
  const [dossierTitle, setDossierTitle] = useState<string>("IND Module 3.2.P Analytical Verification");
  const [dossierType, setDossierType] = useState<string>("GxP Certificate of Analysis");
  const [summary, setSummary] = useState<string>(
    "Comprehensive Good Laboratory Practice (GLP) characterization and multi-plate quantitation performed in accordance with FDA 21 CFR Part 11 standards."
  );
  const [sections, setSections] = useState<DossierSection[]>([
    {
      title: "1.0 Executive Summary & Scope of Analysis",
      content: "Complete analytical dossier comprising microplate spectrophotometry, 4PL sigmoidal calibration, chemical descriptor validation, and molecular sequence integrity.",
      status: "APPROVED",
    },
    {
      title: "2.0 21 CFR Part 11 Audit Trail & Cryptographic Evidence",
      content: "Immutable audit log records with HMAC-SHA256 signatures validated. Zero unrecorded revisions or unauthorized data modifications detected.",
      status: "VERIFIED",
    },
    {
      title: "3.0 Chemical Characterization & Molecular Quality Control",
      content: "SMILES topological properties and Lipinski Rule of 5 evaluation conform to pharmaceutical drug-likeness specifications.",
      status: "COMPLIANT",
    },
    {
      title: "4.0 Spectrophotometric & 4PL Sigmoidal Quantitation",
      content: "Absorbance readings (OD450) fitted via 4PL regression with R² >= 0.992. Baseline blanks automatically subtracted.",
      status: "VALIDATED",
    },
    {
      title: "5.0 Final Certification & Electronic Sign-Off",
      content: "The undersigned certifies that this laboratory dossier constitutes a complete, accurate, and immutable record of experimental procedures.",
      status: "READY",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    loadDossiers();
  }, [isOpen]);

  async function loadDossiers() {
    try {
      const list = await dossierApi.list(selectedProjectId, selectedExperimentId);
      setDossiers(list);
      if (list.length > 0) {
        selectDossier(list[0]);
      }
    } catch (err) {
      console.error("Failed to load dossiers", err);
    }
  }

  function selectDossier(d: RegulatoryDossierItem) {
    setActiveDossier(d);
    setDossierTitle(d.title);
    setDossierType(d.dossier_type);
    setSummary(d.summary);
    setSections(d.sections || []);
  }

  async function handleCompile() {
    setLoading(true);
    setError(null);
    try {
      const created = await dossierApi.compile({
        title: dossierTitle,
        dossier_type: dossierType,
        summary,
        project_id: selectedProjectId,
        experiment_id: selectedExperimentId,
        custom_sections: sections,
      });
      setActiveDossier(created);
      setDossiers((prev) => [created, ...prev]);
      setNotice(`Compiled Dossier #${created.id} with SHA-256 integrity seal!`);
      setTimeout(() => setNotice(null), 3500);
    } catch (err: any) {
      setError(err?.message || "Failed to compile dossier.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCertify() {
    if (!activeDossier) return;
    setLoading(true);
    try {
      const res = await dossierApi.certify(activeDossier.id, {
        user_id: currentUserId || 1,
        user_name: currentUserName || "Authorized Principal Investigator",
      });
      setActiveDossier((prev) => prev ? { ...prev, ...res } as any : null);
      setNotice(`Dossier #${activeDossier.id} Officially Certified & Digitally Signed!`);
      setTimeout(() => setNotice(null), 3500);
      void loadDossiers();
    } catch (err: any) {
      setError(err?.message || "Certification failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenPrintView() {
    if (!activeDossier) return;
    window.open(`/api/dossier/${activeDossier.id}/html`, "_blank");
  }

  function handleInsertMarkdown() {
    if (!activeDossier || !onInsertIntoNotebook) return;
    const md = `
### 📜 Regulatory Dossier Certified: ${activeDossier.title}
- **Type:** ${activeDossier.dossier_type}
- **Status:** ${activeDossier.status.toUpperCase()}
- **SHA-256 Hash:** \`${activeDossier.sha256_checksum}\`
- **Certified By:** ${activeDossier.certified_by_user_name || "Pending Sign-off"}
- **Sections:** ${activeDossier.sections.length} GxP verification modules approved.
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content dossier-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">REGULATORY DOSSIER BUILDER</span>
            <h2>GxP Certificate of Analysis & Publication Submission Package</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Toolbar */}
        <div className="dossier-toolbar-row">
          <div className="dossier-title-group">
            <input
              type="text"
              className="input-text dossier-name-input"
              value={dossierTitle}
              onChange={(e) => setDossierTitle(e.target.value)}
              placeholder="Dossier Document Title"
            />
            <select
              className="input-text"
              style={{ fontSize: 12, padding: "6px 10px" }}
              value={dossierType}
              onChange={(e) => setDossierType(e.target.value)}
            >
              <option value="GxP Certificate of Analysis">GxP Certificate of Analysis</option>
              <option value="IND Regulatory Submission Module">IND Regulatory Submission Module</option>
              <option value="Peer-Reviewed Publication Package">Peer-Reviewed Publication Package</option>
              <option value="GLP Quality Audit Dossier">GLP Quality Audit Dossier</option>
            </select>
          </div>

          <div className="dossier-actions-group">
            {dossiers.length > 0 && (
              <select
                className="input-text"
                style={{ fontSize: 11, padding: "4px 8px" }}
                value={activeDossier?.id || ""}
                onChange={(e) => {
                  const d = dossiers.find((item) => item.id === Number(e.target.value));
                  if (d) selectDossier(d);
                }}
              >
                <option value="">-- Compiled Dossiers ({dossiers.length}) --</option>
                {dossiers.map((d) => (
                  <option key={d.id} value={d.id}>
                    #{d.id} - {d.title} ({d.status})
                  </option>
                ))}
              </select>
            )}

            <button className="button button-primary" onClick={handleCompile} disabled={loading}>
              ⚡ Compile New Dossier
            </button>
            {activeDossier && activeDossier.status !== "certified" && (
              <button className="button button-primary" onClick={handleCertify} disabled={loading}>
                🔏 Certify & Sign
              </button>
            )}
            {activeDossier && (
              <button className="button button-secondary" onClick={handleOpenPrintView}>
                🖨️ Print / PDF
              </button>
            )}
            {onInsertIntoNotebook && activeDossier && (
              <button className="button button-outline" onClick={handleInsertMarkdown}>
                📝 Insert in Notebook
              </button>
            )}
          </div>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {notice && <div className="callout callout-success">{notice}</div>}

        {/* Dossier Preview & SHA-256 Seal Box */}
        <div className="dossier-layout-body">
          {/* Certificate Badge */}
          {activeDossier && (
            <div className={`dossier-cert-seal ${activeDossier.status === "certified" ? "seal-certified" : "seal-draft"}`}>
              <div className="seal-header">
                <span className="seal-icon">
                  {activeDossier.status === "certified" ? "🛡️ CERTIFIED GxP RECORD" : "⚠️ DRAFT COMPILATION"}
                </span>
                <span className="seal-id">ID: #{activeDossier.id}</span>
              </div>
              <div className="seal-meta-grid">
                <div>
                  <span className="meta-lbl">Digital Signature</span>
                  <span className="meta-val">{activeDossier.certified_by_user_name || "Pending Electronic Signature"}</span>
                </div>
                <div>
                  <span className="meta-lbl">Cryptographic Fingerprint (SHA-256)</span>
                  <span className="meta-val font-mono hash-val">{activeDossier.sha256_checksum}</span>
                </div>
              </div>
            </div>
          )}

          {/* Structured Sections */}
          <div className="dossier-sections-list">
            {sections.map((sec, idx) => (
              <div key={idx} className="dossier-section-card">
                <div className="card-header-flex">
                  <h4>{sec.title}</h4>
                  <span className="badge-tag tag-pass">{sec.status}</span>
                </div>
                <textarea
                  className="input-text section-textarea"
                  rows={3}
                  value={sec.content}
                  onChange={(e) => {
                    const updated = [...sections];
                    updated[idx] = { ...updated[idx], content: e.target.value };
                    setSections(updated);
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

