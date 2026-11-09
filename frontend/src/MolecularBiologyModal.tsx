import { useState, useEffect } from "react";
import {
  molecularApi,
  MolecularSequenceItem,
  SequenceAnalysis,
  DigestResult,
  OpenReadingFrame,
  PrimerCheckResult,
} from "./api";
import { CircularPlasmidMap } from "./CircularPlasmidMap";

interface MolecularBiologyModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  onInsertIntoNotebook?: (markdown: string) => void;
}

export function MolecularBiologyModal({
  isOpen,
  onClose,
  selectedProjectId,
  selectedExperimentId,
  onInsertIntoNotebook,
}: MolecularBiologyModalProps) {
  const [activeTab, setActiveTab] = useState<"analyzer" | "plasmid" | "digest" | "orfs" | "primers" | "repository">("analyzer");
  const [sequenceName, setSequenceName] = useState<string>("GFP Expression Cassette");
  const [rawSequence, setRawSequence] = useState<string>(
    "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGCCACAACGTCTATATCATGGCCGACAAGCAGAAGAACGGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCATCGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA"
  );
  const [topology, setTopology] = useState<"linear" | "circular">("linear");
  const [analysis, setAnalysis] = useState<SequenceAnalysis | null>(null);
  const [presets, setPresets] = useState<{ name: string; sequence: string; topology: string; description: string }[]>([]);
  const [enzymesList, setEnzymesList] = useState<{ name: string; motif: string; cut_offset: number; overhang: string }[]>([]);
  const [selectedEnzymes, setSelectedEnzymes] = useState<string[]>(["EcoRI", "BamHI", "HindIII"]);
  const [digestResult, setDigestResult] = useState<DigestResult | null>(null);
  const [orfs, setOrfs] = useState<OpenReadingFrame[]>([]);
  const [fwdPrimer, setFwdPrimer] = useState<string>("ATGGTGAGCAAGGGCGAGGAG");
  const [revPrimer, setRevPrimer] = useState<string>("TTACTTGTACAGCTCGTCCATGCC");
  const [primerResult, setPrimerResult] = useState<PrimerCheckResult | null>(null);
  const [savedSequences, setSavedSequences] = useState<MolecularSequenceItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    loadPresetsAndEnzymes();
    loadRepository();
    void runAnalysis(rawSequence, sequenceName);
  }, [isOpen]);

  async function loadPresetsAndEnzymes() {
    try {
      const [pData, eData] = await Promise.all([
        molecularApi.getPresets(),
        molecularApi.getEnzymes(),
      ]);
      setPresets(pData);
      setEnzymesList(eData);
    } catch (err) {
      console.error("Failed to load molecular presets/enzymes", err);
    }
  }

  async function loadRepository() {
    try {
      const list = await molecularApi.list(selectedProjectId, selectedExperimentId);
      setSavedSequences(list);
    } catch (err) {
      console.error("Failed to load saved sequences", err);
    }
  }

  async function runAnalysis(seq: string, name?: string) {
    if (!seq.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await molecularApi.analyze(seq, name || sequenceName, "dna");
      setAnalysis(res);
    } catch (err: any) {
      setError(err?.message || "Sequence analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runDigest() {
    if (!rawSequence.trim()) return;
    setLoading(true);
    try {
      const res = await molecularApi.digest(rawSequence, selectedEnzymes, topology);
      setDigestResult(res);
    } catch (err: any) {
      setError(err?.message || "Restriction digest failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runOrfFinder() {
    if (!rawSequence.trim()) return;
    setLoading(true);
    try {
      const res = await molecularApi.findOrfs(rawSequence, 30);
      setOrfs(res);
    } catch (err: any) {
      setError(err?.message || "ORF search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runPrimerCheck() {
    if (!fwdPrimer.trim() || !revPrimer.trim()) return;
    setLoading(true);
    try {
      const res = await molecularApi.testPrimers(fwdPrimer.trim(), revPrimer.trim());
      setPrimerResult(res);
    } catch (err: any) {
      setError(err?.message || "Primer evaluation failed.");
    } finally {
      setLoading(false);
    }
  }

  function toggleEnzyme(name: string) {
    setSelectedEnzymes((prev) =>
      prev.includes(name) ? prev.filter((e) => e !== name) : [...prev, name]
    );
  }

  async function handleSaveSequence() {
    if (!analysis) return;
    try {
      await molecularApi.save({
        name: sequenceName || analysis.name,
        sequence: analysis.sequence,
        sequence_type: "dna",
        topology,
        project_id: selectedProjectId,
        experiment_id: selectedExperimentId,
      });
      setNotice(`Saved "${sequenceName || analysis.name}" to Molecular Repository!`);
      setTimeout(() => setNotice(null), 3000);
      void loadRepository();
    } catch (err: any) {
      setError(err?.message || "Failed to save sequence.");
    }
  }

  function handleInsertMarkdown() {
    if (!analysis || !onInsertIntoNotebook) return;
    const md = `
### 🧬 Molecular Biology Sequence Analysis: ${sequenceName || analysis.name}
- **Length:** ${analysis.length} bp (${topology})
- **GC Content:** ${analysis.gc_content}%
- **Melting Temp (Tm):** ${analysis.melting_temp} °C
- **Molecular Weight:** ${analysis.molecular_weight} Da
- **Base Counts:** A: ${analysis.base_counts.A || 0}, T: ${analysis.base_counts.T || 0}, C: ${analysis.base_counts.C || 0}, G: ${analysis.base_counts.G || 0}
- **5' to 3' Sequence Preview:** \`${analysis.sequence.slice(0, 60)}...\`
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content molecular-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">MOLECULAR BIOLOGY STUDIO</span>
            <h2>DNA/RNA Sequence Analysis, In Silico Digestion & Primer Suite</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Subnav Navigation */}
        <div className="subnav-tabs">
          <button
            className={`tab-btn ${activeTab === "analyzer" ? "active" : ""}`}
            onClick={() => setActiveTab("analyzer")}
          >
            📊 Sequence Metrics
          </button>
          <button
            className={`tab-btn ${activeTab === "plasmid" ? "active" : ""}`}
            onClick={() => setActiveTab("plasmid")}
          >
            ⭕ Circular Plasmid Map (360° Vector View)
          </button>
          <button
            className={`tab-btn ${activeTab === "digest" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("digest");
              void runDigest();
            }}
          >
            ✂️ In Silico Restriction & Gel Electrophoresis
          </button>
          <button
            className={`tab-btn ${activeTab === "orfs" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("orfs");
              void runOrfFinder();
            }}
          >
            🧬 6-Frame ORFs & Translation
          </button>
          <button
            className={`tab-btn ${activeTab === "primers" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("primers");
              void runPrimerCheck();
            }}
          >
            🎯 PCR Primer Quality
          </button>
          <button
            className={`tab-btn ${activeTab === "repository" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("repository");
              void loadRepository();
            }}
          >
            📁 Saved Sequences ({savedSequences.length})
          </button>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {notice && <div className="callout callout-success">{notice}</div>}

        {/* Tab: Circular Plasmid Map */}
        {activeTab === "plasmid" && (
          <CircularPlasmidMap
            plasmidName={sequenceName || analysis?.name || "Cloning Plasmid Vector"}
            totalBp={analysis?.length || 2686}
            gcPercent={analysis?.gc_content || 50.7}
            topology={topology}
          />
        )}

        {/* Tab 1: Sequence Analyzer */}
        {activeTab === "analyzer" && (
          <div className="molecular-grid-layout">
            <div className="mol-input-col">
              <div className="input-field-group">
                <label className="field-label">Sequence Identifier</label>
                <input
                  type="text"
                  className="input-text"
                  value={sequenceName}
                  onChange={(e) => setSequenceName(e.target.value)}
                  placeholder="e.g. pUC19, CMV Promoter, Cas9 Target"
                />
              </div>

              <div className="input-field-group">
                <div className="label-with-topology">
                  <label className="field-label">FASTA / Raw Nucleotide Sequence</label>
                  <div className="topology-toggle">
                    <button
                      type="button"
                      className={`toggle-pill ${topology === "linear" ? "active" : ""}`}
                      onClick={() => setTopology("linear")}
                    >
                      Linear
                    </button>
                    <button
                      type="button"
                      className={`toggle-pill ${topology === "circular" ? "active" : ""}`}
                      onClick={() => setTopology("circular")}
                    >
                      Circular Plasmid
                    </button>
                  </div>
                </div>
                <textarea
                  className="input-text font-mono sequence-textarea"
                  rows={8}
                  value={rawSequence}
                  onChange={(e) => setRawSequence(e.target.value)}
                  placeholder="Paste raw sequence or FASTA header (>id ...)"
                />
                <button
                  type="button"
                  className="button button-primary button-sm"
                  onClick={() => runAnalysis(rawSequence, sequenceName)}
                  disabled={loading}
                >
                  {loading ? "Analyzing..." : "Recompute Sequence Metrics"}
                </button>
              </div>

              {/* Presets */}
              <div className="presets-block">
                <label className="field-label">Standard Cloning Presets:</label>
                <div className="preset-pill-list">
                  {presets.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      className="preset-pill"
                      onClick={() => {
                        setSequenceName(p.name);
                        setRawSequence(p.sequence);
                        setTopology(p.topology as any);
                        void runAnalysis(p.sequence, p.name);
                      }}
                    >
                      {p.name.split(" ")[0]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="chemical-actions-row">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handleSaveSequence}
                  disabled={!analysis}
                >
                  💾 Save to Molecular Repository
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

            {/* Right Metrics Panel */}
            <div className="mol-metrics-col">
              {analysis && (
                <>
                  <div className="prop-card">
                    <h4>Nucleotide Composition & Properties</h4>
                    <div className="prop-grid">
                      <div className="prop-stat">
                        <span className="stat-label">Length</span>
                        <span className="stat-value highlight-cyan">{analysis.length.toLocaleString()} <small>bp</small></span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">GC Content</span>
                        <span className="stat-value">{analysis.gc_content}%</span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Melting Temp (Tm)</span>
                        <span className="stat-value">{analysis.melting_temp} <small>°C</small></span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Molecular Weight</span>
                        <span className="stat-value">{(analysis.molecular_weight / 1000).toFixed(1)} <small>kDa</small></span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Topology</span>
                        <span className="stat-value capitalize">{topology}</span>
                      </div>
                      <div className="prop-stat">
                        <span className="stat-label">Purine / Pyrimidine</span>
                        <span className="stat-value">
                          {((((analysis.base_counts.A || 0) + (analysis.base_counts.G || 0)) / (analysis.length || 1)) * 100).toFixed(1)}% /{" "}
                          {((((analysis.base_counts.T || 0) + (analysis.base_counts.C || 0)) / (analysis.length || 1)) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    {/* Base bar */}
                    <div className="base-distribution-bar">
                      <div
                        className="bar-segment seg-a"
                        style={{ width: `${((analysis.base_counts.A || 0) / analysis.length) * 100}%` }}
                        title={`Adenine (A): ${analysis.base_counts.A}`}
                      >
                        A ({analysis.base_counts.A})
                      </div>
                      <div
                        className="bar-segment seg-t"
                        style={{ width: `${((analysis.base_counts.T || 0) / analysis.length) * 100}%` }}
                        title={`Thymine (T): ${analysis.base_counts.T}`}
                      >
                        T ({analysis.base_counts.T})
                      </div>
                      <div
                        className="bar-segment seg-c"
                        style={{ width: `${((analysis.base_counts.C || 0) / analysis.length) * 100}%` }}
                        title={`Cytosine (C): ${analysis.base_counts.C}`}
                      >
                        C ({analysis.base_counts.C})
                      </div>
                      <div
                        className="bar-segment seg-g"
                        style={{ width: `${((analysis.base_counts.G || 0) / analysis.length) * 100}%` }}
                        title={`Guanine (G): ${analysis.base_counts.G}`}
                      >
                        G ({analysis.base_counts.G})
                      </div>
                    </div>
                  </div>

                  {/* Reverse Complement Preview */}
                  <div className="prop-card">
                    <div className="card-header-flex">
                      <h4>Reverse Complement (3' ← 5')</h4>
                      <button
                        className="button-link"
                        onClick={() => {
                          navigator.clipboard.writeText(analysis.reverse_complement);
                          setNotice("Copied reverse complement to clipboard!");
                          setTimeout(() => setNotice(null), 2500);
                        }}
                      >
                        Copy Sequence
                      </button>
                    </div>
                    <div className="rev-comp-box font-mono">
                      {analysis.reverse_complement.slice(0, 240)}
                      {analysis.reverse_complement.length > 240 && "..."}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Restriction Digestion & Agarose Gel Simulator */}
        {activeTab === "digest" && (
          <div className="digest-layout">
            <div className="digest-controls">
              <h4>Select Restriction Endonucleases</h4>
              <div className="enzyme-chips-list">
                {enzymesList.map((e) => {
                  const isChecked = selectedEnzymes.includes(e.name);
                  return (
                    <button
                      key={e.name}
                      type="button"
                      className={`enzyme-chip ${isChecked ? "selected" : ""}`}
                      onClick={() => toggleEnzyme(e.name)}
                    >
                      <span className="enzyme-name">{e.name}</span>
                      <span className="enzyme-motif font-mono">{e.motif}</span>
                    </button>
                  );
                })}
              </div>
              <button className="button button-primary" onClick={runDigest} style={{ marginTop: 12 }}>
                Run In Silico Digestion
              </button>
            </div>

            <div className="gel-and-fragments-view">
              {/* Virtual Agarose Gel Simulator */}
              <div className="virtual-gel-container">
                <div className="gel-header">
                  <span>Simulated 1.0% Agarose Gel (EtBr / UV)</span>
                  <span className="badge-tag">{topology} DNA</span>
                </div>
                <div className="gel-cassette">
                  {/* Ladder lane */}
                  <div className="gel-lane ladder-lane">
                    <div className="lane-label">1kb Ladder</div>
                    <div className="band" style={{ top: "15%" }} title="10,000 bp"><span className="band-txt">10k</span></div>
                    <div className="band" style={{ top: "25%" }} title="6,000 bp"><span className="band-txt">6k</span></div>
                    <div className="band" style={{ top: "35%" }} title="4,000 bp"><span className="band-txt">4k</span></div>
                    <div className="band" style={{ top: "48%" }} title="2,000 bp"><span className="band-txt">2k</span></div>
                    <div className="band" style={{ top: "62%" }} title="1,000 bp"><span className="band-txt">1k</span></div>
                    <div className="band" style={{ top: "78%" }} title="500 bp"><span className="band-txt">500</span></div>
                  </div>

                  {/* Sample digestion lane */}
                  <div className="gel-lane sample-lane">
                    <div className="lane-label">Digested</div>
                    {digestResult?.fragments.map((frag, idx) => (
                      <div
                        key={idx}
                        className="band sample-band"
                        style={{ top: `${frag.migration_percent}%` }}
                        title={`${frag.label}: ${frag.length} bp`}
                      >
                        <span className="band-txt">{frag.length} bp</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Fragment Table */}
              <div className="fragments-table-card">
                <h4>Predicted Cleavage Fragments ({digestResult?.fragments.length || 0})</h4>
                <div className="scroll-table-container">
                  <table className="lipinski-table">
                    <thead>
                      <tr>
                        <th>Fragment</th>
                        <th>Length</th>
                        <th>Coordinates</th>
                      </tr>
                    </thead>
                    <tbody>
                      {digestResult?.fragments.map((f, i) => (
                        <tr key={i}>
                          <td>{f.label}</td>
                          <td className="highlight-cyan font-mono">{f.length} bp</td>
                          <td className="font-mono text-muted">{f.start} .. {f.end}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="cut-sites-summary" style={{ marginTop: 12 }}>
                  <h4>Identified Cut Sites ({digestResult?.cut_sites.length || 0})</h4>
                  <div className="cut-sites-pills">
                    {digestResult?.cut_sites.map((c, i) => (
                      <span key={i} className="cut-site-badge">
                        {c.enzyme} @ pos {c.position} ({c.overhang} {c.type})
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: ORFs */}
        {activeTab === "orfs" && (
          <div className="orfs-view">
            <div className="orfs-toolbar">
              <button className="button button-primary" onClick={runOrfFinder}>
                Scan 6-Reading Frames
              </button>
              <span className="text-muted">Detected {orfs.length} open reading frame(s) ≥ 30 aa</span>
            </div>

            <div className="orfs-grid">
              {orfs.map((orf, idx) => (
                <div key={idx} className="orf-card">
                  <div className="card-header-flex">
                    <span className="badge-tag highlight-cyan">Frame {orf.frame}</span>
                    <span className="text-muted">{orf.length_aa} aa ({orf.length_bp} bp)</span>
                  </div>
                  <div className="orf-coords font-mono text-muted">
                    Start: {orf.start} → End: {orf.end} ({orf.strand} strand)
                  </div>
                  <div className="orf-protein font-mono">
                    {orf.protein_sequence}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 4: PCR Primers */}
        {activeTab === "primers" && (
          <div className="primers-layout">
            <div className="primer-inputs-card">
              <h4>PCR Primer Pair Quality Assessor</h4>
              <div className="input-field-group">
                <label className="field-label">Forward Primer (5' → 3')</label>
                <input
                  type="text"
                  className="input-text font-mono"
                  value={fwdPrimer}
                  onChange={(e) => setFwdPrimer(e.target.value)}
                />
              </div>

              <div className="input-field-group">
                <label className="field-label">Reverse Primer (5' → 3')</label>
                <input
                  type="text"
                  className="input-text font-mono"
                  value={revPrimer}
                  onChange={(e) => setRevPrimer(e.target.value)}
                />
              </div>

              <button className="button button-primary" onClick={runPrimerCheck}>
                Evaluate Primer Chemistry & ΔTm
              </button>
            </div>

            {primerResult && (
              <div className="primer-results-card">
                <div className="card-header-flex">
                  <h4>Pair Compatibility Score</h4>
                  <span className={`badge-tag ${primerResult.quality_score >= 80 ? "tag-pass" : "tag-warning"}`}>
                    {primerResult.quality_score}/100 Confidence
                  </span>
                </div>

                <div className="primer-stats-grid">
                  <div className="prop-stat">
                    <span className="stat-label">Forward Tm</span>
                    <span className="stat-value">{primerResult.forward.melting_temp}°C ({primerResult.forward.length} nt)</span>
                  </div>
                  <div className="prop-stat">
                    <span className="stat-label">Reverse Tm</span>
                    <span className="stat-value">{primerResult.reverse.melting_temp}°C ({primerResult.reverse.length} nt)</span>
                  </div>
                  <div className="prop-stat">
                    <span className="stat-label">ΔTm Difference</span>
                    <span className={`stat-value ${primerResult.tm_difference <= 5 ? "status-pass" : "status-fail"}`}>
                      {primerResult.tm_difference}°C
                    </span>
                  </div>
                  <div className="prop-stat">
                    <span className="stat-label">Recommended Annealing (Ta)</span>
                    <span className="stat-value highlight-cyan">{primerResult.recommended_annealing_temp}°C</span>
                  </div>
                </div>

                {primerResult.warnings.length > 0 && (
                  <div className="primer-warnings-list">
                    {primerResult.warnings.map((w, i) => (
                      <div key={i} className="primer-warn-item">⚠️ {w}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 5: Repository */}
        {activeTab === "repository" && (
          <div className="chemical-library-view">
            <div className="compound-cards-grid">
              {savedSequences.map((s) => (
                <div key={s.id} className="compound-item-card">
                  <div className="item-info">
                    <h4>{s.name}</h4>
                    <p className="item-formula font-mono">{s.length} bp • {s.gc_content}% GC • {s.topology}</p>
                    <div className="item-meta-row">
                      <span className="badge-tag">Tm: {s.melting_temp}°C</span>
                      <span className="badge-tag">{(s.molecular_weight / 1000).toFixed(1)} kDa</span>
                    </div>
                    <div className="item-actions-row">
                      <button
                        className="button-link"
                        onClick={async () => {
                          const full = await molecularApi.get(s.id);
                          setSequenceName(full.name);
                          setRawSequence(full.sequence_data || "");
                          setTopology((full.topology as any) || "linear");
                          setActiveTab("analyzer");
                          void runAnalysis(full.sequence_data || "", full.name);
                        }}
                      >
                        Load into Studio
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

