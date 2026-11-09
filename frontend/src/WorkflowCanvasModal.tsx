import { useState, useEffect } from "react";
import {
  canvasApi,
  WorkflowCanvasItem,
  CanvasNode,
  CanvasEdge,
  CanvasRunItem,
} from "./api";

interface WorkflowCanvasModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedProjectId?: number | null;
  selectedExperimentId?: number | null;
  onInsertIntoNotebook?: (markdown: string) => void;
}

const NODE_COLORS: Record<string, { bg: string; border: string; icon: string }> = {
  prep: { bg: "rgba(59, 130, 246, 0.15)", border: "#3b82f6", icon: "🧪" },
  pipette: { bg: "rgba(16, 185, 129, 0.15)", border: "#10b981", icon: "💧" },
  incubate: { bg: "rgba(245, 158, 11, 0.15)", border: "#f59e0b", icon: "🌡️" },
  wash: { bg: "rgba(6, 182, 212, 0.15)", border: "#06b6d4", icon: "🚿" },
  read: { bg: "rgba(168, 85, 247, 0.15)", border: "#a855f7", icon: "🔬" },
  qc: { bg: "rgba(239, 68, 68, 0.15)", border: "#ef4444", icon: "⚖️" },
};

export function WorkflowCanvasModal({
  isOpen,
  onClose,
  selectedProjectId,
  selectedExperimentId,
  onInsertIntoNotebook,
}: WorkflowCanvasModalProps) {
  const [canvases, setCanvases] = useState<WorkflowCanvasItem[]>([]);
  const [activeCanvas, setActiveCanvas] = useState<WorkflowCanvasItem | null>(null);
  const [canvasName, setCanvasName] = useState<string>("Standard Protocol DAG");
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [edges, setEdges] = useState<CanvasEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<CanvasRunItem | null>(null);
  const [templates, setTemplates] = useState<{ name: string; description: string; nodes: CanvasNode[]; edges: CanvasEdge[] }[]>([]);
  const [validation, setValidation] = useState<{ is_valid: boolean; has_cycle: boolean; topological_order: string[]; error?: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    loadTemplatesAndCanvases();
  }, [isOpen]);

  async function loadTemplatesAndCanvases() {
    try {
      const [tpls, list] = await Promise.all([
        canvasApi.getTemplates(),
        canvasApi.list(selectedProjectId, selectedExperimentId),
      ]);
      setTemplates(tpls);
      setCanvases(list);
      if (list.length > 0) {
        selectCanvas(list[0]);
      } else if (tpls.length > 0) {
        applyTemplate(tpls[0]);
      }
    } catch (err) {
      console.error("Failed to load workflow canvases", err);
    }
  }

  function applyTemplate(tpl: { name: string; nodes: CanvasNode[]; edges: CanvasEdge[] }) {
    setCanvasName(tpl.name);
    setNodes(tpl.nodes);
    setEdges(tpl.edges);
    setActiveCanvas(null);
    setActiveRun(null);
    void validateWorkflow(tpl.nodes, tpl.edges);
  }

  function selectCanvas(c: WorkflowCanvasItem) {
    setActiveCanvas(c);
    setCanvasName(c.name);
    setNodes(c.nodes || []);
    setEdges(c.edges || []);
    setActiveRun(null);
    void validateWorkflow(c.nodes || [], c.edges || []);
    void loadRuns(c.id);
  }

  async function loadRuns(canvasId: number) {
    try {
      const runs = await canvasApi.listRuns(canvasId);
      if (runs.length > 0) setActiveRun(runs[0]);
    } catch (err) {
      console.error("Failed to load runs", err);
    }
  }

  async function validateWorkflow(nList: CanvasNode[], eList: CanvasEdge[]) {
    try {
      const res = await canvasApi.validateDag(nList, eList);
      setValidation(res);
      if (!res.is_valid) {
        setError(res.error || "Cycle detected in DAG!");
      } else {
        setError(null);
      }
    } catch (err: any) {
      setError(err?.message || "Validation failed.");
    }
  }

  async function handleSaveCanvas() {
    setLoading(true);
    try {
      if (activeCanvas) {
        const updated = await canvasApi.update(activeCanvas.id, {
          name: canvasName,
          nodes,
          edges,
        });
        setActiveCanvas(updated);
        setNotice(`Saved "${canvasName}"!`);
      } else {
        const created = await canvasApi.create({
          name: canvasName,
          nodes,
          edges,
          project_id: selectedProjectId,
          experiment_id: selectedExperimentId,
        });
        setActiveCanvas(created);
        setCanvases((prev) => [created, ...prev]);
        setNotice(`Created new workflow canvas "${canvasName}"!`);
      }
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Failed to save workflow.");
    } finally {
      setLoading(false);
    }
  }

  async function handleStartExecution() {
    if (!activeCanvas) {
      await handleSaveCanvas();
    }
    if (!activeCanvas?.id) return;
    setLoading(true);
    try {
      const run = await canvasApi.startRun(activeCanvas.id);
      setActiveRun(run);
      setNotice(`Started execution run #${run.id}!`);
      setTimeout(() => setNotice(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Failed to start execution.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCompleteStep(nodeId: string) {
    if (!activeRun) return;
    try {
      const updatedRun = await canvasApi.stepRun(activeRun.id, nodeId);
      setActiveRun(updatedRun);
      if (updatedRun.status === "completed") {
        setNotice("🎉 Entire workflow execution completed successfully!");
      }
    } catch (err: any) {
      setError(err?.message || "Step completion failed.");
    }
  }

  function addNode(type: CanvasNode["type"]) {
    const newId = `node-${Date.now().toString().slice(-4)}`;
    const newNode: CanvasNode = {
      id: newId,
      label: `New ${type.toUpperCase()} Step`,
      type,
      duration_min: 15,
      x: 100 + (nodes.length % 5) * 160,
      y: 100 + Math.floor(nodes.length / 5) * 140,
    };
    const updated = [...nodes, newNode];
    setNodes(updated);
    void validateWorkflow(updated, edges);
  }

  function handleInsertMarkdown() {
    if (!onInsertIntoNotebook) return;
    const orderStr = validation?.topological_order?.join(" → ") || "Sequential";
    const md = `
### 🕸️ Workflow Canvas Protocol: ${canvasName}
- **Total Steps:** ${nodes.length} nodes, ${edges.length} dependencies
- **Topological Order:** ${orderStr}
- **Estimated Total Duration:** ${nodes.reduce((acc, n) => acc + (n.duration_min || 0), 0)} minutes
- **Status:** ${activeRun ? `Run #${activeRun.id} (${activeRun.status})` : "Configured"}
`;
    onInsertIntoNotebook(md);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content canvas-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge-cyan">WORKFLOW CANVAS DAG SUITE</span>
            <h2>Scientific Protocol Execution Graph & Automated Runner</h2>
          </div>
          <button className="button-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        {/* Toolbar */}
        <div className="canvas-toolbar-row">
          <div className="canvas-title-group">
            <input
              type="text"
              className="input-text canvas-name-input"
              value={canvasName}
              onChange={(e) => setCanvasName(e.target.value)}
              placeholder="Workflow Protocol Name"
            />
            {validation && (
              <span className={`badge-tag ${validation.is_valid ? "tag-pass" : "tag-fail"}`}>
                {validation.is_valid ? "✓ Valid DAG (Acyclic)" : "✕ Deadlock / Cycle"}
              </span>
            )}
          </div>

          <div className="canvas-actions-group">
            {canvases.length > 0 && (
              <select
                className="input-text"
                style={{ fontSize: 11, padding: "4px 8px" }}
                value={activeCanvas?.id || ""}
                onChange={(e) => {
                  const found = canvases.find((c) => c.id === Number(e.target.value));
                  if (found) selectCanvas(found);
                }}
              >
                <option value="">-- Load Saved ({canvases.length}) --</option>
                {canvases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}

            <div className="preset-pill-list">
              <span className="text-muted" style={{ fontSize: 11, alignSelf: "center" }}>Templates:</span>
              {templates.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  className="preset-pill"
                  onClick={() => applyTemplate(t)}
                >
                  {t.name.split(" ")[0]}
                </button>
              ))}
            </div>

            <button
              className="button button-secondary"
              onClick={handleSaveCanvas}
              disabled={loading}
            >
              💾 Save
            </button>

            <button
              className="button button-primary"
              onClick={handleStartExecution}
              disabled={loading || !validation?.is_valid}
            >
              ▶️ {activeRun && activeRun.status === "running" ? "Resume Run" : "Start Run"}
            </button>

            {onInsertIntoNotebook && (
              <button
                className="button button-outline"
                onClick={handleInsertMarkdown}
              >
                📝 Insert in Notebook
              </button>
            )}
          </div>
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {notice && <div className="callout callout-success">{notice}</div>}

        {/* Main Canvas Work Area */}
        <div className="canvas-body-grid">
          {/* Node palette */}
          <aside className="canvas-palette">
            <h4>Add Protocol Step</h4>
            <div className="palette-buttons">
              <button className="button-palette" onClick={() => addNode("prep")}>
                <span>🧪</span> Prep Reagent
              </button>
              <button className="button-palette" onClick={() => addNode("pipette")}>
                <span>💧</span> Pipette / Dispense
              </button>
              <button className="button-palette" onClick={() => addNode("incubate")}>
                <span>🌡️</span> Incubate / Heat
              </button>
              <button className="button-palette" onClick={() => addNode("wash")}>
                <span>🚿</span> Microplate Wash
              </button>
              <button className="button-palette" onClick={() => addNode("read")}>
                <span>🔬</span> Instrument Read
              </button>
              <button className="button-palette" onClick={() => addNode("qc")}>
                <span>⚖️</span> QC Validation Gate
              </button>
            </div>

            {/* Run Execution Monitor */}
            {activeRun && (
              <div className="run-inspector-card">
                <h4>Execution Run #{activeRun.id}</h4>
                <div className="prop-stat">
                  <span className="stat-label">Status</span>
                  <span className="stat-value capitalize highlight-cyan">{activeRun.status}</span>
                </div>
                <div className="run-log-box">
                  {activeRun.logs.slice(-6).map((log, i) => (
                    <div key={i} className="run-log-line">› {log}</div>
                  ))}
                </div>
              </div>
            )}
          </aside>

          {/* Interactive DAG Graph Area */}
          <div className="canvas-graph-viewport">
            <svg className="dag-svg-canvas" width="100%" height="100%">
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="10"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#00f2fe" />
                </marker>
              </defs>

              {/* Draw Edges */}
              {edges.map((e) => {
                const srcNode = nodes.find((n) => n.id === e.source);
                const tgtNode = nodes.find((n) => n.id === e.target);
                if (!srcNode || !tgtNode) return null;
                const x1 = srcNode.x + 80;
                const y1 = srcNode.y + 35;
                const x2 = tgtNode.x;
                const y2 = tgtNode.y + 35;
                return (
                  <g key={e.id}>
                    <path
                      d={`M ${x1} ${y1} C ${x1 + 60} ${y1}, ${x2 - 60} ${y2}, ${x2} ${y2}`}
                      stroke="#00f2fe"
                      strokeWidth="2.5"
                      fill="none"
                      markerEnd="url(#arrow)"
                    />
                  </g>
                );
              })}
            </svg>

            {/* HTML Node cards layered on top */}
            <div className="dag-nodes-layer">
              {nodes.map((node) => {
                const style = NODE_COLORS[node.type] || NODE_COLORS.prep;
                const runState = activeRun?.node_states[node.id];
                const isReady = runState === "ready";
                const isCompleted = runState === "completed";

                return (
                  <div
                    key={node.id}
                    className={`dag-node-card ${selectedNodeId === node.id ? "selected" : ""} ${
                      isCompleted ? "node-completed" : isReady ? "node-ready" : ""
                    }`}
                    style={{
                      left: node.x,
                      top: node.y,
                      backgroundColor: style.bg,
                      borderColor: isCompleted ? "#10b981" : isReady ? "#00f2fe" : style.border,
                    }}
                    onClick={() => setSelectedNodeId(node.id)}
                  >
                    <div className="node-card-header">
                      <span className="node-icon">{style.icon}</span>
                      <span className="node-type-label">{node.type}</span>
                      {isCompleted && <span className="node-check">✓</span>}
                    </div>
                    <div className="node-title">{node.label}</div>
                    <div className="node-duration font-mono">{node.duration_min} min</div>

                    {activeRun && isReady && (
                      <button
                        className="button button-primary button-xs"
                        style={{ marginTop: 6 }}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleCompleteStep(node.id);
                        }}
                      >
                        ✓ Mark Done
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
