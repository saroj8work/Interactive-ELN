with open("frontend/src/styles.css", "a", encoding="utf-8") as f:
    f.write('''

/* ==========================================================================
   PHASE 1: 96-WELL & 384-WELL MICROPLATE & ASSAY ANALYSIS STYLES
   ========================================================================== */

.microplate-modal-card {
  width: 95vw;
  max-width: 1400px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: var(--bg-card, #ffffff);
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
}

.microplate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--line, #e2e8f0);
  background: var(--bg-panel, #f8fafc);
}

.microplate-header .badge-core {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #06b6d4;
  background: rgba(6, 182, 212, 0.12);
  padding: 3px 8px;
  border-radius: 6px;
  display: inline-block;
  margin-bottom: 4px;
}

.microplate-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: var(--text-heading, #0f172a);
}

.microplate-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 24px;
  background: var(--bg-subtle, #f1f5f9);
  border-bottom: 1px solid var(--line, #e2e8f0);
}

.plate-select-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.plate-select-group select {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--line, #cbd5e1);
  background: var(--bg-card, #fff);
  font-weight: 600;
  color: var(--text-body, #1e293b);
}

.view-mode-toggle {
  display: flex;
  gap: 6px;
}

.csv-upload-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.csv-label {
  cursor: pointer;
}

.create-plate-dialog {
  padding: 16px 24px;
  background: rgba(6, 182, 212, 0.06);
  border-bottom: 1px solid #06b6d4;
}

.create-plate-dialog .form-row {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.create-plate-dialog label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  flex: 1;
}

.microplate-body {
  display: grid;
  grid-template-columns: 1fr 340px;
  flex: 1;
  overflow: hidden;
}

.plate-grid-container {
  padding: 20px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.microplate-table-wrapper {
  background: var(--bg-card, #ffffff);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--line, #e2e8f0);
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.05);
}

.microplate-table {
  border-collapse: separate;
  border-spacing: 6px;
}

.col-header-th, .row-header-th {
  padding: 4px;
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted, #64748b);
  cursor: pointer;
  user-select: none;
  text-align: center;
}

.col-header-th:hover, .row-header-th:hover {
  color: #06b6d4;
}

.well-td {
  width: 48px;
  height: 48px;
  padding: 0;
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  text-align: center;
  vertical-align: middle;
  border: 2px solid transparent;
}

.microplate-table-wrapper.384-well .well-td {
  width: 24px;
  height: 24px;
  border-spacing: 2px;
}

.well-td:hover {
  transform: scale(1.12);
  z-index: 2;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.well-td.selected-well {
  border-color: #00f2fe;
  box-shadow: 0 0 12px #00f2fe;
  transform: scale(1.1);
}

.well-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.well-coord-text {
  font-size: 9px;
  font-weight: 800;
  line-height: 1;
}

.well-value-text {
  font-size: 10px;
  line-height: 1.1;
}

.well-role-badge {
  font-size: 8px;
  font-weight: 700;
  text-transform: uppercase;
  max-width: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Inspector Drawer */
.microplate-inspector {
  padding: 20px;
  background: var(--bg-panel, #f8fafc);
  border-left: 1px solid var(--line, #e2e8f0);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.inspector-card {
  background: var(--bg-card, #fff);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--line, #e2e8f0);
}

.inspector-card h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 800;
  color: var(--text-heading, #0f172a);
}

.role-selector-radios {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0;
}

.role-radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.role-chip-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.standard-conc-input {
  margin-bottom: 12px;
}

.standard-conc-input input {
  width: 100%;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--line, #cbd5e1);
  margin-top: 4px;
}

.telemetry-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  font-size: 11px;
}

.heatmap-gradient-legend {
  margin: 10px 0;
}

.heatmap-gradient-legend .gradient-bar {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, #00f2fe 0%, #f59e0b 50%, #ef4444 100%);
  margin: 4px 0;
}

.legend-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted, #64748b);
  display: flex;
  justify-content: space-between;
}

.legend-caption {
  font-size: 11px;
  color: var(--text-muted, #64748b);
  margin: 0;
  line-height: 1.4;
}
''')

print("Added microplate CSS styles.")

