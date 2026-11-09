import React, { useState } from 'react';

export interface GanttTask {
  id: string;
  resourceId: string; // equipment or scientist id
  resourceType: 'equipment' | 'scientist';
  title: string;
  protocol: string;
  project: string;
  operator: string;
  startHour: number; // offset hours from start of timeline window (0 - 48 or 0 - 168)
  durationHours: number;
  status: 'running' | 'scheduled' | 'maintenance' | 'collision' | 'locked_out';
  dependsOnId?: string;
  color?: string;
}

export interface ResourceLane {
  id: string;
  name: string;
  type: 'equipment' | 'scientist';
  category: string;
  capacityHoursPerWeek: number;
  avatarOrIcon: string;
  isLockedOut?: boolean;
}

const RESOURCE_LANES: ResourceLane[] = [
  // Equipment Lanes
  { id: 'eq-hplc', name: 'Agilent 1260 Infinity II HPLC', type: 'equipment', category: 'Analytical', capacityHoursPerWeek: 120, avatarOrIcon: '🧪' },
  { id: 'eq-qpcr', name: 'QuantStudio 5 384-Well qPCR', type: 'equipment', category: 'Genomics', capacityHoursPerWeek: 80, avatarOrIcon: '🧬' },
  { id: 'eq-facs', name: 'BD FACSAria Fusion Sorter', type: 'equipment', category: 'Flow Cytometry', capacityHoursPerWeek: 60, avatarOrIcon: '🔬' },
  { id: 'eq-bioreactor', name: 'Sartorius Biostat B 5L Bioreactor', type: 'equipment', category: 'Bioprocess', capacityHoursPerWeek: 168, avatarOrIcon: '🧫' },
  { id: 'eq-balance', name: 'Sartorius Entris Balance (GxP Lockout)', type: 'equipment', category: 'Metrology', capacityHoursPerWeek: 40, avatarOrIcon: '⚖️', isLockedOut: true },

  // Scientist Lanes
  { id: 'sci-sarah', name: 'Dr. Sarah Chen (Lead PI)', type: 'scientist', category: 'Molecular Bio', capacityHoursPerWeek: 40, avatarOrIcon: '👩‍🔬' },
  { id: 'sci-marcus', name: 'Marcus Brody (Senior Bio-Engineer)', type: 'scientist', category: 'Bioprocess', capacityHoursPerWeek: 40, avatarOrIcon: '👨‍🔬' },
  { id: 'sci-elena', name: 'Dr. Elena Rostova (Flow Core Manager)', type: 'scientist', category: 'Cytometry', capacityHoursPerWeek: 40, avatarOrIcon: '👩‍🔬' },
  { id: 'sci-alex', name: 'Alex Rivera (Automation Specialist)', type: 'scientist', category: 'Assay Dev', capacityHoursPerWeek: 40, avatarOrIcon: '🧑‍💻' },
];

