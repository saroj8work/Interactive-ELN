import React, { useState, useMemo } from 'react';

interface Peak {
  index: number;
  base: 'A' | 'C' | 'G' | 'T';
  pos: number;
  qScore: number;
  referenceBase?: string;
}

const SAMPLE_SEQUENCE = 'ATGCGATCGGATCGATAGCTAGCTAGCTGATCGATCGATCGATCGAATCGATCGATCGATCGTAGCTAGCTAGCTACCCGATCGATCGA';
const REFERENCE_SEQUENCE = 'ATGCGATCGGATCGATAGCTAGCTAGCTGATCGATCGATCGATCGTATCGATCGATCGATCGTAGCTAGCTAGCTACCCGATCGATCGA'; // base 42 mutation A -> T

export const ChromatogramViewerModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({
  isOpen,
  onClose,
}) => {
  const [zoomLevel, setZoomLevel] = useState<number>(1.2);
  const [peakHeight, setPeakHeight] = useState<number>(85);
  const [showChannelA, setShowChannelA] = useState(true);
  const [showChannelC, setShowChannelC] = useState(true);
  const [showChannelG, setShowChannelG] = useState(true);
  const [showChannelT, setShowChannelT] = useState(true);
  const [reverseComplement, setReverseComplement] = useState(false);
  const [selectedBaseIndex, setSelectedBaseIndex] = useState<number | null>(42);

  // Generate trace data points
  const { peaks, maxPos } = useMemo(() => {
    const list: Peak[] = [];
    const spacing = 32;
    for (let i = 0; i < SAMPLE_SEQUENCE.length; i++) {
      const b = SAMPLE_SEQUENCE[i] as 'A' | 'C' | 'G' | 'T';
      const refB = REFERENCE_SEQUENCE[i];
      // realistic Phred Q scores (20 to 55, slight dip at ends)
      const distFromEnd = Math.min(i, SAMPLE_SEQUENCE.length - 1 - i);
      const baseQ = distFromEnd < 8 ? 24 + distFromEnd * 2 : 42 + Math.sin(i * 0.7) * 8;
      list.push({
        index: i + 1,
        base: b,
        pos: 20 + i * spacing,
        qScore: Math.round(baseQ),
        referenceBase: refB,
      });
    }
    return { peaks: list, maxPos: 40 + SAMPLE_SEQUENCE.length * spacing };
  }, []);

  if (!isOpen) return null;

  // Generate continuous SVG paths for 4 dye channels
  const generateDyePath = (channel: 'A' | 'C' | 'G' | 'T') => {
    let d = `M 0,${peakHeight}`;
    const step = 4;
    for (let x = 0; x <= maxPos; x += step) {
      // Find nearest peak
      let yIntensity = 0;
      peaks.forEach((p) => {
        const dx = x - p.pos;
        if (Math.abs(dx) < 28) {
          const bell = Math.exp(-(dx * dx) / 100);
          if (p.base === channel) {
            yIntensity += bell * (peakHeight * 0.92);
          } else {
            // slight background baseline noise
            yIntensity += bell * (peakHeight * 0.08);
          }
        }
      });
      const yVal = peakHeight - Math.min(yIntensity, peakHeight - 5);
      d += ` L ${x},${yVal.toFixed(1)}`;
    }
    return d;
  };

  const channelColors = {
    A: '#10b981', // Green
    C: '#0ea5e9', // Blue
    G: '#f1f5f9', // Black/Light Silver
    T: '#f43f5e', // Red
  };

  const averageQV = (peaks.reduce((acc, p) => acc + p.qScore, 0) / peaks.length).toFixed(1);
  const selectedPeak = selectedBaseIndex !== null ? peaks[selectedBaseIndex] : null;

  return (
    <div className="modal-backdrop futuristic-backdrop" onClick={onClose}>
      <div
        className="modal-container futuristic-chromatogram-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1240px', width: '96vw', maxHeight: '92vh' }}
      >
        {/* Header */}
        <div className="futuristic-modal-header">
          <div className="flex items-center gap-3">
            <div className="futuristic-icon-badge violet-pulse">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M2 12h2l3-7 4 14 3-7h8" />
                <circle cx="12" cy="12" r="2" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="futuristic-modal-title">Sanger Sequencing Chromatogram (.ab1 / SCF) Studio</h2>
                <span className="gxp-pill gxp-certified">ABI 3730xl 4-Dye Capillary</span>
              </div>
              <p className="futuristic-modal-sub">
                Fluorescence electropherogram trace deconvolution, Phred QV caller, mutation alignment & IUPAC base calling.
              </p>
            </div>
          </div>
          <button className="futuristic-close-btn" onClick={onClose} aria-label="Close Chromatogram Viewer">
            ✕
          </button>
        </div>

        {/* Trace Metric Ribbon */}
        <div className="chroma-metrics-ribbon">
          <div className="chroma-metric-pill">
            <span className="lbl">TRACE SPECIMEN</span>
            <span className="val text-cyan">pLenti-EF1a-Cas9-Blast_Fwd.ab1</span>
          </div>
          <div className="chroma-metric-pill">
            <span className="lbl">READ LENGTH</span>
            <span className="val text-emerald">{peaks.length} bp</span>
          </div>
          <div className="chroma-metric-pill">
            <span className="lbl">MEAN PHRED SCORE</span>
            <span className="val text-indigo-400">Q{averageQV} (High Quality &gt; Q30)</span>
          </div>
          <div className="chroma-metric-pill">
            <span className="lbl">CONTIGUOUS READ LENGTH</span>
            <span className="val text-slate-200">89 bp (0 N-ambiguities)</span>
          </div>
          <div className="chroma-metric-pill">
            <span className="lbl">MUTATIONS / VARIANTS</span>
            <span className="val text-amber">1 Mismatch Detected</span>
          </div>
        </div>

        {/* Toolbar & Controls */}
        <div className="chroma-toolbar">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-300">Dye Channels:</span>
            <label className="chroma-channel-toggle text-emerald">
              <input
                type="checkbox"
                checked={showChannelA}
                onChange={(e) => setShowChannelA(e.target.checked)}
              />
              <span className="dot bg-emerald" /> Adenine (A - FAM)
            </label>
            <label className="chroma-channel-toggle text-cyan">
              <input
                type="checkbox"
                checked={showChannelC}
                onChange={(e) => setShowChannelC(e.target.checked)}
              />
              <span className="dot bg-cyan" /> Cytosine (C - JOE)
            </label>
            <label className="chroma-channel-toggle text-slate-200">
              <input
                type="checkbox"
                checked={showChannelG}
                onChange={(e) => setShowChannelG(e.target.checked)}
              />
              <span className="dot bg-slate-200" /> Guanine (G - NED)
            </label>
            <label className="chroma-channel-toggle text-rose">
              <input
                type="checkbox"
                checked={showChannelT}
                onChange={(e) => setShowChannelT(e.target.checked)}
              />
              <span className="dot bg-rose" /> Thymine (T - ROX)
            </label>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <span>Zoom:</span>
              <input
                type="range"
                min="0.8"
                max="2.5"
                step="0.1"
                value={zoomLevel}
                onChange={(e) => setZoomLevel(parseFloat(e.target.value))}
                className="chroma-slider"
              />
              <span>{Math.round(zoomLevel * 100)}%</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <span>Peak Gain:</span>
              <input
                type="range"
                min="40"
                max="140"
                value={peakHeight}
                onChange={(e) => setPeakHeight(parseInt(e.target.value))}
                className="chroma-slider"
              />
            </div>
            <button
              className={`chroma-btn-compact ${reverseComplement ? 'active' : ''}`}
              onClick={() => setReverseComplement(!reverseComplement)}
            >
              🔄 Rev-Comp
            </button>
            <button
              className="chroma-btn-compact text-cyan"
              onClick={() => {
                navigator.clipboard?.writeText(SAMPLE_SEQUENCE);
                alert('FASTA sequence copied to clipboard!');
              }}
            >
              📋 Copy FASTA
            </button>
          </div>
        </div>

        {/* Interactive Electropherogram Trace Canvas */}
        <div className="chroma-viewport-container">
          <div
            className="chroma-viewport-scroll"
            style={{ overflowX: 'auto', transform: `scaleX(${zoomLevel})`, transformOrigin: '0 0' }}
          >
            <div style={{ width: `${maxPos}px`, height: '280px', position: 'relative' }}>
              {/* Reference Alignment Comparison Track */}
              <div className="chroma-ref-track">
                <span className="chroma-track-label">Ref Construct:</span>
                {peaks.map((p, idx) => {
                  const isMatch = p.base === p.referenceBase;
                  return (
                    <div
                      key={`ref-${idx}`}
                      className={`chroma-ref-cell ${isMatch ? 'match' : 'mismatch'}`}
                      style={{ left: `${p.pos - 8}px` }}
                      title={`Ref Base: ${p.referenceBase} | Read: ${p.base}`}
                    >
                      {p.referenceBase}
                    </div>
                  );
                })}
              </div>

              {/* Base Call Letters Track */}
              <div className="chroma-base-track">
                <span className="chroma-track-label">Call (QV):</span>
                {peaks.map((p, idx) => {
                  const isSelected = selectedBaseIndex === idx;
                  const isMismatch = p.base !== p.referenceBase;
                  return (
                    <div
                      key={`call-${idx}`}
                      className={`chroma-call-cell base-${p.base} ${isSelected ? 'selected' : ''} ${
                        isMismatch ? 'mismatch-alert' : ''
                      }`}
                      style={{ left: `${p.pos - 9}px` }}
                      onClick={() => setSelectedBaseIndex(idx)}
                    >
                      <span className="base-char">{p.base}</span>
                      <span className="base-idx">{p.index}</span>
                    </div>
                  );
                })}
              </div>

              {/* SVG 4-Dye Fluorescence Waveforms */}
              <svg width={maxPos} height={peakHeight + 10} className="chroma-svg-waveforms">
                <defs>
                  <linearGradient id="grid-grad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="rgba(255,255,255,0.02)" />
                    <stop offset="100%" stopColor="rgba(255,255,255,0.06)" />
                  </linearGradient>
                </defs>
                <rect width={maxPos} height={peakHeight + 10} fill="url(#grid-grad)" />

                {/* Base vertical locator markers */}
                {peaks.map((p, idx) => (
                  <line
                    key={idx}
                    x1={p.pos}
                    y1={0}
                    x2={p.pos}
                    y2={peakHeight + 10}
                    stroke="rgba(255,255,255,0.05)"
                    strokeDasharray="2 3"
                  />
                ))}

                {/* Dye traces */}
                {showChannelG && (
                  <path d={generateDyePath('G')} fill="none" stroke={channelColors.G} strokeWidth="1.8" />
                )}
                {showChannelC && (
                  <path d={generateDyePath('C')} fill="none" stroke={channelColors.C} strokeWidth="1.8" />
                )}
                {showChannelA && (
                  <path d={generateDyePath('A')} fill="none" stroke={channelColors.A} strokeWidth="1.8" />
                )}
                {showChannelT && (
                  <path d={generateDyePath('T')} fill="none" stroke={channelColors.T} strokeWidth="1.8" />
                )}

                {/* Selected Base Pointer */}
                {selectedPeak && (
                  <g>
                    <line
                      x1={selectedPeak.pos}
                      y1={0}
                      x2={selectedPeak.pos}
                      y2={peakHeight + 10}
                      stroke="#38bdf8"
                      strokeWidth="2"
                    />
                    <circle cx={selectedPeak.pos} cy={peakHeight * 0.25} r="4" fill="#38bdf8" />
                  </g>
                )}
              </svg>

              {/* Phred Quality Score Bar Graph Track */}
              <div className="chroma-phred-track">
                <span className="chroma-track-label">Phred Score:</span>
                {peaks.map((p, idx) => {
                  const barH = Math.min(38, Math.round((p.qScore / 60) * 38));
                  const isHighQ = p.qScore >= 30;
                  return (
                    <div
                      key={`q-${idx}`}
                      className="chroma-phred-bar-wrapper"
                      style={{ left: `${p.pos - 5}px` }}
                      title={`Base #${p.index} (${p.base}): Phred Q${p.qScore}`}
                      onClick={() => setSelectedBaseIndex(idx)}
                    >
                      <div
                        className={`chroma-phred-bar ${isHighQ ? 'q-pass' : 'q-warn'}`}
                        style={{ height: `${barH}px` }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Inspection & Mutation Analysis Drawer */}
        <div className="chroma-inspector-grid">
          <div className="chroma-inspector-card">
            <span className="inspector-title">SELECTED BASE INSPECTION</span>
            {selectedPeak ? (
              <div className="inspector-content">
                <div className="flex items-center gap-4 mb-2">
                  <div className={`selected-base-large base-${selectedPeak.base}`}>
                    {selectedPeak.base}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-white">
                      Base Position #{selectedPeak.index}
                    </div>
                    <div className="text-xs text-slate-400">
                      Chromatogram coordinate: {selectedPeak.pos} px
                    </div>
                    <div className="text-xs text-cyan mt-1">
                      Phred Score: <strong>Q{selectedPeak.qScore}</strong> (Error prob:{' '}
                      {(10 ** (-selectedPeak.qScore / 10) * 100).toFixed(4)}%)
                    </div>
                  </div>
                </div>
                <div className="text-xs text-slate-300">
                  Reference Match:{' '}
                  {selectedPeak.base === selectedPeak.referenceBase ? (
                    <span className="text-emerald font-semibold">100% Homology ({selectedPeak.referenceBase})</span>
                  ) : (
                    <span className="text-rose font-semibold">
                      Point Mutation: Ref={selectedPeak.referenceBase} → Read={selectedPeak.base} (SNV)
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 py-3">Click on any base peak above to inspect metrology.</div>
            )}
          </div>

          <div className="chroma-inspector-card">
            <span className="inspector-title">SANGER TRACE RUN QA VALIDATION</span>
            <div className="chroma-qa-checklist">
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-800">
                <span className="text-slate-400">Capillary Voltage:</span>
                <span className="text-slate-200">13.2 kV (Stable ±0.1%)</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-800">
                <span className="text-slate-400">Polymer Matrix:</span>
                <span className="text-slate-200">POP-7™ Performance Optimized</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-800">
                <span className="text-slate-400">Signal-to-Noise Ratio:</span>
                <span className="text-emerald">64.2 dB (Optimal &gt; 50 dB)</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1">
                <span className="text-slate-400">Plasmid LOR (Loss of Resolution):</span>
                <span className="text-slate-200">Base 942</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
