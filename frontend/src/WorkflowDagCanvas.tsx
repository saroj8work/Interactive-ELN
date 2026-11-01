import { useState, useMemo } from "react";
import type { LabTask } from "./types";
import type { OrganizationUser } from "./api";

interface WorkflowDagCanvasProps {
  tasks: LabTask[];
  organizationUsers?: OrganizationUser[];
  onUpdateTaskStatus?: (taskId: number, status: LabTask["status"]) => Promise<void>;
  onAddTaskDependency?: (taskId: number, dependsOnTaskId: number) => Promise<void>;
  disabled?: boolean;
}

interface DagNode {
  task: LabTask;
  tier: number;
  x: number;
  y: number;
  dependencies: number[];
}

// Helper to extract dependencies from task description e.g. [depends_on: 1, 2]
function parseTaskDependencies(task: LabTask): number[] {
  const match = task.description.match(/\[depends_on:\s*([0-9,\s]+)\]/i);
  if (!match) return [];
  return match[1]
    .split(",")
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => !isNaN(n));
}

function getStatusColor(status: LabTask["status"]): { bg: string; border: string; text: string } {
  switch (status) {
    case "completed":
      return { bg: "#ecfdf5", border: "#10b981", text: "#059669" };
    case "in_progress":
      return { bg: "#eff6ff", border: "#3b82f6", text: "#1d4ed8" };
    case "blocked":
      return { bg: "#fef2f2", border: "#ef4444", text: "#b91c1c" };
    case "cancelled":
      return { bg: "#f1f5f9", border: "#94a3b8", text: "#64748b" };
    default:
      return { bg: "#fefce8", border: "#f59e0b", text: "#b45309" };
  }
}

