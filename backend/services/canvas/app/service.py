import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import WorkflowCanvas, WorkflowCanvasRun


PRESET_TEMPLATES = [
    {
        "name": "ELISA Automated Assay Workflow",
        "description": "Standard 96-well sandwich ELISA procedure with automated wash gates and 450nm readout",
        "nodes": [
            {"id": "node-1", "label": "Reagent Prep & Standard Dilution", "type": "prep", "duration_min": 20, "x": 100, "y": 150},
            {"id": "node-2", "label": "Plate Coating (Capture Ab)", "type": "pipette", "duration_min": 15, "x": 320, "y": 150},
            {"id": "node-3", "label": "Overnight Incubation @ 4°C", "type": "incubate", "duration_min": 720, "x": 540, "y": 150},
            {"id": "node-4", "label": "Blocking Buffer Treatment", "type": "prep", "duration_min": 60, "x": 760, "y": 150},
            {"id": "node-5", "label": "Sample Addition & Standards", "type": "pipette", "duration_min": 30, "x": 980, "y": 150},
            {"id": "node-6", "label": "Microplate Wash Cycle (PBST 3x)", "type": "wash", "duration_min": 10, "x": 760, "y": 300},
            {"id": "node-7", "label": "Secondary HRP Detection Ab", "type": "pipette", "duration_min": 45, "x": 540, "y": 300},
            {"id": "node-8", "label": "TMB Substrate & Stop Solution", "type": "read", "duration_min": 15, "x": 320, "y": 300},
            {"id": "node-9", "label": "OD 450nm Spectrophotometry", "type": "read", "duration_min": 5, "x": 100, "y": 300},
        ],
        "edges": [
            {"id": "e1-2", "source": "node-1", "target": "node-2"},
            {"id": "e2-3", "source": "node-2", "target": "node-3"},
            {"id": "e3-4", "source": "node-3", "target": "node-4"},
            {"id": "e4-5", "source": "node-4", "target": "node-5"},
            {"id": "e5-6", "source": "node-5", "target": "node-6"},
            {"id": "e6-7", "source": "node-6", "target": "node-7"},
            {"id": "e7-8", "source": "node-7", "target": "node-8"},
            {"id": "e8-9", "source": "node-8", "target": "node-9"},
        ],
    },
    {
        "name": "CRISPR-Cas9 sgRNA Ligation & Screening",
        "description": "Golden Gate assembly, E. coli heat shock transformation, and Sanger validation",
        "nodes": [
            {"id": "c1", "label": "sgRNA Oligo Annealing & Phosphorylation", "type": "prep", "duration_min": 45, "x": 120, "y": 160},
            {"id": "c2", "label": "BsmBI Vector Digestion", "type": "prep", "duration_min": 60, "x": 360, "y": 100},
            {"id": "c3", "label": "T4 DNA Ligation", "type": "prep", "duration_min": 30, "x": 600, "y": 160},
            {"id": "c4", "label": "DH5α Heat Shock Transformation", "type": "incubate", "duration_min": 90, "x": 840, "y": 160},
            {"id": "c5", "label": "Ampicillin Selection Plating", "type": "incubate", "duration_min": 960, "x": 840, "y": 320},
            {"id": "c6", "label": "Colony PCR & Gel QC Gate", "type": "read", "duration_min": 120, "x": 500, "y": 320},
        ],
        "edges": [
            {"id": "ce1", "source": "c1", "target": "c3"},
            {"id": "ce2", "source": "c2", "target": "c3"},
            {"id": "ce3", "source": "c3", "target": "c4"},
            {"id": "ce4", "source": "c4", "target": "c5"},
            {"id": "ce5", "source": "c5", "target": "c6"},
        ],
    },
]


