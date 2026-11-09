import React, { useState } from 'react';

export interface RodentAnimal {
  id: string;
  tag: string; // RFID / Ear notch
  strain: string;
  sex: 'Male' | 'Female';
  dob: string;
  ageWeeks: number;
  genotype: 'WT (+/+)' | 'Het (+/-)' | 'KO (-/-)' | 'Transgenic';
  cageId: string;
  rackLocation: string; // e.g. Rack A - B3
  cohort: string;
  damTag?: string; // Mother
  sireTag?: string; // Father
  weightHistory: { day: number; weightG: number }[];
  tumorVolumeMm3?: number;
  status: 'active' | 'breeding' | 'weaning' | 'humane_endpoint' | 'culled';
}

export interface BreedingPair {
  id: string;
  pairName: string;
  sireTag: string;
  damTag: string;
  matingDate: string;
  expectedLitterDate: string;
  litterPups: number;
  weanDueDate: string;
  status: 'pregnant' | 'nursing' | 'mated';
}

const INITIAL_ANIMALS: RodentAnimal[] = [
  {
    id: 'an-001',
    tag: 'RFID-C57-881',
    strain: 'C57BL/6J (Inbred)',
    sex: 'Female',
    dob: '2026-07-15',
    ageWeeks: 16,
    genotype: 'KO (-/-)',
    cageId: 'CAGE-101',
    rackLocation: 'Rack A - R1:C2',
    cohort: 'High Dose Cohort (25 mg/kg)',
    damTag: 'RFID-C57-702',
    sireTag: 'RFID-C57-699',
    weightHistory: [
      { day: 0, weightG: 22.4 },
      { day: 7, weightG: 22.8 },
      { day: 14, weightG: 23.5 },
      { day: 21, weightG: 24.1 },
      { day: 28, weightG: 23.9 },
    ],
    tumorVolumeMm3: 142.5,
    status: 'active',
  },
  {
    id: 'an-002',
    tag: 'RFID-C57-882',
    strain: 'C57BL/6J (Inbred)',
    sex: 'Female',
    dob: '2026-07-15',
    ageWeeks: 16,
    genotype: 'KO (-/-)',
    cageId: 'CAGE-101',
    rackLocation: 'Rack A - R1:C2',
    cohort: 'High Dose Cohort (25 mg/kg)',
    damTag: 'RFID-C57-702',
    sireTag: 'RFID-C57-699',
    weightHistory: [
      { day: 0, weightG: 21.8 },
      { day: 7, weightG: 22.1 },
      { day: 14, weightG: 22.9 },
      { day: 21, weightG: 23.2 },
      { day: 28, weightG: 23.0 },
    ],
    tumorVolumeMm3: 110.2,
    status: 'active',
  },
  {
    id: 'an-003',
    tag: 'RFID-NSG-204',
    strain: 'NSG (NOD.Cg-Prkdc Il2rg / SzJ)',
    sex: 'Male',
    dob: '2026-08-01',
    ageWeeks: 14,
    genotype: 'Transgenic',
    cageId: 'CAGE-102',
    rackLocation: 'Rack A - R2:C4',
    cohort: 'Vehicle Control (Saline)',
    damTag: 'RFID-NSG-110',
    sireTag: 'RFID-NSG-108',
    weightHistory: [
      { day: 0, weightG: 26.5 },
      { day: 7, weightG: 27.0 },
      { day: 14, weightG: 27.6 },
      { day: 21, weightG: 28.1 },
      { day: 28, weightG: 28.4 },
    ],
    tumorVolumeMm3: 450.8,
    status: 'active',
  },
  {
    id: 'an-004',
    tag: 'RFID-BALB-512',
    strain: 'BALB/c AnNCrl',
    sex: 'Female',
    dob: '2026-06-20',
    ageWeeks: 20,
    genotype: 'WT (+/+)',
    cageId: 'CAGE-204',
    rackLocation: 'Rack B - R3:C1',
    cohort: 'Breeding Colony Alpha',
    damTag: 'RFID-BALB-390',
    sireTag: 'RFID-BALB-388',
    weightHistory: [
      { day: 0, weightG: 24.2 },
      { day: 7, weightG: 25.1 },
      { day: 14, weightG: 27.8 },
      { day: 21, weightG: 31.5 },
      { day: 28, weightG: 34.2 },
    ],
    status: 'breeding',
  },
  {
    id: 'an-005',
    tag: 'RFID-NSG-209',
    strain: 'NSG (NOD.Cg-Prkdc Il2rg / SzJ)',
    sex: 'Male',
    dob: '2026-08-01',
    ageWeeks: 14,
    genotype: 'Transgenic',
    cageId: 'CAGE-105',
    rackLocation: 'Rack A - R4:C3',
    cohort: 'High Dose Cohort (25 mg/kg)',
    damTag: 'RFID-NSG-110',
    sireTag: 'RFID-NSG-108',
    weightHistory: [
      { day: 0, weightG: 25.8 },
      { day: 7, weightG: 24.1 },
      { day: 14, weightG: 22.0 },
      { day: 21, weightG: 20.2 },
      { day: 28, weightG: 18.9 }, // > 20% loss alert!
    ],
    tumorVolumeMm3: 890.0,
    status: 'humane_endpoint',
  },
];