export function WorkflowDagCanvas({
  tasks,
  organizationUsers = [],
  onUpdateTaskStatus,
  onAddTaskDependency,
  disabled = false,
}: WorkflowDagCanvasProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [targetDepId, setTargetDepId] = useState<number | "">("");
  const [isUpdating, setIsUpdating] = useState(false);

  // Compute DAG topological layout
  const { nodes, edges, canvasWidth, canvasHeight } = useMemo(() => {
    const taskMap = new Map<number, LabTask>();
    tasks.forEach((t) => taskMap.set(t.id, t));

    // Map of taskId -> dependencies
    const depMap = new Map<number, number[]>();
    tasks.forEach((t) => {
      const deps = parseTaskDependencies(t).filter((id) => taskMap.has(id));
      depMap.set(t.id, deps);
    });

    // Compute topological tiers
    const tiers = new Map<number, number>();
    function getTier(id: number, visited = new Set<number>()): number {
      if (tiers.has(id)) return tiers.get(id)!;
      if (visited.has(id)) return 0; // Prevent cycle lock
      visited.add(id);

      const deps = depMap.get(id) || [];
      if (deps.length === 0) {
        tiers.set(id, 0);
        return 0;
      }

      let maxDepTier = -1;
      for (const d of deps) {
        maxDepTier = Math.max(maxDepTier, getTier(d, new Set(visited)));
      }
      const myTier = maxDepTier + 1;
      tiers.set(id, myTier);
      return myTier;
    }

    tasks.forEach((t) => getTier(t.id));

    // Group tasks by tier
    const tierGroups = new Map<number, LabTask[]>();
    tasks.forEach((t) => {
      const tier = tiers.get(t.id) || 0;
      if (!tierGroups.has(tier)) tierGroups.set(tier, []);
      tierGroups.get(tier)!.push(t);
    });

    // Node layout constants
    const nodeWidth = 200;
    const nodeHeight = 85;
    const tierSpacingX = 280;
    const nodeSpacingY = 120;
    const paddingX = 40;
    const paddingY = 40;

    const dagNodes: DagNode[] = [];
    const nodeCoords = new Map<number, { x: number; y: number }>();

    let maxTier = 0;
    let maxRows = 1;

    tierGroups.forEach((group, tier) => {
      maxTier = Math.max(maxTier, tier);
      maxRows = Math.max(maxRows, group.length);
      group.forEach((task, index) => {
        const x = paddingX + tier * tierSpacingX;
        const y = paddingY + index * nodeSpacingY;
        const deps = depMap.get(task.id) || [];
        dagNodes.push({ task, tier, x, y, dependencies: deps });
        nodeCoords.set(task.id, { x, y });
      });
    });

    // Generate edge curves
    const dagEdges: { fromId: number; toId: number; path: string }[] = [];
    dagNodes.forEach((node) => {
      node.dependencies.forEach((depId) => {
        const sourceCoord = nodeCoords.get(depId);
        if (sourceCoord) {
          const x1 = sourceCoord.x + nodeWidth;
          const y1 = sourceCoord.y + nodeHeight / 2;
          const x2 = node.x;
          const y2 = node.y + nodeHeight / 2;
          const dx = (x2 - x1) / 2;
          const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
          dagEdges.push({ fromId: depId, toId: node.task.id, path });
        }
      });
    });

    const width = Math.max(750, paddingX * 2 + (maxTier + 1) * tierSpacingX);
    const height = Math.max(450, paddingY * 2 + maxRows * nodeSpacingY);

    return { nodes: dagNodes, edges: dagEdges, canvasWidth: width, canvasHeight: height };
  }, [tasks]);

  const selectedNode = selectedTaskId ? nodes.find((n) => n.task.id === selectedTaskId) ?? null : null;
  const userMap = useMemo(() => {
    const map = new Map<number, string>();
    organizationUsers.forEach((u) => map.set(u.id, u.display_name));
    return map;
  }, [organizationUsers]);

  async function handleStatusChange(newStatus: LabTask["status"]) {
    if (!selectedTaskId || !onUpdateTaskStatus) return;
    try {
      setIsUpdating(true);
      await onUpdateTaskStatus(selectedTaskId, newStatus);
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleAddDependency() {
    if (!selectedTaskId || !targetDepId || !onAddTaskDependency) return;
    try {
      setIsUpdating(true);
      await onAddTaskDependency(selectedTaskId, Number(targetDepId));
      setTargetDepId("");
    } finally {
      setIsUpdating(false);
    }
  }

  return (
    <div className="workflow-dag-container" style={{ background: "#ffffff", borderRadius: "8px", border: "1px solid #cbd5e1", padding: "1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div>
          <h4 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span>🕸️</span> Visual Task DAG & Workflow Dependency Canvas
          </h4>
          <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
            SciNote-compatible directed acyclic graph connecting project tasks and prerequisite execution milestones.
          </span>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.8rem", color: "#64748b", alignSelf: "center" }}>
            {tasks.length} total tasks | {edges.length} dependency paths
          </span>
        </div>
      </div>

      <div style={{ display: "flex", gap: "1.25rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        {/* SVG Flowchart Canvas */}
        <div
          style={{
            flex: "1 1 650px",
            overflowX: "auto",
            background: "#f8fafc",
            borderRadius: "6px",
            border: "1px solid #e2e8f0",
            minHeight: "420px",
            position: "relative",
          }}
        >
          <svg width={canvasWidth} height={canvasHeight} style={{ display: "block" }}>
            <defs>
              <marker
                id="dag-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
              </marker>
            </defs>

            {/* Connecting Dependency Arrows */}
            {edges.map((edge) => (
              <path
                key={`${edge.fromId}->${edge.toId}`}
                d={edge.path}
                fill="none"
                stroke="#64748b"
                strokeWidth="2"
                strokeDasharray={edge.fromId === selectedTaskId || edge.toId === selectedTaskId ? "none" : "none"}
                markerEnd="url(#dag-arrow)"
                style={{
                  transition: "stroke 0.2s, stroke-width 0.2s",
                  stroke: edge.fromId === selectedTaskId || edge.toId === selectedTaskId ? "#2563eb" : "#94a3b8",
                  strokeWidth: edge.fromId === selectedTaskId || edge.toId === selectedTaskId ? 3 : 2,
                }}
              />
            ))}

            {/* Task Nodes */}
            {nodes.map((node) => {
              const { task, x, y } = node;
              const isSelected = selectedTaskId === task.id;
              const colors = getStatusColor(task.status);
              const assigneeName = task.assigned_to_user_id ? userMap.get(task.assigned_to_user_id) || `User #${task.assigned_to_user_id}` : "Unassigned";

              return (
                <g
                  key={task.id}
                  transform={`translate(${x}, ${y})`}
                  onClick={() => setSelectedTaskId(task.id)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Node Background Box */}
                  <rect
                    width="200"
                    height="85"
                    rx="6"
                    fill={colors.bg}
                    stroke={isSelected ? "#2563eb" : colors.border}
                    strokeWidth={isSelected ? "3" : "1.5"}
                    style={{
                      filter: isSelected
                        ? "drop-shadow(0 4px 6px rgba(37, 99, 235, 0.25))"
                        : "drop-shadow(0 1px 2px rgba(0,0,0,0.06))",
                      transition: "all 0.15s ease",
                    }}
                  />

                  {/* Status Badge */}
                  <rect x="12" y="10" width="75" height="18" rx="3" fill={colors.border} />
                  <text
                    x="50"
                    y="22"
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="9.5"
                    fontWeight="700"
                    fontFamily="sans-serif"
                    style={{ textTransform: "uppercase" }}
                  >
                    {task.status}
                  </text>

                  {/* Priority indicator */}
                  {task.priority !== "normal" && (
                    <text
                      x="185"
                      y="22"
                      textAnchor="end"
                      fill={task.priority === "urgent" || task.priority === "high" ? "#dc2626" : "#64748b"}
                      fontSize="9"
                      fontWeight="700"
                      fontFamily="sans-serif"
                    >
                      {task.priority.toUpperCase()}
                    </text>
                  )}

                  {/* Task Title */}
                  <text
                    x="12"
                    y="46"
                    fill="#0f172a"
                    fontSize="11.5"
                    fontWeight="700"
                    fontFamily="sans-serif"
                  >
                    {task.title.length > 24 ? task.title.slice(0, 22) + "…" : task.title}
                  </text>

                  {/* Assignee / Metadata */}
                  <text
                    x="12"
                    y="68"
                    fill="#64748b"
                    fontSize="9.5"
                    fontFamily="sans-serif"
                  >
                    👤 {assigneeName.length > 20 ? assigneeName.slice(0, 18) + "…" : assigneeName}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Selected Task Inspector */}
        <div
          style={{
            flex: "1 1 280px",
            minWidth: "280px",
            background: "#ffffff",
            padding: "1rem",
            borderRadius: "6px",
            border: "1px solid #cbd5e1",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <h5 style={{ margin: "0 0 0.75rem 0", borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
            {selectedNode ? `Task #${selectedNode.task.id}: ${selectedNode.task.title}` : "Select a Task Node"}
          </h5>

          {selectedNode ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
                  Status
                </label>
                <select
                  value={selectedNode.task.status}
                  disabled={disabled || isUpdating}
                  onChange={(e) => void handleStatusChange(e.target.value as LabTask["status"])}
                  style={{ width: "100%", padding: "0.35rem", marginTop: "0.2rem", borderRadius: "4px" }}
                >
                  <option value="open">Open</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="blocked">Blocked</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>

              <div>
                <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
                  <strong>Priority:</strong> {selectedNode.task.priority.toUpperCase()}
                </span>
                <br />
                <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
                  <strong>Assignee:</strong>{" "}
                  {selectedNode.task.assigned_to_user_id
                    ? userMap.get(selectedNode.task.assigned_to_user_id) || `#${selectedNode.task.assigned_to_user_id}`
                    : "None"}
                </span>
              </div>

              {selectedNode.task.description && (
                <div style={{ fontSize: "0.8rem", color: "#334155", background: "#f8fafc", padding: "0.5rem", borderRadius: "4px" }}>
                  <strong>Description:</strong>
                  <p style={{ margin: "0.25rem 0 0 0" }}>{selectedNode.task.description}</p>
                </div>
              )}

              {/* Prerequisites & Dependents */}
              <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "0.5rem" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#475569" }}>
                  Prerequisites ({selectedNode.dependencies.length}):
                </span>
                {selectedNode.dependencies.length > 0 ? (
                  <ul style={{ margin: "0.25rem 0 0 0", paddingLeft: "1.2rem", fontSize: "0.8rem", color: "#64748b" }}>
                    {selectedNode.dependencies.map((depId) => {
                      const depTask = tasks.find((t) => t.id === depId);
                      return (
                        <li key={depId}>
                          Task #{depId}: {depTask ? depTask.title : "Unknown"} ({depTask?.status})
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", color: "#94a3b8" }}>
                    No prerequisite tasks. This task can begin immediately.
                  </p>
                )}
              </div>

              {/* Add Dependency Control */}
              {!disabled && onAddTaskDependency && (
                <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "0.5rem" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                    Add Prerequisite Task:
                  </label>
                  <div style={{ display: "flex", gap: "0.35rem" }}>
                    <select
                      value={targetDepId}
                      onChange={(e) => setTargetDepId(e.target.value ? Number(e.target.value) : "")}
                      style={{ flex: 1, padding: "0.35rem", fontSize: "0.8rem" }}
                    >
                      <option value="">-- Choose prerequisite --</option>
                      {tasks
                        .filter((t) => t.id !== selectedNode.task.id && !selectedNode.dependencies.includes(t.id))
                        .map((t) => (
                          <option key={t.id} value={t.id}>
                            #{t.id} - {t.title}
                          </option>
                        ))}
                    </select>
                    <button
                      className="button button-outline"
                      type="button"
                      disabled={!targetDepId || isUpdating}
                      onClick={() => void handleAddDependency()}
                      style={{ padding: "0.35rem 0.6rem", fontSize: "0.8rem" }}
                    >
                      Link
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p style={{ fontSize: "0.85rem", color: "#94a3b8", margin: 0 }}>
              Click on any task card on the DAG canvas to inspect its status, assignee, and prerequisite workflow dependencies.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
