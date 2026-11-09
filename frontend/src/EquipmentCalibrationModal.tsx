import React, { useState } from 'react';

interface EquipmentItem {
  id: string;
  name: string;
  category: string;
  assetTag: string;
  serialNumber: string;
  location: string;
  status: 'calibrated' | 'warning' | 'locked_out' | 'in_service';
  lastCalibrated: string;
  nextDue: string;
  driftPercentage: number;
  qualifications: { iq: boolean; oq: boolean; pq: boolean };
  readings: { standard: number; measured: number; tolerance: number }[];
  slope: number;
  intercept: number;
  rSquared: number;
}

const INITIAL_EQUIPMENT: EquipmentItem[] = [
  {
    id: 'eq-001',
    name: 'Agilent 1260 Infinity II HPLC System',
    category: 'Chromatography',
    assetTag: 'AST-HPLC-092',
    serialNumber: 'DEBA491820',
    location: 'Analytical Suite B, Bench 4',
    status: 'calibrated',
    lastCalibrated: '2026-10-15',
    nextDue: '2027-04-15',
    driftPercentage: 0.42,
    qualifications: { iq: true, oq: true, pq: true },
    readings: [
      { standard: 10.0, measured: 10.02, tolerance: 0.1 },
      { standard: 25.0, measured: 24.97, tolerance: 0.25 },
      { standard: 50.0, measured: 50.11, tolerance: 0.5 },
      { standard: 100.0, measured: 99.88, tolerance: 1.0 },
      { standard: 200.0, measured: 200.41, tolerance: 2.0 },
    ],
    slope: 1.0018,
    intercept: -0.042,
    rSquared: 0.99994,
  },
  {
    id: 'eq-002',
    name: 'QuantStudio 5 Real-Time PCR (384-Well)',
    category: 'Molecular Diagnostics',
    assetTag: 'AST-QPCR-104',
    serialNumber: 'QS5-384-8841',
    location: 'Cleanroom Genomics Core, Bay 2',
    status: 'warning',
    lastCalibrated: '2026-08-01',
    nextDue: '2026-11-15',
    driftPercentage: 2.85,
    qualifications: { iq: true, oq: true, pq: false },
    readings: [
      { standard: 55.0, measured: 55.4, tolerance: 0.3 },
      { standard: 65.0, measured: 65.8, tolerance: 0.3 },
      { standard: 75.0, measured: 76.2, tolerance: 0.3 },
      { standard: 85.0, measured: 86.9, tolerance: 0.3 },
      { standard: 95.0, measured: 97.4, tolerance: 0.3 },
    ],
    slope: 1.049,
    intercept: -2.31,
    rSquared: 0.9982,
  },
  {
    id: 'eq-003',
    name: 'Sartorius Entris II Analytical Balance (0.1mg)',
    category: 'Gravimetric Metrology',
    assetTag: 'AST-BAL-017',
    serialNumber: 'SRT-0199421',
    location: 'Formulation Suite A, Isolator 1',
    status: 'locked_out',
    lastCalibrated: '2026-05-10',
    nextDue: '2026-11-01',
    driftPercentage: 6.40,
    qualifications: { iq: true, oq: false, pq: false },
    readings: [
      { standard: 0.05, measured: 0.054, tolerance: 0.001 },
      { standard: 0.50, measured: 0.531, tolerance: 0.005 },
      { standard: 5.00, measured: 5.280, tolerance: 0.02 },
      { standard: 50.0, measured: 53.12, tolerance: 0.1 },
    ],
    slope: 1.062,
    intercept: 0.003,
    rSquared: 0.9941,
  },
  {
    id: 'eq-004',
    name: 'Eppendorf 5424R Refrigerated Microcentrifuge',
    category: 'Centrifugation',
    assetTag: 'AST-CENT-033',
    serialNumber: 'EPP-984421',
    location: 'Cell Biology Lab, Bench 1',
    status: 'calibrated',
    lastCalibrated: '2026-09-20',
    nextDue: '2027-03-20',
    driftPercentage: 0.18,
    qualifications: { iq: true, oq: true, pq: true },
    readings: [
      { standard: 1000, measured: 1002, tolerance: 20 },
      { standard: 5000, measured: 5006, tolerance: 50 },
      { standard: 10000, measured: 9988, tolerance: 100 },
      { standard: 15000, measured: 15012, tolerance: 150 },
    ],
    slope: 1.0006,
    intercept: -1.2,
    rSquared: 0.99998,
  },
  {
    id: 'eq-005',
    name: 'Bio-Rad ChemiDoc MP Imaging System',
    category: 'Optical Imagers',
    assetTag: 'AST-IMG-056',
    serialNumber: 'BR-CHEMI-449',
    location: 'Darkroom Imaging Suite',
    status: 'in_service',
    lastCalibrated: '2026-10-30',
    nextDue: '2027-04-30',
    driftPercentage: 0.85,
    qualifications: { iq: true, oq: true, pq: true },
    readings: [
      { standard: 100, measured: 99.2, tolerance: 2 },
      { standard: 500, measured: 497.1, tolerance: 5 },
      { standard: 1000, measured: 994.0, tolerance: 10 },
      { standard: 2000, measured: 1989.4, tolerance: 20 },
    ],
    slope: 0.9942,
    intercept: 0.32,
    rSquared: 0.99991,
  },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const EquipmentCalibrationModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [equipment, setEquipment] = useState<EquipmentItem[]>(INITIAL_EQUIPMENT);
  const [selectedId, setSelectedId] = useState<string>('eq-001');
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [witnessName, setWitnessName] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  if (!isOpen) return null;

  const selected = equipment.find((e) => e.id === selectedId) || equipment[0];

  const toggleLockout = (id: string) => {
    setEquipment((prev) =>
      prev.map((e) => {
        if (e.id === id) {
          const nextStatus = e.status === 'locked_out' ? 'warning' : 'locked_out';
          return { ...e, status: nextStatus };
        }
        return e;
      })
    );
  };

  const handleExecuteRecalibration = () => {
    setEquipment((prev) =>
      prev.map((e) => {
        if (e.id === selected.id) {
          return {
            ...e,
            status: 'calibrated',
            driftPercentage: 0.05,
            lastCalibrated: new Date().toISOString().slice(0, 10),
            nextDue: '2027-05-01',
            rSquared: 0.99999,
            readings: e.readings.map((r) => ({
              ...r,
              measured: Number((r.standard * (1 + (Math.random() * 0.002 - 0.001))).toFixed(3)),
            })),
          };
        }
        return e;
      })
    );
  };

  // SVG dimensions for Calibration regression plot
  const plotW = 420;
  const plotH = 220;
  const pad = 35;
  const maxStd = Math.max(...selected.readings.map((r) => r.standard));
  const maxMeas = Math.max(...selected.readings.map((r) => r.measured));
  const maxAxis = Math.max(maxStd, maxMeas) * 1.1;

  const toX = (val: number) => pad + (val / maxAxis) * (plotW - pad * 2);
  const toY = (val: number) => plotH - pad - (val / maxAxis) * (plotH - pad * 2);

  return (
    <div className="modal-backdrop futuristic-backdrop" onClick={onClose}>
      <div
        className="modal-container futuristic-calibration-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1180px', width: '95vw', maxHeight: '92vh' }}
      >
        {/* Header */}
        <div className="futuristic-modal-header">
          <div className="flex items-center gap-3">
            <div className="futuristic-icon-badge cyan-pulse">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="futuristic-modal-title">GxP Equipment Calibration & Qualification Hub</h2>
                <span className="gxp-pill gxp-certified">FDA 21 CFR §11 & ISO 17025</span>
              </div>
              <p className="futuristic-modal-sub">
                Real-time metrology regression, drift tolerance monitoring, IQ/OQ/PQ records & automated execution lockout.
              </p>
            </div>
          </div>
          <button className="futuristic-close-btn" onClick={onClose} aria-label="Close Calibration Hub">
            ✕
          </button>
        </div>

        {/* Global Metrology Summary KPI Ribbon */}
        <div className="calibration-kpi-ribbon">
          <div className="cal-kpi-card">
            <span className="cal-kpi-lbl">TOTAL INSTRUMENTS</span>
            <span className="cal-kpi-val text-cyan">{equipment.length}</span>
            <span className="cal-kpi-sub">All assets registered</span>
          </div>
          <div className="cal-kpi-card">
            <span className="cal-kpi-lbl">CALIBRATED & GxP ACTIVE</span>
            <span className="cal-kpi-val text-emerald">
              {equipment.filter((e) => e.status === 'calibrated' || e.status === 'in_service').length}
            </span>
            <span className="cal-kpi-sub">Certified for runs</span>
          </div>
          <div className="cal-kpi-card">
            <span className="cal-kpi-lbl">DRIFT WARNING (&gt;2.5%)</span>
            <span className="cal-kpi-val text-amber">
              {equipment.filter((e) => e.status === 'warning').length}
            </span>
            <span className="cal-kpi-sub">Recalibration due</span>
          </div>
          <div className="cal-kpi-card">
            <span className="cal-kpi-lbl">GXP HARD LOCKOUT</span>
            <span className="cal-kpi-val text-rose">
              {equipment.filter((e) => e.status === 'locked_out').length}
            </span>
            <span className="cal-kpi-sub">ELN execution blocked</span>
          </div>
        </div>

        {/* Main Body */}
        <div className="calibration-body-grid">
          {/* Left Column: Equipment Master Registry List */}
          <div className="calibration-sidebar-card">
            <div className="cal-section-header">
              <span className="cal-section-title">LABORATORY ASSET DIRECTORY</span>
              <span className="cal-count-badge">{equipment.length} UNITS</span>
            </div>
            <div className="cal-asset-list">
              {equipment.map((item) => {
                const isSelected = item.id === selectedId;
                const statusColor =
                  item.status === 'calibrated'
                    ? 'emerald'
                    : item.status === 'warning'
                    ? 'amber'
                    : item.status === 'locked_out'
                    ? 'rose'
                    : 'cyan';

                return (
                  <div
                    key={item.id}
                    className={`cal-asset-item ${isSelected ? 'active' : ''} status-${item.status}`}
                    onClick={() => setSelectedId(item.id)}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className="cal-asset-tag">{item.assetTag}</span>
                      <span className={`status-badge-mini ${statusColor}`}>
                        {item.status.toUpperCase().replace('_', ' ')}
                      </span>
                    </div>
                    <div className="cal-asset-name">{item.name}</div>
                    <div className="flex justify-between items-center text-xs mt-2 text-slate-400">
                      <span>{item.category}</span>
                      <span className={`cal-drift-pill ${item.driftPercentage > 2.5 ? 'drift-high' : 'drift-low'}`}>
                        Δ {item.driftPercentage}% drift
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Metrology Inspection & Lockout Management */}
          <div className="calibration-detail-pane">
            {/* Top Info Bar */}
            <div className="cal-asset-header-panel">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="cal-detail-name">{selected.name}</h3>
                  <span className={`gxp-status-pill status-${selected.status}`}>
                    {selected.status === 'locked_out' ? '🔒 GxP LOCKED OUT' : `● ${selected.status.toUpperCase()}`}
                  </span>
                </div>
                <div className="cal-detail-meta">
                  <span>Tag: <strong>{selected.assetTag}</strong></span>
                  <span>S/N: <strong>{selected.serialNumber}</strong></span>
                  <span>Location: <strong>{selected.location}</strong></span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className={`cal-btn ${selected.status === 'locked_out' ? 'cal-btn-unlock' : 'cal-btn-lockout'}`}
                  onClick={() => toggleLockout(selected.id)}
                  title="Toggle GxP execution lockout enforcement in notebook protocols"
                >
                  {selected.status === 'locked_out' ? '🔓 Release Lockout' : '🔒 Force Lockout'}
                </button>
                <button className="cal-btn cal-btn-primary" onClick={handleExecuteRecalibration}>
                  ⚡ Recalibrate & Certify
                </button>
              </div>
            </div>

            {selected.status === 'locked_out' && (
              <div className="cal-lockout-banner">
                <div className="flex items-center gap-3">
                  <div className="cal-lock-icon">⚠️</div>
                  <div>
                    <strong>HARD LOCKOUT ENFORCED:</strong> This asset has drifted beyond the allowed metrological
                    tolerance limit ($\Delta &gt; 5.0\%$) or calibration has expired. Protocols attempting to bind this
                    instrument will be automatically halted by the Aura GxP Engine until recalibration is certified.
                  </div>
                </div>
              </div>
            )}

            {/* Middle Grid: Regression Plot & Standards Table */}
            <div className="cal-analytics-grid">
              {/* Regression Chart Card */}
              <div className="cal-card">
                <div className="flex justify-between items-center mb-2">
                  <span className="cal-card-title">LINEAR RESPONSE REGRESSION CURVE</span>
                  <span className="cal-r2-badge">R² = {selected.rSquared}</span>
                </div>
                <div className="cal-chart-wrapper">
                  <svg width="100%" height="220" viewBox={`0 0 ${plotW} ${plotH}`} className="cal-svg-plot">
                    {/* Grid lines */}
                    {[0.25, 0.5, 0.75, 1.0].map((f, i) => (
                      <g key={i}>
                        <line
                          x1={pad}
                          y1={toY(maxAxis * f)}
                          x2={plotW - pad}
                          y2={toY(maxAxis * f)}
                          stroke="rgba(255,255,255,0.08)"
                          strokeDasharray="3 3"
                        />
                        <line
                          x1={toX(maxAxis * f)}
                          y1={plotH - pad}
                          x2={toX(maxAxis * f)}
                          y2={pad}
                          stroke="rgba(255,255,255,0.08)"
                          strokeDasharray="3 3"
                        />
                      </g>
                    ))}

                    {/* Axes */}
                    <line x1={pad} y1={plotH - pad} x2={plotW - pad} y2={plotH - pad} stroke="rgba(255,255,255,0.3)" />
                    <line x1={pad} y1={pad} x2={pad} y2={plotH - pad} stroke="rgba(255,255,255,0.3)" />

                    {/* Ideal diagonal y = x */}
                    <line
                      x1={toX(0)}
                      y1={toY(0)}
                      x2={toX(maxAxis * 0.95)}
                      y2={toY(maxAxis * 0.95)}
                      stroke="rgba(100,200,255,0.25)"
                      strokeDasharray="4 4"
                      strokeWidth="1.5"
                    />

                    {/* Fitted line */}
                    <line
                      x1={toX(0)}
                      y1={toY(selected.intercept)}
                      x2={toX(maxAxis * 0.95)}
                      y2={toY(selected.slope * maxAxis * 0.95 + selected.intercept)}
                      stroke={selected.status === 'locked_out' ? '#f43f5e' : '#06b6d4'}
                      strokeWidth="2.5"
                    />

                    {/* Measured Points */}
                    {selected.readings.map((r, i) => {
                      const cx = toX(r.standard);
                      const cy = toY(r.measured);
                      const isDrift = Math.abs(r.measured - r.standard) > r.tolerance;
                      return (
                        <g key={i} className="cal-datapoint-group">
                          <circle
                            cx={cx}
                            cy={cy}
                            r="5"
                            fill={isDrift ? '#f43f5e' : '#10b981'}
                            stroke="#0f172a"
                            strokeWidth="2"
                          />
                          <circle cx={cx} cy={cy} r="9" fill="none" stroke={isDrift ? '#f43f5e' : '#10b981'} strokeWidth="1" opacity="0.4" />
                        </g>
                      );
                    })}

                    {/* Labels */}
                    <text x={plotW / 2} y={plotH - 8} fill="rgba(255,255,255,0.6)" fontSize="10" textAnchor="middle">
                      Standard Reference Target
                    </text>
                    <text
                      x={-plotH / 2}
                      y={14}
                      fill="rgba(255,255,255,0.6)"
                      fontSize="10"
                      textAnchor="middle"
                      transform="rotate(-90)"
                    >
                      Instrument Reading
                    </text>
                  </svg>
                </div>
                <div className="cal-math-readout">
                  <span>Regression Eq: <code>y = {selected.slope}x + ({selected.intercept})</code></span>
                  <span>Tolerance Limit: <code>±3σ (99.7%)</code></span>
                </div>
              </div>

              {/* Multi-point Standards & Drift Table */}
              <div className="cal-card">
                <span className="cal-card-title">VERIFICATION REFERENCE STANDARDS</span>
                <div className="cal-table-scroll">
                  <table className="cal-table">
                    <thead>
                      <tr>
                        <th>Std Value</th>
                        <th>Measured</th>
                        <th>Δ Dev</th>
                        <th>Tol Max</th>
                        <th>Pass/Fail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.readings.map((r, i) => {
                        const dev = Number((r.measured - r.standard).toFixed(3));
                        const passed = Math.abs(dev) <= r.tolerance;
                        return (
                          <tr key={i}>
                            <td><strong>{r.standard}</strong></td>
                            <td className="text-cyan">{r.measured}</td>
                            <td className={passed ? 'text-emerald' : 'text-rose'}>
                              {dev > 0 ? `+${dev}` : dev}
                            </td>
                            <td>±{r.tolerance}</td>
                            <td>
                              <span className={`cal-flag ${passed ? 'pass' : 'fail'}`}>
                                {passed ? 'PASS' : 'EXCEEDED'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="cal-iq-oq-row">
                  <div className="flex items-center gap-2">
                    <span className="cal-label">GxP Qualification:</span>
                    <span className={`qual-pill ${selected.qualifications.iq ? 'qual-pass' : 'qual-fail'}`}>
                      IQ {selected.qualifications.iq ? '✓' : '✗'}
                    </span>
                    <span className={`qual-pill ${selected.qualifications.oq ? 'qual-pass' : 'qual-fail'}`}>
                      OQ {selected.qualifications.oq ? '✓' : '✗'}
                    </span>
                    <span className={`qual-pill ${selected.qualifications.pq ? 'qual-pass' : 'qual-fail'}`}>
                      PQ {selected.qualifications.pq ? '✓' : '✗'}
                    </span>
                  </div>
                  <div className="cal-cal-dates">
                    Last: {selected.lastCalibrated} | Next Due: <strong>{selected.nextDue}</strong>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Panel: Audit Trail & Calibration Certificate Sign-off */}
            <div className="cal-audit-panel">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-sm font-semibold text-slate-200">21 CFR Part 11 Audit Trail & Electronic Signatures</span>
                  <div className="text-xs text-slate-400">
                    All calibration calibrations, offsets, and lockout overrides require dual cryptographically signed credentials.
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="cal-btn-ghost" onClick={() => alert('Exporting ISO 17025 PDF Certificate...')}>
                    📄 Export ISO 17025 Certificate
                  </button>
                  <button className="cal-btn-ghost" onClick={() => setOverrideModalOpen(true)}>
                    ✍️ Add Quality Witness Sign-off
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Override Modal */}
        {overrideModalOpen && (
          <div className="sub-modal-backdrop" onClick={() => setOverrideModalOpen(false)}>
            <div className="sub-modal-card" onClick={(e) => e.stopPropagation()}>
              <h4 className="text-base font-bold text-white mb-2">GxP Dual-Witness Calibration Sign-Off</h4>
              <p className="text-xs text-slate-400 mb-4">
                Record certified metrology sign-off for {selected.name} under FDA 21 CFR Part 11 guidelines.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-300 block mb-1">QA Witness Name</label>
                  <input
                    type="text"
                    className="futuristic-input w-full"
                    placeholder="e.g. Dr. Robert Vance, Head of QA"
                    value={witnessName}
                    onChange={(e) => setWitnessName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-300 block mb-1">Metrology / Calibration Protocol Note</label>
                  <textarea
                    className="futuristic-input w-full"
                    rows={3}
                    placeholder="NIST-traceable weights utilized, certificate cert# CAL-2026-9912..."
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button className="cal-btn-ghost" onClick={() => setOverrideModalOpen(false)}>
                    Cancel
                  </button>
                  <button
                    className="cal-btn cal-btn-primary"
                    onClick={() => {
                      alert(`Signed & Recorded into GxP Ledger: Witness ${witnessName}`);
                      setOverrideModalOpen(false);
                      setWitnessName('');
                      setOverrideReason('');
                    }}
                  >
                    Authorize & Sign Certificate
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

