import React, { useState } from 'react';

interface PurchaseOrderItem {
  id: string;
  poNumber: string;
  reagentName: string;
  vendor: 'Sigma-Aldrich' | 'Thermo Fisher' | 'New England Biolabs' | 'Corning' | 'Qiagen';
  catalogNumber: string;
  casNumber?: string;
  quantity: number;
  unit: string;
  unitPrice: number;
  totalPrice: number;
  status: 'draft' | 'pending_pi' | 'authorized' | 'dispatched' | 'received';
  urgency: 'routine' | 'urgent' | 'critical_stockout';
  grantCode: string;
  requestedBy: string;
  currentStock: number;
  minThreshold: number;
  estimatedDelivery: string;
}

const INITIAL_POS: PurchaseOrderItem[] = [
  {
    id: 'po-101',
    poNumber: 'PO-2026-0841',
    reagentName: 'Q5® High-Fidelity 2X Master Mix',
    vendor: 'New England Biolabs',
    catalogNumber: 'M0492L',
    quantity: 4,
    unit: '500 reactions',
    unitPrice: 420.0,
    totalPrice: 1680.0,
    status: 'pending_pi',
    urgency: 'critical_stockout',
    grantCode: 'NIH-R01-HG01124',
    requestedBy: 'Dr. Sarah Chen',
    currentStock: 1,
    minThreshold: 3,
    estimatedDelivery: '2026-11-10',
  },
  {
    id: 'po-102',
    poNumber: 'PO-2026-0842',
    reagentName: 'Gibco™ Fetal Bovine Serum (FBS) Certified',
    vendor: 'Thermo Fisher',
    catalogNumber: '16000044',
    quantity: 10,
    unit: '500 mL bottle',
    unitPrice: 585.5,
    totalPrice: 5855.0,
    status: 'authorized',
    urgency: 'urgent',
    grantCode: 'NSF-BIO-449102',
    requestedBy: 'Marcus Brody',
    currentStock: 2,
    minThreshold: 6,
    estimatedDelivery: '2026-11-12',
  },
  {
    id: 'po-103',
    poNumber: 'PO-2026-0843',
    reagentName: 'Puromycin Dihydrochloride',
    vendor: 'Sigma-Aldrich',
    catalogNumber: 'P8833-25MG',
    casNumber: '58-58-2',
    quantity: 3,
    unit: '25 mg vial',
    unitPrice: 145.0,
    totalPrice: 435.0,
    status: 'draft',
    urgency: 'routine',
    grantCode: 'AURA-INTERNAL-R&D',
    requestedBy: 'Dr. Sarah Chen',
    currentStock: 4,
    minThreshold: 2,
    estimatedDelivery: '2026-11-15',
  },
  {
    id: 'po-104',
    poNumber: 'PO-2026-0844',
    reagentName: 'Falcon® 96-well Black/Clear Microplates',
    vendor: 'Corning',
    catalogNumber: '353219',
    quantity: 5,
    unit: 'Case of 50',
    unitPrice: 320.0,
    totalPrice: 1600.0,
    status: 'dispatched',
    urgency: 'routine',
    grantCode: 'NIH-R01-HG01124',
    requestedBy: 'Dr. Elena Rostova',
    currentStock: 12,
    minThreshold: 5,
    estimatedDelivery: '2026-11-09',
  },
  {
    id: 'po-105',
    poNumber: 'PO-2026-0845',
    reagentName: 'DNeasy Blood & Tissue Kit (250)',
    vendor: 'Qiagen',
    catalogNumber: '69506',
    quantity: 2,
    unit: 'Kit (250 preps)',
    unitPrice: 610.0,
    totalPrice: 1220.0,
    status: 'received',
    urgency: 'routine',
    grantCode: 'NIH-R01-HG01124',
    requestedBy: 'Dr. Sarah Chen',
    currentStock: 6,
    minThreshold: 2,
    estimatedDelivery: '2026-11-04',
  },
];