const INITIAL_BREEDING_PAIRS: BreedingPair[] = [
  {
    id: 'bp-01',
    pairName: 'C57BL6-F3 Lineage Pair A',
    sireTag: 'RFID-C57-699',
    damTag: 'RFID-C57-702',
    matingDate: '2026-10-18',
    expectedLitterDate: '2026-11-08',
    litterPups: 7,
    weanDueDate: '2026-11-29',
    status: 'nursing',
  },
  {
    id: 'bp-02',
    pairName: 'NSG Breeder Stock 09',
    sireTag: 'RFID-NSG-108',
    damTag: 'RFID-NSG-110',
    matingDate: '2026-10-25',
    expectedLitterDate: '2026-11-15',
    litterPups: 0,
    weanDueDate: '2026-12-06',
    status: 'pregnant',
  },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const RodentColonyModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [animals, setAnimals] = useState<RodentAnimal[]>(INITIAL_ANIMALS);
  const [breedingPairs] = useState<BreedingPair[]>(INITIAL_BREEDING_PAIRS);
  const [selectedAnimalId, setSelectedAnimalId] = useState<string>('an-001');
  const [activeTab, setActiveTab] = useState<'inventory' | 'breeding' | 'rack_layout'>('inventory');
  const [filterStrain, setFilterStrain] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState(false);

  // New Animal Form State
  const [newTag, setNewTag] = useState('');
  const [newStrain, setNewStrain] = useState('C57BL/6J (Inbred)');
  const [newSex, setNewSex] = useState<'Male' | 'Female'>('Female');
  const [newGenotype, setNewGenotype] = useState<'WT (+/+)' | 'Het (+/-)' | 'KO (-/-)' | 'Transgenic'>('KO (-/-)');
  const [newCage, setNewCage] = useState('CAGE-101');
  const [newCohort, setNewCohort] = useState('High Dose Cohort (25 mg/kg)');

  if (!isOpen) return null;

  const filteredAnimals = animals.filter((a) => {
    if (filterStrain !== 'all' && !a.strain.includes(filterStrain)) return false;
    return true;
  });

  const selectedAnimal = animals.find((a) => a.id === selectedAnimalId) || animals[0];

  const totalAnimals = animals.length;
  const activeCohorts = new Set(animals.map((a) => a.cohort)).size;
  const humaneAlerts = animals.filter((a) => a.status === 'humane_endpoint').length;
  const totalBreedingPups = breedingPairs.reduce((acc, bp) => acc + bp.litterPups, 0);

  const handleAddAnimal = () => {
    if (!newTag) return;
    const newSpecimen: RodentAnimal = {
      id: `an-${Date.now().toString().slice(-4)}`,
      tag: newTag,
      strain: newStrain,
      sex: newSex,
      dob: '2026-09-01',
      ageWeeks: 9,
      genotype: newGenotype,
      cageId: newCage,
      rackLocation: 'Rack A - R1:C4',
      cohort: newCohort,
      weightHistory: [{ day: 0, weightG: 21.0 }],
      status: 'active',
    };
    setAnimals([newSpecimen, ...animals]);
    setSelectedAnimalId(newSpecimen.id);
    setShowAddModal(false);
    setNewTag('');
  };

  // SVG dimensions for Weight Tracking Curve
  const plotW = 380;
  const plotH = 180;
  const pad = 30;
  const weights = selectedAnimal.weightHistory;
  const maxDay = Math.max(...weights.map((w) => w.day), 28);
  const minW = Math.min(...weights.map((w) => w.weightG)) * 0.9;
  const maxW = Math.max(...weights.map((w) => w.weightG)) * 1.1;

  const toX = (day: number) => pad + (day / maxDay) * (plotW - pad * 2);
  const toY = (w: number) => plotH - pad - ((w - minW) / (maxW - minW || 1)) * (plotH - pad * 2);

  const pointsPath = weights.map((w, i) => `${i === 0 ? 'M' : 'L'} ${toX(w.day).toFixed(1)},${toY(w.weightG).toFixed(1)}`).join(' ');

  return (
    <div className="modal-backdrop futuristic-backdrop" onClick={onClose}>
      <div
        className="modal-container futuristic-rodent-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1260px', width: '96vw', maxHeight: '92vh' }}
      >
        {/* Header */}
        <div className="futuristic-modal-header">
          <div className="flex items-center gap-3">
            <div className="futuristic-icon-badge emerald-pulse">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
                <circle cx="8" cy="11" r="1.5" />
                <circle cx="16" cy="11" r="1.5" />
                <path d="M12 16c-2 0-3-1-3-1" />
                <path d="M15 15s-1 1-3 1" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="futuristic-modal-title">In Vivo Preclinical Rodent Colony Management</h2>
                <span className="gxp-pill gxp-certified">IACUC Protocol #2026-042 Approved</span>
              </div>
              <p className="futuristic-modal-sub">
                IVC ventilated cage rack matrix, breeding pedigrees, genotype tracking, tumor caliper metrics & cachexia humane endpoints.
              </p>
            </div>
          </div>
          <button className="futuristic-close-btn" onClick={onClose} aria-label="Close Colony Manager">
            ✕
          </button>
        </div>

        {/* Global Vivarium KPI Ribbon */}
        <div className="rodent-kpi-ribbon">
          <div className="rodent-kpi-card">
            <span className="lbl">TOTAL VIVARIUM SPECIMENS</span>
            <span className="val text-cyan">{totalAnimals} RODENTS</span>
            <span className="sub">Across 3 approved inbred/transgenic strains</span>
          </div>
          <div className="rodent-kpi-card">
            <span className="lbl">ACTIVE EXPERIMENTAL COHORTS</span>
            <span className="val text-emerald">{activeCohorts} COHORTS</span>
            <span className="sub">CAR-T & AAV in vivo efficacy trials</span>
          </div>
          <div className="rodent-kpi-card">
            <span className="lbl">BREEDING COLONY & LITTERS</span>
            <span className="val text-indigo-400">{totalBreedingPups} PUPS NURSING</span>
            <span className="sub">{breedingPairs.length} active breeding pairs (P21 wean)</span>
          </div>
          <div className="rodent-kpi-card">
            <span className="lbl">HUMANE ENDPOINT ALERTS</span>
            <span className={`val ${humaneAlerts > 0 ? 'text-rose font-bold' : 'text-emerald'}`}>
              {humaneAlerts} CRITICAL
            </span>
            <span className="sub">
              {humaneAlerts > 0 ? '> 20% Cachexia weight loss detected' : 'All animals within health limits'}
            </span>
          </div>
        </div>

        {/* Toolbar & Tab Switcher */}
        <div className="rodent-toolbar">
          <div className="flex items-center gap-3">
            <div className="gantt-tab-group">
              <button
                className={`gantt-tab-btn ${activeTab === 'inventory' ? 'active' : ''}`}
                onClick={() => setActiveTab('inventory')}
              >
                🐁 Animals & Cohorts ({animals.length})
              </button>
              <button
                className={`gantt-tab-btn ${activeTab === 'breeding' ? 'active' : ''}`}
                onClick={() => setActiveTab('breeding')}
              >
                🧬 Breeding Lineages & Litters ({breedingPairs.length})
              </button>
              <button
                className={`gantt-tab-btn ${activeTab === 'rack_layout' ? 'active' : ''}`}
                onClick={() => setActiveTab('rack_layout')}
              >
                🗄️ IVC Cage Rack Matrix (4x6)
              </button>
            </div>

            <select
              value={filterStrain}
              onChange={(e) => setFilterStrain(e.target.value)}
              className="futuristic-select-compact"
            >
              <option value="all">All Strains</option>
              <option value="C57BL/6J">C57BL/6J</option>
              <option value="NSG">NSG Immunodeficient</option>
              <option value="BALB/c">BALB/c</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button className="rodent-btn rodent-btn-primary" onClick={() => setShowAddModal(true)}>
              + Register Specimen / Ear Notch
            </button>
          </div>
        </div>

        {/* Body based on Active Tab */}
        {activeTab === 'inventory' && (
          <div className="rodent-grid-container">
            {/* Left Animal List Table */}
            <div className="rodent-table-card">
              <div className="cal-table-scroll" style={{ maxHeight: '420px' }}>
                <table className="procur-table">
                  <thead>
                    <tr>
                      <th>RFID / Ear Tag</th>
                      <th>Strain & Sex</th>
                      <th>Genotype</th>
                      <th>Age</th>
                      <th>Cage & Rack</th>
                      <th>Study Cohort</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAnimals.map((a) => {
                      const isSelected = a.id === selectedAnimalId;
                      const isAlert = a.status === 'humane_endpoint';
                      return (
                        <tr
                          key={a.id}
                          className={`procur-tr ${isSelected ? 'active' : ''}`}
                          onClick={() => setSelectedAnimalId(a.id)}
                        >
                          <td>
                            <strong>{a.tag}</strong>
                            {isAlert && <span className="stockout-dot" title="Humane Endpoint Alert!" />}
                          </td>
                          <td>
                            <div className="text-sm font-semibold text-white">
                              {a.sex === 'Female' ? '♀' : '♂'} {a.strain}
                            </div>
                          </td>
                          <td>
                            <code className="text-cyan">{a.genotype}</code>
                          </td>
                          <td>{a.ageWeeks} wks</td>
                          <td>
                            <span className="text-slate-300 font-mono text-xs">{a.rackLocation}</span>
                          </td>
                          <td>
                            <span className="text-xs text-indigo-300">{a.cohort}</span>
                          </td>
                          <td>
                            <span
                              className={`status-pill ${
                                a.status === 'humane_endpoint'
                                  ? 'badge-rose'
                                  : a.status === 'breeding'
                                  ? 'badge-amber'
                                  : 'badge-emerald'
                              }`}
                            >
                              {a.status.toUpperCase().replace('_', ' ')}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right Detailed Physiological Inspector & Caliper Tumor Progression */}
            <div className="rodent-detail-card">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <span className="text-xs font-mono text-cyan">{selectedAnimal.tag}</span>
                  <h3 className="text-base font-bold text-white mt-1">
                    {selectedAnimal.sex === 'Female' ? '♀ Female' : '♂ Male'} - {selectedAnimal.strain}
                  </h3>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Cage: <strong>{selectedAnimal.cageId}</strong> ({selectedAnimal.rackLocation})
                  </div>
                </div>
                <span
                  className={`status-pill ${
                    selectedAnimal.status === 'humane_endpoint' ? 'badge-rose' : 'badge-emerald'
                  }`}
                >
                  {selectedAnimal.status.toUpperCase().replace('_', ' ')}
                </span>
              </div>

              {selectedAnimal.status === 'humane_endpoint' && (
                <div className="collision-alert-card mb-3">
                  <div className="text-xs font-bold text-rose-300">⚠️ IACUC HUMANE ENDPOINT ALERT</div>
                  <div className="text-xs text-rose-200 mt-0.5">
                    Specimen has lost &gt; 20% baseline body weight (25.8g → 18.9g). Immediate veterinary consultation
                    or euthanasia protocol required under IACUC-2026-042.
                  </div>
                </div>
              )}

              {/* Weight Trajectory Longitudinal Plot */}
              <div className="rodent-plot-card">
                <div className="flex justify-between items-center mb-1">
                  <span className="cal-card-title">BODY WEIGHT TRAJECTORY (LONGITUDINAL)</span>
                  <span className="text-xs text-cyan font-mono">
                    {weights[weights.length - 1].weightG} g
                  </span>
                </div>
                <svg width="100%" height="150" viewBox={`0 0 ${plotW} ${plotH}`} className="cal-svg-plot">
                  {/* Grid Lines */}
                  {[0.25, 0.5, 0.75, 1].map((f, i) => (
                    <line
                      key={i}
                      x1={pad}
                      y1={toY(minW + (maxW - minW) * f)}
                      x2={plotW - pad}
                      y2={toY(minW + (maxW - minW) * f)}
                      stroke="rgba(255,255,255,0.06)"
                      strokeDasharray="2 3"
                    />
                  ))}
                  {/* Trend line */}
                  <path
                    d={pointsPath}
                    fill="none"
                    stroke={selectedAnimal.status === 'humane_endpoint' ? '#f43f5e' : '#10b981'}
                    strokeWidth="2.5"
                  />
                  {/* Nodes */}
                  {weights.map((w, idx) => (
                    <g key={idx}>
                      <circle
                        cx={toX(w.day)}
                        cy={toY(w.weightG)}
                        r="4"
                        fill={selectedAnimal.status === 'humane_endpoint' ? '#f43f5e' : '#10b981'}
                      />
                    </g>
                  ))}
                </svg>
              </div>

              {/* Caliper Tumor Volume Calculation */}
              {selectedAnimal.tumorVolumeMm3 && (
                <div className="spec-box mt-3">
                  <div className="flex justify-between items-center">
                    <span className="lbl">SUBCUTANEOUS TUMOR BURDEN (CALIPERS)</span>
                    <span className="text-amber font-mono font-bold text-sm">
                      {selectedAnimal.tumorVolumeMm3} mm³
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Calculated via Modified Ellipsoid formula: <code>V = (Length × Width²) / 2</code>
                  </div>
                </div>
              )}

              {/* Pedigree Parentage */}
              <div className="procur-spec-grid mt-3">
                <div className="spec-box">
                  <span className="lbl">DAM (MOTHER)</span>
                  <span className="val text-cyan font-mono">{selectedAnimal.damTag || 'N/A Foundation'}</span>
                </div>
                <div className="spec-box">
                  <span className="lbl">SIRE (FATHER)</span>
                  <span className="val text-cyan font-mono">{selectedAnimal.sireTag || 'N/A Foundation'}</span>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-slate-800 flex justify-between gap-2">
                <button
                  className="cal-btn-ghost w-1/2"
                  onClick={() => alert(`Log dose administered for ${selectedAnimal.tag}`)}
                >
                  💉 Log Dose (IP/IV)
                </button>
                <button
                  className="rodent-btn rodent-btn-primary w-1/2"
                  onClick={() => alert(`Caliper measurements updated for ${selectedAnimal.tag}`)}
                >
                  📏 Caliper Measurement
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Breeding Lineages */}
        {activeTab === 'breeding' && (
          <div className="breeding-view-grid">
            {breedingPairs.map((bp) => (
              <div key={bp.id} className="breeding-card">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="text-sm font-bold text-white">{bp.pairName}</h4>
                    <span className="text-xs text-slate-400">Pair ID: {bp.id}</span>
                  </div>
                  <span className={`status-pill ${bp.status === 'nursing' ? 'badge-emerald' : 'badge-amber'}`}>
                    {bp.status.toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center gap-3 my-3">
                  <div className="breeder-node">♂ {bp.sireTag}</div>
                  <span className="text-slate-500 font-bold">×</span>
                  <div className="breeder-node">♀ {bp.damTag}</div>
                </div>
                <div className="space-y-1 text-xs text-slate-300">
                  <div className="flex justify-between">
                    <span>Mating Initiated:</span>
                    <span className="font-mono">{bp.matingDate}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Litter Size:</span>
                    <span className="font-mono text-emerald font-bold">{bp.litterPups} Live Pups</span>
                  </div>
                  <div className="flex justify-between">
                    <span>P21 Weaning Due Date:</span>
                    <span className="font-mono text-cyan font-bold">{bp.weanDueDate}</span>
                  </div>
                </div>
                <button
                  className="rodent-btn rodent-btn-primary w-full mt-3"
                  onClick={() => alert(`Weaning workflow generated for ${bp.pairName} (7 new cage tags registered).`)}
                >
                  ✂️ Wean & Tag Pups (P21)
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Tab 3: IVC Rack Layout */}
        {activeTab === 'rack_layout' && (
          <div className="rack-layout-container">
            <div className="flex justify-between items-center mb-3">
              <span className="text-sm font-bold text-white">IVC VENTILATED CAGE RACK ALPHA (4 Rows × 6 Columns)</span>
              <span className="text-xs text-emerald">● Airflow HEPA Balanced (60 ACH)</span>
            </div>
            <div className="rack-matrix-grid">
              {['R1', 'R2', 'R3', 'R4'].map((row) =>
                ['C1', 'C2', 'C3', 'C4', 'C5', 'C6'].map((col) => {
                  const locKey = `${row}:${col}`;
                  const cageAnimals = animals.filter((a) => a.rackLocation.includes(locKey));
                  const isOccupied = cageAnimals.length > 0;
                  const hasAlert = cageAnimals.some((a) => a.status === 'humane_endpoint');

                  return (
                    <div
                      key={locKey}
                      className={`rack-cage-slot ${isOccupied ? 'occupied' : 'empty'} ${hasAlert ? 'slot-alert' : ''}`}
                    >
                      <div className="slot-header">
                        <span className="slot-coord">{locKey}</span>
                        {isOccupied && <span className="slot-count">{cageAnimals.length} 🐁</span>}
                      </div>
                      {isOccupied ? (
                        <div className="slot-body">
                          <div className="cage-code">{cageAnimals[0].cageId}</div>
                          <div className="cage-strain truncate">{cageAnimals[0].strain.split(' ')[0]}</div>
                        </div>
                      ) : (
                        <span className="empty-lbl">Vacant</span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* Registration Modal Dialog */}
        {showAddModal && (
          <div className="sub-modal-backdrop" onClick={() => setShowAddModal(false)}>
            <div className="sub-modal-card" onClick={(e) => e.stopPropagation()}>
              <h4 className="text-base font-bold text-white mb-2">Register New Specimen (RFID / Ear Notch)</h4>
              <p className="text-xs text-slate-400 mb-4">
                Record preclinical animal into vivarium database under IACUC guidelines.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-300 block mb-1">RFID / Ear Notch Tag</label>
                  <input
                    type="text"
                    className="futuristic-input w-full"
                    placeholder="e.g. RFID-C57-899"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Strain</label>
                    <select
                      className="futuristic-input w-full"
                      value={newStrain}
                      onChange={(e) => setNewStrain(e.target.value)}
                    >
                      <option value="C57BL/6J (Inbred)">C57BL/6J (Inbred)</option>
                      <option value="NSG (NOD.Cg-Prkdc Il2rg / SzJ)">NSG Immunodeficient</option>
                      <option value="BALB/c AnNCrl">BALB/c AnNCrl</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Sex</label>
                    <select
                      className="futuristic-input w-full"
                      value={newSex}
                      onChange={(e) => setNewSex(e.target.value as any)}
                    >
                      <option value="Female">♀ Female</option>
                      <option value="Male">♂ Male</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Genotype</label>
                    <select
                      className="futuristic-input w-full"
                      value={newGenotype}
                      onChange={(e) => setNewGenotype(e.target.value as any)}
                    >
                      <option value="KO (-/-)">KO (-/-)</option>
                      <option value="Het (+/-)">Het (+/-)</option>
                      <option value="WT (+/+)">WT (+/+)</option>
                      <option value="Transgenic">Transgenic</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Cage ID</label>
                    <input
                      type="text"
                      className="futuristic-input w-full"
                      value={newCage}
                      onChange={(e) => setNewCage(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-300 block mb-1">Assigned Study Cohort</label>
                  <select
                    className="futuristic-input w-full"
                    value={newCohort}
                    onChange={(e) => setNewCohort(e.target.value)}
                  >
                    <option value="High Dose Cohort (25 mg/kg)">High Dose Cohort (25 mg/kg)</option>
                    <option value="Low Dose Cohort (5 mg/kg)">Low Dose Cohort (5 mg/kg)</option>
                    <option value="Vehicle Control (Saline)">Vehicle Control (Saline)</option>
                    <option value="Breeding Colony Alpha">Breeding Colony Alpha</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-3">
                  <button className="cal-btn-ghost" onClick={() => setShowAddModal(false)}>
                    Cancel
                  </button>
                  <button className="rodent-btn rodent-btn-primary" onClick={handleAddAnimal}>
                    Register Specimen
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

