path = "frontend/src/styles.css"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

ux_enhancements_css = """
/* ==========================================================================
   Aura Lab UX Enhancements: Autocomplete, Autosave, Themes & Bench Mode
   ========================================================================== */

/* Mention Autocomplete Popover */
.mention-popover {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.18);
  width: 320px;
  max-height: 280px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.mention-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px;
  font-weight: 700;
  color: #334155;
}
.mention-hint {
  font-size: 9px;
  color: #94a3b8;
  font-weight: 500;
}
.mention-list {
  list-style: none;
  padding: 4px 0;
  margin: 0;
  overflow-y: auto;
  max-height: 240px;
}
.mention-item {
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.12s;
}
.mention-item:hover, .mention-item.selected {
  background: #f1f5f9;
}
.mention-item-name {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}
.mention-item-detail {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}

/* Autosave Status Pill */
.autosave-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}
.autosave-pill.status-saved {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.35);
  color: #059669;
}
.autosave-pill.status-saving {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.35);
  color: #2563eb;
}
.autosave-pill.status-unsaved {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.35);
  color: #d97706;
}
.autosave-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
}

/* Collapsible Navigation Sidebar */
.sidebar {
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.sidebar.collapsed {
  width: 64px !important;
  min-width: 64px !important;
  padding: 12px 8px;
}
.sidebar.collapsed .brand div,
.sidebar.collapsed .workspace-label,
.sidebar.collapsed .sidebar-heading,
.sidebar.collapsed .project-tree,
.sidebar.collapsed .sidebar-form,
.sidebar.collapsed .sidebar-footer span:not(.avatar) {
  display: none !important;
}
.sidebar.collapsed .brand-mark {
  margin: 0 auto 12px;
  width: 44px;
  height: 44px;
}
.sidebar.collapsed .sidebar-footer {
  justify-content: center;
  padding: 0;
}
.sidebar-collapse-btn {
  background: transparent;
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}
.sidebar-collapse-btn:hover {
  background: rgba(139, 92, 246, 0.15);
  color: #00f0d0;
}

/* Interior Dark Theme Support */
[data-theme="dark"] .app-shell {
  background: #0c0b16;
  color: #e2e8f0;
}
[data-theme="dark"] .sidebar {
  background: #110e20;
  border-right-color: rgba(139, 92, 246, 0.18);
  color: #cbd5e1;
}
[data-theme="dark"] .brand strong {
  color: #fff;
}
[data-theme="dark"] .brand span {
  color: #00f0d0;
}
[data-theme="dark"] .top-bar {
  background: rgba(17, 14, 32, 0.95);
  border-bottom-color: rgba(139, 92, 246, 0.18);
}
[data-theme="dark"] .main-panel {
  background: #0c0b16;
}
[data-theme="dark"] .content-grid {
  background: #0c0b16;
}
[data-theme="dark"] .entry-list-column,
[data-theme="dark"] .editor-column,
[data-theme="dark"] .activity-column {
  background: #131024;
  border-color: rgba(139, 92, 246, 0.18);
}
[data-theme="dark"] .entry-card {
  background: #18142e;
  border-color: rgba(139, 92, 246, 0.22);
  color: #e2e8f0;
}
[data-theme="dark"] .entry-card:hover {
  border-color: #00f0d0;
}
[data-theme="dark"] .entry-card.active {
  background: #201a3d;
  border-color: #00f0d0;
}
[data-theme="dark"] .entry-card strong {
  color: #f8fafc;
}
[data-theme="dark"] .entry-card p {
  color: #94a3b8;
}
[data-theme="dark"] .editor-card {
  background: #17132b;
  border-color: rgba(139, 92, 246, 0.22);
}
[data-theme="dark"] .editor-card input,
[data-theme="dark"] .editor-card textarea {
  background: #0f0c1d;
  border-color: rgba(139, 92, 246, 0.28);
  color: #f1f5f9;
}
[data-theme="dark"] .editor-card input:focus,
[data-theme="dark"] .editor-card textarea:focus {
  border-color: #00f0d0;
  box-shadow: 0 0 0 3px rgba(0, 240, 208, 0.2);
}
[data-theme="dark"] .admin-panel,
[data-theme="dark"] .inventory-panel,
[data-theme="dark"] .templates-panel,
[data-theme="dark"] .history-panel {
  background: #16122a;
  border-color: rgba(139, 92, 246, 0.3);
  color: #e2e8f0;
  box-shadow: 0 20px 50px rgba(0,0,0,0.6);
}
[data-theme="dark"] .mention-popover {
  background: #191530;
  border-color: rgba(139, 92, 246, 0.35);
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
}
[data-theme="dark"] .mention-popover-header {
  background: #120e24;
  border-bottom-color: rgba(139, 92, 246, 0.25);
  color: #00f0d0;
}
[data-theme="dark"] .mention-item-name {
  color: #f8fafc;
}
[data-theme="dark"] .mention-item:hover,
[data-theme="dark"] .mention-item.selected {
  background: #251e47;
}
[data-theme="dark"] .button-outline {
  border-color: rgba(139, 92, 246, 0.35);
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.04);
}
[data-theme="dark"] .button-outline:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: #00f0d0;
  color: #fff;
}
[data-theme="dark"] .status-chip {
  background: #211b3d;
  color: #c4b5fd;
}
[data-theme="dark"] .autosave-pill.status-saved {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
}
[data-theme="dark"] .autosave-pill.status-unsaved {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}
[data-theme="dark"] .autosave-pill.status-saving {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

/* Bench Mode Glove-Friendly Styling */
[data-bench-mode="true"] {
  font-size: 15px;
}
[data-bench-mode="true"] .button {
  min-height: 48px !important;
  padding: 12px 20px !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  border-width: 2px !important;
  border-radius: 9px !important;
}
[data-bench-mode="true"] input,
[data-bench-mode="true"] select {
  min-height: 48px !important;
  font-size: 14px !important;
  padding: 10px 14px !important;
}
[data-bench-mode="true"] textarea {
  font-size: 15px !important;
  line-height: 1.7 !important;
}
[data-bench-mode="true"] input[type="checkbox"] {
  width: 22px !important;
  height: 22px !important;
  margin: 6px !important;
  cursor: pointer;
}
[data-bench-mode="true"] .entry-card {
  padding: 18px !important;
}
[data-bench-mode="true"] .entry-card strong {
  font-size: 16px !important;
}
[data-bench-mode="true"] .autosave-pill {
  padding: 6px 14px !important;
  font-size: 13px !important;
}
[data-bench-mode="true"] .bench-mode-active {
  background: #00f0d0 !important;
  color: #0b0915 !important;
  border-color: #00f0d0 !important;
  box-shadow: 0 0 12px rgba(0, 240, 208, 0.45) !important;
}
"""

norm_text += ux_enhancements_css

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully appended UX enhancements styles to styles.css!")