export const ProcurementRequisitionModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({
  isOpen,
  onClose,
}) => {
  const [requisitions, setRequisitions] = useState<PurchaseOrderItem[]>(INITIAL_POS);
  const [selectedId, setSelectedId] = useState<string>('po-101');
  const [vendorFilter, setVendorFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showNewModal, setShowNewModal] = useState(false);

  // New item form state
  const [newReagentName, setNewReagentName] = useState('');
  const [newVendor, setNewVendor] = useState<'Sigma-Aldrich' | 'Thermo Fisher' | 'New England Biolabs' | 'Corning' | 'Qiagen'>('Thermo Fisher');
  const [newCatNum, setNewCatNum] = useState('');
  const [newQty, setNewQty] = useState(1);
  const [newPrice, setNewPrice] = useState(150.0);
  const [newGrant, setNewGrant] = useState('NIH-R01-HG01124');

  if (!isOpen) return null;

  const filtered = requisitions.filter((r) => {
    if (vendorFilter !== 'all' && r.vendor !== vendorFilter) return false;
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    return true;
  });

  const selected = requisitions.find((r) => r.id === selectedId) || requisitions[0];

  const handleAuthorize = (id: string) => {
    setRequisitions((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: 'authorized' } : r))
    );
  };

  const handleTransmitEDI = (id: string) => {
    setRequisitions((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: 'dispatched' } : r))
    );
    alert(`cXML Electronic Data Interchange (EDI) PO transmitted directly to ${selected.vendor} ERP.`);
  };

  const handleReceiveStock = (id: string) => {
    setRequisitions((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              status: 'received',
              currentStock: r.currentStock + r.quantity,
            }
          : r
      )
    );
    alert(`Item received! Automatically generated 2D DataMatrix barcodes and registered to Aura Biobank.`);
  };

  const handleCreateRequisition = () => {
    if (!newReagentName) return;
    const newPo: PurchaseOrderItem = {
      id: `po-${Date.now().toString().slice(-4)}`,
      poNumber: `PO-2026-${Math.floor(1000 + Math.random() * 9000)}`,
      reagentName: newReagentName,
      vendor: newVendor,
      catalogNumber: newCatNum || 'CAT-CUSTOM',
      quantity: newQty,
      unit: 'Units',
      unitPrice: newPrice,
      totalPrice: Number((newQty * newPrice).toFixed(2)),
      status: 'pending_pi',
      urgency: 'routine',
      grantCode: newGrant,
      requestedBy: 'Dr. Sarah Chen',
      currentStock: 0,
      minThreshold: 2,
      estimatedDelivery: '2026-11-20',
    };
    setRequisitions([newPo, ...requisitions]);
    setSelectedId(newPo.id);
    setShowNewModal(false);
    setNewReagentName('');
  };

  const totalCommittedSpend = requisitions
    .filter((r) => r.status !== 'received')
    .reduce((acc, r) => acc + r.totalPrice, 0);

  return (
    <div className="modal-backdrop futuristic-backdrop" onClick={onClose}>
      <div
        className="modal-container futuristic-procurement-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '1240px', width: '96vw', maxHeight: '92vh' }}
      >
        {/* Header */}
        <div className="futuristic-modal-header">
          <div className="flex items-center gap-3">
            <div className="futuristic-icon-badge amber-pulse">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="9" cy="21" r="1" />
                <circle cx="20" cy="21" r="1" />
                <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="futuristic-modal-title">Automated Reagent Procurement & PO Requisitions</h2>
                <span className="gxp-pill gxp-certified">cXML / PunchOut EDI</span>
              </div>
              <p className="futuristic-modal-sub">
                Predictive stockout trigger, vendor catalog pricing, multi-grant approval workflow & instant biobank barcode intake.
              </p>
            </div>
          </div>
          <button className="futuristic-close-btn" onClick={onClose} aria-label="Close Procurement Modal">
            ✕
          </button>
        </div>

        {/* Procurement KPI Ribbon */}
        <div className="procur-kpi-ribbon">
          <div className="procur-kpi-card">
            <span className="lbl">COMMITTED PIPELINE SPEND</span>
            <span className="val text-amber">${totalCommittedSpend.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            <span className="sub">Across 4 active grant allocations</span>
          </div>
          <div className="procur-kpi-card">
            <span className="lbl">CRITICAL STOCKOUTS</span>
            <span className="val text-rose">
              {requisitions.filter((r) => r.currentStock < r.minThreshold).length} ITEMS
            </span>
            <span className="sub">Auto-replenishment armed</span>
          </div>
          <div className="procur-kpi-card">
            <span className="lbl">PENDING PI APPROVAL</span>
            <span className="val text-cyan">
              {requisitions.filter((r) => r.status === 'pending_pi').length} ORDERS
            </span>
            <span className="sub">Awaiting budget authorization</span>
          </div>
          <div className="procur-kpi-card">
            <span className="lbl">CONNECTIVITY STATUS</span>
            <span className="val text-emerald">EDI LIVE (5 Vendors)</span>
            <span className="sub">Thermo, Sigma, NEB, Qiagen, Corning</span>
          </div>
        </div>

        {/* Filter & Action Toolbar */}
        <div className="procur-toolbar">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-300">Filter By:</span>
            <select
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              className="futuristic-select-compact"
            >
              <option value="all">All Vendors</option>
              <option value="Sigma-Aldrich">Sigma-Aldrich</option>
              <option value="Thermo Fisher">Thermo Fisher</option>
              <option value="New England Biolabs">New England Biolabs</option>
              <option value="Corning">Corning</option>
              <option value="Qiagen">Qiagen</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="futuristic-select-compact"
            >
              <option value="all">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending_pi">Pending PI</option>
              <option value="authorized">Authorized</option>
              <option value="dispatched">Dispatched</option>
              <option value="received">Received</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button className="procur-btn procur-btn-primary" onClick={() => setShowNewModal(true)}>
              + New Requisition PO
            </button>
          </div>
        </div>

        {/* Master-Detail Split Grid */}
        <div className="procur-grid-container">
          {/* Left: Requisition Order Table */}
          <div className="procur-table-card">
            <div className="cal-table-scroll">
              <table className="procur-table">
                <thead>
                  <tr>
                    <th>PO Number</th>
                    <th>Reagent & Vendor</th>
                    <th>Catalog #</th>
                    <th>Stock / Min</th>
                    <th>Total</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => {
                    const isSelected = item.id === selectedId;
                    const isStockout = item.currentStock < item.minThreshold;
                    const statusBadgeClass =
                      item.status === 'received'
                        ? 'badge-emerald'
                        : item.status === 'authorized'
                        ? 'badge-cyan'
                        : item.status === 'dispatched'
                        ? 'badge-indigo'
                        : item.status === 'pending_pi'
                        ? 'badge-amber'
                        : 'badge-slate';

                    return (
                      <tr
                        key={item.id}
                        className={`procur-tr ${isSelected ? 'active' : ''}`}
                        onClick={() => setSelectedId(item.id)}
                      >
                        <td>
                          <strong>{item.poNumber}</strong>
                          {isStockout && <span className="stockout-dot" title="Stock below minimum threshold!" />}
                        </td>
                        <td>
                          <div className="text-sm font-semibold text-white">{item.reagentName}</div>
                          <div className="text-xs text-slate-400">{item.vendor}</div>
                        </td>
                        <td>
                          <code>{item.catalogNumber}</code>
                        </td>
                        <td>
                          <span className={isStockout ? 'text-rose font-bold' : 'text-slate-300'}>
                            {item.currentStock} / {item.minThreshold}
                          </span>
                        </td>
                        <td>
                          <strong className="text-slate-100">${item.totalPrice.toFixed(2)}</strong>
                        </td>
                        <td>
                          <span className={`status-pill ${statusBadgeClass}`}>
                            {item.status.toUpperCase().replace('_', ' ')}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right: Detailed Requisition Lifecycle & Action Panel */}
          <div className="procur-detail-card">
            <div className="flex justify-between items-start mb-4">
              <div>
                <span className="text-xs font-mono text-cyan">{selected.poNumber}</span>
                <h3 className="text-base font-bold text-white mt-1">{selected.reagentName}</h3>
                <div className="text-xs text-slate-400 mt-0.5">
                  Supplier: <strong>{selected.vendor}</strong> | Cat#: <strong>{selected.catalogNumber}</strong>
                </div>
              </div>
              <span className={`status-pill ${selected.status === 'received' ? 'badge-emerald' : 'badge-amber'}`}>
                {selected.status.toUpperCase().replace('_', ' ')}
              </span>
            </div>

            {/* Stepper Progress Bar */}
            <div className="po-lifecycle-stepper">
              {['draft', 'pending_pi', 'authorized', 'dispatched', 'received'].map((step, idx) => {
                const stepOrder = ['draft', 'pending_pi', 'authorized', 'dispatched', 'received'];
                const currentIdx = stepOrder.indexOf(selected.status);
                const isPassed = idx <= currentIdx;
                const isCurrent = idx === currentIdx;

                return (
                  <div key={step} className={`step-node ${isPassed ? 'completed' : ''} ${isCurrent ? 'current' : ''}`}>
                    <div className="step-circle">{isPassed ? '✓' : idx + 1}</div>
                    <span className="step-label">{step.replace('_', ' ').toUpperCase()}</span>
                  </div>
                );
              })}
            </div>

            {/* Details Specification Grid */}
            <div className="procur-spec-grid">
              <div className="spec-box">
                <span className="lbl">ORDER QUANTITY</span>
                <span className="val">{selected.quantity} × {selected.unit}</span>
              </div>
              <div className="spec-box">
                <span className="lbl">UNIT PRICE</span>
                <span className="val">${selected.unitPrice.toFixed(2)}</span>
              </div>
              <div className="spec-box">
                <span className="lbl">COMMITTED BUDGET</span>
                <span className="val text-amber font-bold">${selected.totalPrice.toFixed(2)}</span>
              </div>
              <div className="spec-box">
                <span className="lbl">GRANT / COST CENTER</span>
                <span className="val text-cyan font-mono">{selected.grantCode}</span>
              </div>
              <div className="spec-box">
                <span className="lbl">REQUESTED BY</span>
                <span className="val">{selected.requestedBy}</span>
              </div>
              <div className="spec-box">
                <span className="lbl">ESTIMATED ARRIVAL</span>
                <span className="val text-emerald">{selected.estimatedDelivery}</span>
              </div>
            </div>

            {/* Live Actions depending on current lifecycle stage */}
            <div className="procur-action-footer">
              {selected.status === 'pending_pi' && (
                <button
                  className="procur-btn procur-btn-primary w-full"
                  onClick={() => handleAuthorize(selected.id)}
                >
                  ✍️ PI Electronic Signature & Authorize Budget
                </button>
              )}

              {selected.status === 'authorized' && (
                <button
                  className="procur-btn procur-btn-accent w-full"
                  onClick={() => handleTransmitEDI(selected.id)}
                >
                  🚀 Transmit PO to {selected.vendor} via cXML EDI
                </button>
              )}

              {selected.status === 'dispatched' && (
                <button
                  className="procur-btn procur-btn-emerald w-full"
                  onClick={() => handleReceiveStock(selected.id)}
                >
                  📦 Confirm Receipt & Register Biobank Barcodes
                </button>
              )}

              {selected.status === 'received' && (
                <div className="text-center p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-lg text-emerald-300 text-xs">
                  ✓ Reagent in Biobank stock. Barcode labels dispatched to Zebra thermal printer.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* New Requisition Modal Dialog */}
        {showNewModal && (
          <div className="sub-modal-backdrop" onClick={() => setShowNewModal(false)}>
            <div className="sub-modal-card" onClick={(e) => e.stopPropagation()}>
              <h4 className="text-base font-bold text-white mb-2">Create New Laboratory Requisition</h4>
              <p className="text-xs text-slate-400 mb-4">
                Enter vendor catalog details to trigger automated PO generation and grant deduction.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-slate-300 block mb-1">Reagent / Consumable Name</label>
                  <input
                    type="text"
                    className="futuristic-input w-full"
                    placeholder="e.g. Lipofectamine™ 3000 Transfection Reagent"
                    value={newReagentName}
                    onChange={(e) => setNewReagentName(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Vendor Partner</label>
                    <select
                      className="futuristic-input w-full"
                      value={newVendor}
                      onChange={(e) => setNewVendor(e.target.value as any)}
                    >
                      <option value="Thermo Fisher">Thermo Fisher</option>
                      <option value="Sigma-Aldrich">Sigma-Aldrich</option>
                      <option value="New England Biolabs">New England Biolabs</option>
                      <option value="Corning">Corning</option>
                      <option value="Qiagen">Qiagen</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Catalog Number</label>
                    <input
                      type="text"
                      className="futuristic-input w-full"
                      placeholder="e.g. L3000015"
                      value={newCatNum}
                      onChange={(e) => setNewCatNum(e.target.value)}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Quantity</label>
                    <input
                      type="number"
                      min="1"
                      className="futuristic-input w-full"
                      value={newQty}
                      onChange={(e) => setNewQty(parseInt(e.target.value) || 1)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Unit Price ($)</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className="futuristic-input w-full"
                      value={newPrice}
                      onChange={(e) => setNewPrice(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-300 block mb-1">Grant Allocation</label>
                    <select
                      className="futuristic-input w-full"
                      value={newGrant}
                      onChange={(e) => setNewGrant(e.target.value)}
                    >
                      <option value="NIH-R01-HG01124">NIH-R01-HG01124</option>
                      <option value="NSF-BIO-449102">NSF-BIO-449102</option>
                      <option value="AURA-INTERNAL-R&D">AURA-INTERNAL-R&D</option>
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-3">
                  <button className="cal-btn-ghost" onClick={() => setShowNewModal(false)}>
                    Cancel
                  </button>
                  <button className="procur-btn procur-btn-primary" onClick={handleCreateRequisition}>
                    Submit Requisition
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