const INITIAL_GANTT_TASKS: GanttTask[] = [
  // Day 1 & 2 Tasks
  {
    id: 'gt-01',
    resourceId: 'eq-hplc',
    resourceType: 'equipment',
    title: 'Purification Assay #04',
    protocol: 'AEX-HPLC Salt Gradient Peak Collection',
    project: 'CRISPR CAR-T Target #4',
    operator: 'Dr. Sarah Chen',
    startHour: 4,
    durationHours: 8,
    status: 'running',
    color: '#06b6d4',
  },
  {
    id: 'gt-02',
    resourceId: 'eq-hplc',
    resourceType: 'equipment',
    title: 'Solvent Flush & Column Clean',
    protocol: 'Column Maintenance SOP-701',
    project: 'Lab Operations',
    operator: 'Alex Rivera',
    startHour: 13,
    durationHours: 4,
    status: 'scheduled',
    color: '#3b82f6',
  },
  {
    id: 'gt-03',
    resourceId: 'eq-qpcr',
    resourceType: 'equipment',
    title: 'Viral Titer Quantitation Run A',
    protocol: 'AAV9 ddPCR / TaqMan Multiplex Assay',
    project: 'AAV9 Capsid Optimization',
    operator: 'Dr. Sarah Chen',
    startHour: 6,
    durationHours: 5,
    status: 'scheduled',
    color: '#10b981',
  },
  {
    id: 'gt-04',
    resourceId: 'eq-qpcr',
    resourceType: 'equipment',
    title: 'OVERLAP CONFLICT: mRNA Copy Assay',
    protocol: 'SYBR Green Duplex qPCR',
    project: 'mRNA Vaccine Stability',
    operator: 'Marcus Brody',
    startHour: 9, // overlaps with gt-03 (6-11)
    durationHours: 6,
    status: 'collision',
    color: '#f43f5e',
  },
  {
    id: 'gt-05',
    resourceId: 'eq-facs',
    resourceType: 'equipment',
    title: 'CAR-T Single-Cell Sorting',
    protocol: '8-Color Fluorescence Surface Marker Sort',
    project: 'CRISPR CAR-T Target #4',
    operator: 'Dr. Elena Rostova',
    startHour: 8,
    durationHours: 7,
    status: 'scheduled',
    color: '#8b5cf6',
  },
  {
    id: 'gt-06',
    resourceId: 'eq-bioreactor',
    resourceType: 'equipment',
    title: 'CHO-K1 Fed-Batch Fermentation (48h)',
    protocol: '7-Day High Density Perfusion Culture',
    project: 'Monoclonal mAb Scale-up',
    operator: 'Marcus Brody',
    startHour: 2,
    durationHours: 36,
    status: 'running',
    color: '#f59e0b',
  },
  {
    id: 'gt-07',
    resourceId: 'eq-balance',
    resourceType: 'equipment',
    title: 'GxP LOCKOUT: Analytical Weighed Aliquot',
    protocol: 'Calibration Expired - Execution Blocked',
    project: 'Formulation Suite A',
    operator: 'Alex Rivera',
    startHour: 10,
    durationHours: 6,
    status: 'locked_out',
    color: '#ef4444',
  },

  // Scientist Lane allocations
  {
    id: 'gt-101',
    resourceId: 'sci-sarah',
    resourceType: 'scientist',
    title: 'HPLC Assay + qPCR Setup',
    protocol: 'AEX-HPLC & TaqMan Runs',
    project: 'CRISPR CAR-T Target #4',
    operator: 'Dr. Sarah Chen',
    startHour: 4,
    durationHours: 9,
    status: 'running',
    color: '#06b6d4',
  },
  {
    id: 'gt-102',
    resourceId: 'sci-marcus',
    resourceType: 'scientist',
    title: 'Bioreactor Inoculation & Sampling',
    protocol: 'Dissolved O2 & pH calibration',
    project: 'Monoclonal mAb Scale-up',
    operator: 'Marcus Brody',
    startHour: 2,
    durationHours: 10,
    status: 'running',
    color: '#f59e0b',
  },
  {
    id: 'gt-103',
    resourceId: 'sci-elena',
    resourceType: 'scientist',
    title: 'Laser Alignment & Sorting',
    protocol: 'FACSAria 8-Color Single Cell',
    project: 'CRISPR CAR-T Target #4',
    operator: 'Dr. Elena Rostova',
    startHour: 7,
    durationHours: 8,
    status: 'scheduled',
    color: '#8b5cf6',
  },
  {
    id: 'gt-104',
    resourceId: 'sci-alex',
    resourceType: 'scientist',
    title: 'HPLC Maintenance & Balance Calib',
    protocol: 'SOP-701 Column Clean',
    project: 'Lab Operations',
    operator: 'Alex Rivera',
    startHour: 11,
    durationHours: 7,
    status: 'scheduled',
    color: '#3b82f6',
  },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const GanttResourcePlannerModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [tasks, setTasks] = useState<GanttTask[]>(INITIAL_GANTT_TASKS);
  const [activeLaneType, setActiveLaneType] = useState<'equipment' | 'scientist'>('equipment');
  const [timeZoom, setTimeZoom] = useState<'shift' | 'week' | 'month'>('shift');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>('gt-04');
  const [showNewBookingModal, setShowNewBookingModal] = useState(false);

  // New Booking form state
  const [newTitle, setNewTitle] = useState('');
  const [newResource, setNewResource] = useState('eq-hplc');
  const [newStartHour, setNewStartHour] = useState(14);
  const [newDuration, setNewDuration] = useState(4);
  const [newOperator, setNewOperator] = useState('Dr. Sarah Chen');
  const [newProject, setNewProject] = useState('CRISPR CAR-T Target #4');

  if (!isOpen) return null;

  // Total hours displayed based on zoom level
  const totalHours = timeZoom === 'shift' ? 24 : timeZoom === 'week' ? 96 : 168;
  const hourStep = timeZoom === 'shift' ? 2 : timeZoom === 'week' ? 8 : 12;

  // Filter lanes by active tab
  const visibleLanes = RESOURCE_LANES.filter((l) => l.type === activeLaneType);

  // Filter tasks
  const filteredTasks = tasks.filter((t) => {
    if (t.resourceType !== activeLaneType) return false;
    if (selectedProjectId !== 'all' && t.project !== selectedProjectId) return false;
    return true;
  });

  const selectedTask = tasks.find((t) => t.id === selectedTaskId);

  // Compute workload metrics
  const totalCollisions = tasks.filter((t) => t.status === 'collision').length;
  const totalLockedOutRuns = tasks.filter((t) => t.status === 'locked_out').length;
  const activeEquipCount = RESOURCE_LANES.filter((r) => r.type === 'equipment' && !r.isLockedOut).length;

  const handleLevelWorkload = () => {
    // 1-Click Auto-Leveling: Shift colliding task gt-04 forward by 3 hours so it runs right after gt-03 finishes!
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === 'gt-04') {
          return {
            ...t,
            title: 'RESOLVED: mRNA Copy Assay',
            startHour: 11, // moved after 6-11 qPCR slot
            status: 'scheduled',
            color: '#10b981',
          };
        }
        return t;
      })
    );
  };

  const handleCreateBooking = () => {
    if (!newTitle) return;
    const laneObj = RESOURCE_LANES.find((l) => l.id === newResource);
    const newTask: GanttTask = {
      id: `gt-${Date.now().toString().slice(-4)}`,
      resourceId: newResource,
      resourceType: laneObj?.type || 'equipment',
      title: newTitle,
      protocol: 'Assay SOP Standard Run',
      project: newProject,
      operator: newOperator,
      startHour: newStartHour,
      durationHours: newDuration,
      status: laneObj?.isLockedOut ? 'locked_out' : 'scheduled',
      color: laneObj?.isLockedOut ? '#ef4444' : '#06b6d4',
    };
    setTasks([...tasks, newTask]);
    setSelectedTaskId(newTask.id);
    setShowNewBookingModal(false);
    setNewTitle('');
  };

  return (
    <div className="modal-backdrop futuristic-backdrop" onClick={onClose}>
      <div
        className="modal-container futuristic-gantt-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1280px', width: '96vw', maxHeight: '94vh' }}
      >
        {/* Header */}
        <div className="futuristic-modal-header">
          <div className="flex items-center gap-3">
            <div className="futuristic-icon-badge cyan-pulse">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
                <path d="M7 14h4" />
                <path d="M11 18h6" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="futuristic-modal-title">Gantt Resource Scheduling & Workload Planner</h2>
                <span className="gxp-pill gxp-certified">Dynamic Capacity & Conflict Engine</span>
              </div>
              <p className="futuristic-modal-sub">
                Multi-track timeline for instrument slots, scientist operator hours, automated overlap collision guard & GxP calibration sync.
              </p>
            </div>
          </div>
          <button className="futuristic-close-btn" onClick={onClose} aria-label="Close Gantt Planner">
            ✕
          </button>
        </div>

        {/* Global Workload KPI Ribbon */}
        <div className="gantt-kpi-ribbon">
          <div className="gantt-kpi-card">
            <span className="lbl">ACTIVE LANES</span>
            <span className="val text-cyan">
              {visibleLanes.length} {activeLaneType === 'equipment' ? 'Instruments' : 'Scientists'}
            </span>
            <span className="sub">{activeEquipCount} available for immediate booking</span>
          </div>
          <div className="gantt-kpi-card">
            <span className="lbl">LAB SCHEDULE OVERLAPS</span>
            <span className={`val ${totalCollisions > 0 ? 'text-rose' : 'text-emerald'}`}>
              {totalCollisions} COLLISIONS
            </span>
            <span className="sub">
              {totalCollisions > 0 ? 'Double booking detected on qPCR core' : 'All runs collision-free'}
            </span>
          </div>
          <div className="gantt-kpi-card">
            <span className="lbl">GXP LOCKOUT BLOCKS</span>
            <span className="val text-amber">{totalLockedOutRuns} INSTRUMENT RUNS</span>
            <span className="sub">Sartorius balance calibration overdue</span>
          </div>
          <div className="gantt-kpi-card">
            <span className="lbl">TEAM CAPACITY UTILIZATION</span>
            <span className="val text-emerald">78.4% OPTIMAL</span>
            <span className="sub">No scientist over-allocated (&gt;90%)</span>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="gantt-toolbar">
          <div className="flex items-center gap-3">
            {/* View Mode Toggle: Equipment vs Scientists */}
            <div className="gantt-tab-group">
              <button
                className={`gantt-tab-btn ${activeLaneType === 'equipment' ? 'active' : ''}`}
                onClick={() => setActiveLaneType('equipment')}
              >
                🔬 Instrument Tracks ({RESOURCE_LANES.filter((l) => l.type === 'equipment').length})
              </button>
              <button
                className={`gantt-tab-btn ${activeLaneType === 'scientist' ? 'active' : ''}`}
                onClick={() => setActiveLaneType('scientist')}
              >
                👥 Scientist & Team Tracks ({RESOURCE_LANES.filter((l) => l.type === 'scientist').length})
              </button>
            </div>

            {/* Project Filter */}
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="futuristic-select-compact"
            >
              <option value="all">All Projects</option>
              <option value="CRISPR CAR-T Target #4">CRISPR CAR-T Target #4</option>
              <option value="AAV9 Capsid Optimization">AAV9 Capsid Optimization</option>
              <option value="mRNA Vaccine Stability">mRNA Vaccine Stability</option>
              <option value="Monoclonal mAb Scale-up">Monoclonal mAb Scale-up</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            {/* Zoom Toggle */}
            <div className="gantt-zoom-group">
              <button
                className={`zoom-btn ${timeZoom === 'shift' ? 'active' : ''}`}
                onClick={() => setTimeZoom('shift')}
              >
                24h Shift
              </button>
              <button
                className={`zoom-btn ${timeZoom === 'week' ? 'active' : ''}`}
                onClick={() => setTimeZoom('week')}
              >
                4-Day Run
              </button>
              <button
                className={`zoom-btn ${timeZoom === 'month' ? 'active' : ''}`}
                onClick={() => setTimeZoom('month')}
              >
                7-Day Sprint
              </button>
            </div>

            {/* Smart 1-Click Collision Optimizer */}
            {totalCollisions > 0 && (
              <button className="gantt-btn gantt-btn-amber" onClick={handleLevelWorkload}>
                ⚡ Auto-Resolve Collisions
              </button>
            )}

            <button className="gantt-btn gantt-btn-primary" onClick={() => setShowNewBookingModal(true)}>
              + Schedule Booking
            </button>
          </div>
        </div>

        {/* Main Gantt Viewport */}
        <div className="gantt-viewport-grid">
          {/* Timeline Viewport Canvas */}
          <div className="gantt-canvas-card">
            <div className="gantt-header-row">
              <div className="gantt-lane-header-col">RESOURCE / ASSET</div>
              <div className="gantt-time-axis">
                {Array.from({ length: totalHours / hourStep + 1 }).map((_, i) => {
                  const h = i * hourStep;
                  return (
                    <div
                      key={h}
                      className="time-tick-label"
                      style={{ left: `${(h / totalHours) * 100}%` }}
                    >
                      +{h}h
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Lane Rows */}
            <div className="gantt-lanes-scroll">
              {visibleLanes.map((lane) => {
                const laneTasks = filteredTasks.filter((t) => t.resourceId === lane.id);
                // Calculate capacity percentage
                const totalBookedHours = laneTasks.reduce((acc, t) => acc + t.durationHours, 0);
                const utilPercent = Math.min(100, Math.round((totalBookedHours / lane.capacityHoursPerWeek) * 100 * 2));

                return (
                  <div key={lane.id} className={`gantt-lane-row ${lane.isLockedOut ? 'lane-locked-out' : ''}`}>
                    {/* Left Resource Info Column */}
                    <div className="gantt-lane-label">
                      <div className="flex items-center gap-2">
                        <span className="lane-icon">{lane.avatarOrIcon}</span>
                        <div>
                          <div className="lane-name font-semibold text-white truncate" title={lane.name}>
                            {lane.name}
                          </div>
                          <div className="lane-meta flex items-center gap-2 text-xs text-slate-400">
                            <span>{lane.category}</span>
                            <span className="text-cyan font-mono">{utilPercent}% load</span>
                            {lane.isLockedOut && <span className="text-rose font-bold">🔒 LOCKED OUT</span>}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Right Horizontal Timeline Track */}
                    <div className="gantt-lane-track">
                      {/* Grid background markers */}
                      {Array.from({ length: totalHours / hourStep + 1 }).map((_, i) => (
                        <div
                          key={i}
                          className="gantt-track-gridline"
                          style={{ left: `${((i * hourStep) / totalHours) * 100}%` }}
                        />
                      ))}

                      {/* Current Time Indicator Glowing Line */}
                      <div className="gantt-now-line" style={{ left: '16.6%' }}>
                        <span className="now-flag">LIVE</span>
                      </div>

                      {/* Rendered Task Blocks */}
                      {laneTasks.map((task) => {
                        const leftPercent = (task.startHour / totalHours) * 100;
                        const widthPercent = (task.durationHours / totalHours) * 100;
                        const isSelected = selectedTaskId === task.id;
                        const isCollision = task.status === 'collision';
                        const isLockedOut = task.status === 'locked_out';

                        return (
                          <div
                            key={task.id}
                            className={`gantt-task-bar ${isSelected ? 'selected' : ''} status-${task.status}`}
                            style={{
                              left: `${leftPercent}%`,
                              width: `${Math.max(widthPercent, 4)}%`,
                              backgroundColor: isCollision ? '#f43f5e' : isLockedOut ? '#ef4444' : task.color || '#06b6d4',
                            }}
                            onClick={() => setSelectedTaskId(task.id)}
                            title={`${task.title} | ${task.operator} (${task.durationHours}h)`}
                          >
                            <div className="task-bar-inner">
                              <span className="task-bar-title truncate">{task.title}</span>
                              <span className="task-bar-operator truncate">👤 {task.operator}</span>
                            </div>
                            {isCollision && (
                              <div className="collision-warning-pip" title="Double booking collision!">
                                ⚠️ OVERLAP
                              </div>
                            )}
                            {isLockedOut && (
                              <div className="lockout-warning-pip" title="Instrument calibration expired!">
                                🔒 GxP BLOCK
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Inspector & Reservation Details Drawer */}
          <div className="gantt-inspector-card">
            <span className="gantt-inspector-title">SELECTED RESERVATION AUDIT</span>
            {selectedTask ? (
              <div className="gantt-task-details">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`status-pill ${selectedTask.status === 'collision' ? 'badge-amber' : selectedTask.status === 'locked_out' ? 'badge-slate' : 'badge-emerald'}`}>
                    {selectedTask.status.toUpperCase()}
                  </span>
                  <span className="text-xs font-mono text-cyan">{selectedTask.id}</span>
                </div>

                <h4 className="text-sm font-bold text-white mb-1">{selectedTask.title}</h4>
                <div className="text-xs text-slate-300 mb-3">{selectedTask.protocol}</div>

                <div className="gantt-detail-grid">
                  <div className="gantt-detail-item">
                    <span className="lbl">OPERATOR</span>
                    <span className="val text-white">{selectedTask.operator}</span>
                  </div>
                  <div className="gantt-detail-item">
                    <span className="lbl">PROJECT</span>
                    <span className="val text-cyan truncate">{selectedTask.project}</span>
                  </div>
                  <div className="gantt-detail-item">
                    <span className="lbl">TIMELINE OFFSET</span>
                    <span className="val text-white">Hour +{selectedTask.startHour}:00</span>
                  </div>
                  <div className="gantt-detail-item">
                    <span className="lbl">RUN DURATION</span>
                    <span className="val text-white">{selectedTask.durationHours} Hours</span>
                  </div>
                </div>

                {selectedTask.status === 'collision' && (
                  <div className="collision-alert-card mt-3">
                    <div className="text-xs font-bold text-rose-300">⚠️ SCHEDULE COLLISION DETECTED</div>
                    <div className="text-xs text-rose-200 mt-1">
                      This run collides with another booking on the same core. Click "Auto-Resolve Collisions" above or adjust start time to prevent hardware contention.
                    </div>
                  </div>
                )}

                {selectedTask.status === 'locked_out' && (
                  <div className="lockout-alert-card mt-3">
                    <div className="text-xs font-bold text-amber-300">🔒 GXP CALIBRATION LOCKOUT</div>
                    <div className="text-xs text-amber-200 mt-1">
                      This hardware has exceeded allowable drift (&gt;2.5%). Recalibration sign-off is required in the Calibration Hub before protocol release.
                    </div>
                  </div>
                )}

                <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between gap-2">
                  <button
                    className="cal-btn-ghost w-1/2"
                    onClick={() => {
                      setTasks(tasks.filter((t) => t.id !== selectedTask.id));
                      setSelectedTaskId(null);
                    }}
                  >
                    🗑️ Cancel Booking
                  </button>
                  <button
                    className="gantt-btn gantt-btn-primary w-1/2"
                    onClick={() => alert(`Exported iCal event for ${selectedTask.title}`)}
                  >
                    📅 Sync iCal (.ics)
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 py-6 text-center">
                Select any timeline booking block on the left to inspect parameters and conflict states.
              </div>
            )}

            {/* Team Capacity Mini-Leaderboard */}
            <div className="team-capacity-section mt-4 pt-4 border-t border-slate-800">
              <span className="gantt-inspector-title">LABORATORY TEAM WORKLOAD</span>
              <div className="space-y-2 mt-2">
                {[
                  { name: 'Dr. Sarah Chen', load: 82, badge: 'High Workload' },
                  { name: 'Marcus Brody', load: 74, badge: 'Optimal' },
                  { name: 'Dr. Elena Rostova', load: 60, badge: 'Available' },
                  { name: 'Alex Rivera', load: 55, badge: 'Available' },
                ].map((member) => (
                  <div key={member.name} className="flex justify-between items-center text-xs">
                    <span className="text-slate-300">{member.name}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full ${member.load > 80 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                          style={{ width: `${member.load}%` }}
                        />
                      </div>
                      <span className="font-mono text-slate-400">{member.load}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* New Reservation Dialog Modal */}
        {showNewBookingModal && (
          <div className="sub-modal-backdrop" onClick={() => setShowNewBookingModal(false)}>
            <div className="sub-modal-card" onClick={(e) => e.stopPropagation()}>
              <h4 className="text-base font-bold text-white mb-2">Schedule Equipment or Operator Slot</h4>
              <p className="text-xs text-slate-400 mb-4">
                Reserve an automated run slot with collision checking and capacity deduction.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-300 block mb-1">Run / Assay Title</label>
                  <input
                    type="text"
                    className="futuristic-input w-full"
                    placeholder="e.g. Lentiviral Vector Concentration Prep"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Target Instrument</label>
                    <select
                      className="futuristic-input w-full"
                      value={newResource}
                      onChange={(e) => setNewResource(e.target.value)}
                    >
                      {RESOURCE_LANES.filter((l) => l.type === 'equipment').map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.avatarOrIcon} {e.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Operator</label>
                    <select
                      className="futuristic-input w-full"
                      value={newOperator}
                      onChange={(e) => setNewOperator(e.target.value)}
                    >
                      <option value="Dr. Sarah Chen">Dr. Sarah Chen</option>
                      <option value="Marcus Brody">Marcus Brody</option>
                      <option value="Dr. Elena Rostova">Dr. Elena Rostova</option>
                      <option value="Alex Rivera">Alex Rivera</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Start Offset (Hour)</label>
                    <input
                      type="number"
                      min="0"
                      max="168"
                      className="futuristic-input w-full"
                      value={newStartHour}
                      onChange={(e) => setNewStartHour(parseInt(e.target.value) || 0)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Duration (Hours)</label>
                    <input
                      type="number"
                      min="1"
                      max="48"
                      className="futuristic-input w-full"
                      value={newDuration}
                      onChange={(e) => setNewDuration(parseInt(e.target.value) || 1)}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-300 block mb-1">Research Project</label>
                  <select
                    className="futuristic-input w-full"
                    value={newProject}
                    onChange={(e) => setNewProject(e.target.value)}
                  >
                    <option value="CRISPR CAR-T Target #4">CRISPR CAR-T Target #4</option>
                    <option value="AAV9 Capsid Optimization">AAV9 Capsid Optimization</option>
                    <option value="mRNA Vaccine Stability">mRNA Vaccine Stability</option>
                    <option value="Monoclonal mAb Scale-up">Monoclonal mAb Scale-up</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-3">
                  <button className="cal-btn-ghost" onClick={() => setShowNewBookingModal(false)}>
                    Cancel
                  </button>
                  <button className="gantt-btn gantt-btn-primary" onClick={handleCreateBooking}>
                    Reserve & Check Conflicts
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