class CanvasService:
    def __init__(self, db: Session):
        self.db = db

    def validate_dag(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the DAG using Kahn's topological sorting algorithm.
        Returns is_valid, topological_order, or cycle error details.
        """
        node_ids = set(n["id"] for n in nodes)
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}

        for e in edges:
            u = e["source"]
            v = e["target"]
            if u in node_ids and v in node_ids:
                adj[u].append(v)
                in_degree[v] = in_degree.get(v, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        topological_order: List[str] = []

        while queue:
            curr = queue.pop(0)
            topological_order.append(curr)
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        has_cycle = len(topological_order) < len(node_ids)

        return {
            "is_valid": not has_cycle,
            "has_cycle": has_cycle,
            "total_nodes": len(node_ids),
            "total_edges": len(edges),
            "topological_order": topological_order if not has_cycle else [],
            "error": "Cycle or dependency deadlock detected in workflow DAG!" if has_cycle else None,
        }

    def create_canvas(
        self,
        organization_id: int,
        name: str,
        description: str = "",
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
    ) -> WorkflowCanvas:
        canvas = WorkflowCanvas(
            organization_id=organization_id,
            project_id=project_id,
            experiment_id=experiment_id,
            name=name,
            description=description,
            nodes_json=json.dumps(nodes or []),
            edges_json=json.dumps(edges or []),
        )
        self.db.add(canvas)
        self.db.commit()
        self.db.refresh(canvas)
        return canvas

    def list_canvases(
        self,
        organization_id: int,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
    ) -> List[WorkflowCanvas]:
        stmt = select(WorkflowCanvas).where(WorkflowCanvas.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(WorkflowCanvas.project_id == project_id)
        if experiment_id is not None:
            stmt = stmt.where(WorkflowCanvas.experiment_id == experiment_id)
        stmt = stmt.order_by(WorkflowCanvas.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_canvas(self, canvas_id: int, organization_id: int) -> Optional[WorkflowCanvas]:
        stmt = select(WorkflowCanvas).where(
            WorkflowCanvas.id == canvas_id,
            WorkflowCanvas.organization_id == organization_id,
        )
        return self.db.scalars(stmt).first()

    def update_canvas(
        self,
        canvas_id: int,
        organization_id: int,
        name: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
    ) -> Optional[WorkflowCanvas]:
        canvas = self.get_canvas(canvas_id, organization_id)
        if not canvas:
            return None
        if name is not None:
            canvas.name = name
        if nodes is not None:
            canvas.nodes_json = json.dumps(nodes)
        if edges is not None:
            canvas.edges_json = json.dumps(edges)
        if status is not None:
            canvas.status = status
        self.db.commit()
        self.db.refresh(canvas)
        return canvas

    def start_execution(self, canvas_id: int, organization_id: int) -> Optional[WorkflowCanvasRun]:
        canvas = self.get_canvas(canvas_id, organization_id)
        if not canvas:
            return None

        nodes = json.loads(canvas.nodes_json)
        edges = json.loads(canvas.edges_json)

        val = self.validate_dag(nodes, edges)
        if not val["is_valid"]:
            raise ValueError(val["error"])

        # Initial node states
        in_degrees = {n["id"]: 0 for n in nodes}
        for e in edges:
            in_degrees[e["target"]] = in_degrees.get(e["target"], 0) + 1

        node_states = {}
        for nid, deg in in_degrees.items():
            node_states[nid] = "ready" if deg == 0 else "pending"

        first_ready = next((nid for nid, st in node_states.items() if st == "ready"), None)

        run = WorkflowCanvasRun(
            canvas_id=canvas.id,
            status="running",
            current_node_id=first_ready,
            node_states_json=json.dumps(node_states),
            logs_json=json.dumps([f"Execution initialized at {datetime.now(timezone.utc).isoformat()}"]),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def step_execution(self, run_id: int, completed_node_id: str) -> Optional[WorkflowCanvasRun]:
        stmt = select(WorkflowCanvasRun).where(WorkflowCanvasRun.id == run_id)
        run = self.db.scalars(stmt).first()
        if not run:
            return None

        stmt_canvas = select(WorkflowCanvas).where(WorkflowCanvas.id == run.canvas_id)
        canvas = self.db.scalars(stmt_canvas).first()
        if not canvas:
            return None

        nodes = json.loads(canvas.nodes_json)
        edges = json.loads(canvas.edges_json)
        node_states = json.loads(run.node_states_json)
        logs = json.loads(run.logs_json)

        # Mark completed
        node_states[completed_node_id] = "completed"
        logs.append(f"Node [{completed_node_id}] completed at {datetime.now(timezone.utc).isoformat()}")

        # Check which downstream nodes can be activated
        for n in nodes:
            nid = n["id"]
            if node_states.get(nid) == "pending":
                prereq_edges = [e for e in edges if e["target"] == nid]
                all_prereqs_done = all(node_states.get(e["source"]) == "completed" for e in prereq_edges)
                if all_prereqs_done:
                    node_states[nid] = "ready"
                    logs.append(f"Unlocked Node [{nid}] (prerequisites satisfied)")

        # Update run status
        next_ready = next((nid for nid, st in node_states.items() if st == "ready"), None)
        all_done = all(st == "completed" for st in node_states.values())

        if all_done:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.current_node_id = None
            logs.append("All workflow steps successfully executed!")
        else:
            run.current_node_id = next_ready

        run.node_states_json = json.dumps(node_states)
        run.logs_json = json.dumps(logs)
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_runs(self, canvas_id: int) -> List[WorkflowCanvasRun]:
        stmt = select(WorkflowCanvasRun).where(WorkflowCanvasRun.canvas_id == canvas_id).order_by(WorkflowCanvasRun.started_at.desc())
        return list(self.db.scalars(stmt).all())

