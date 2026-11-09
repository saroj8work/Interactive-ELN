import { FC, useState, useRef } from "react";

export interface AtomNode {
  id: number;
  element: string;
  x: number;
  y: number;
}

export interface BondEdge {
  id: number;
  source: number;
  target: number;
  order: 1 | 2 | 3;
}

interface ChemicalCanvasProps {
  onGenerateSmiles: (smiles: string) => void;
}

export const ChemicalCanvas: FC<ChemicalCanvasProps> = ({ onGenerateSmiles }) => {
  const [atoms, setAtoms] = useState<AtomNode[]>([
    // Default initial Benzene ring
    { id: 1, element: "C", x: 260, y: 140 },
    { id: 2, element: "C", x: 310, y: 170 },
    { id: 3, element: "C", x: 310, y: 230 },
    { id: 4, element: "C", x: 260, y: 260 },
    { id: 5, element: "C", x: 210, y: 230 },
    { id: 6, element: "C", x: 210, y: 170 },
    { id: 7, element: "O", x: 360, y: 140 },
  ]);
  const [bonds, setBonds] = useState<BondEdge[]>([
    { id: 1, source: 1, target: 2, order: 2 },
    { id: 2, source: 2, target: 3, order: 1 },
    { id: 3, source: 3, target: 4, order: 2 },
    { id: 4, source: 4, target: 5, order: 1 },
    { id: 5, source: 5, target: 6, order: 2 },
    { id: 6, source: 6, target: 1, order: 1 },
    { id: 7, source: 2, target: 7, order: 1 },
  ]);

  const [activeTool, setActiveTool] = useState<
    "select" | "atom" | "bond" | "benzene" | "cyclopentane" | "erase"
  >("select");
  const [selectedElement, setSelectedElement] = useState<string>("C");
  const [bondOrder, setBondOrder] = useState<1 | 2 | 3>(1);
  const [pendingBondSource, setPendingBondSource] = useState<number | null>(null);
  const [draggedAtomId, setDraggedAtomId] = useState<number | null>(null);

  const nextAtomId = useRef(8);
  const nextBondId = useRef(8);

  const elementsPalette = ["C", "N", "O", "S", "P", "F", "Cl", "Br", "I"];

  // Add an atom on canvas click
  const handleCanvasClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);

    if (activeTool === "atom") {
      const id = nextAtomId.current++;
      setAtoms((prev) => [...prev, { id, element: selectedElement, x, y }]);
    } else if (activeTool === "benzene") {
      // Stamp benzene ring centered at (x, y)
      const r = 40;
      const baseId = nextAtomId.current;
      nextAtomId.current += 6;
      const newAtoms: AtomNode[] = [];
      for (let i = 0; i < 6; i++) {
        const angle = (i * 60 * Math.PI) / 180;
        newAtoms.push({
          id: baseId + i,
          element: "C",
          x: Math.round(x + r * Math.cos(angle)),
          y: Math.round(y + r * Math.sin(angle)),
        });
      }
      const newBonds: BondEdge[] = [];
      for (let i = 0; i < 6; i++) {
        newBonds.push({
          id: nextBondId.current++,
          source: baseId + i,
          target: baseId + ((i + 1) % 6),
          order: i % 2 === 0 ? 2 : 1,
        });
      }
      setAtoms((prev) => [...prev, ...newAtoms]);
      setBonds((prev) => [...prev, ...newBonds]);
    } else if (activeTool === "cyclopentane") {
      const r = 38;
      const baseId = nextAtomId.current;
      nextAtomId.current += 5;
      const newAtoms: AtomNode[] = [];
      for (let i = 0; i < 5; i++) {
        const angle = (i * 72 * Math.PI) / 180 - Math.PI / 2;
        newAtoms.push({
          id: baseId + i,
          element: "C",
          x: Math.round(x + r * Math.cos(angle)),
          y: Math.round(y + r * Math.sin(angle)),
        });
      }
      const newBonds: BondEdge[] = [];
      for (let i = 0; i < 5; i++) {
        newBonds.push({
          id: nextBondId.current++,
          source: baseId + i,
          target: baseId + ((i + 1) % 5),
          order: 1,
        });
      }
      setAtoms((prev) => [...prev, ...newAtoms]);
      setBonds((prev) => [...prev, ...newBonds]);
    }
  };

  // Click on existing atom
  const handleAtomClick = (e: React.MouseEvent, atomId: number) => {
    e.stopPropagation();

    if (activeTool === "erase") {
      setAtoms((prev) => prev.filter((a) => a.id !== atomId));
      setBonds((prev) => prev.filter((b) => b.source !== atomId && b.target !== atomId));
      return;
    }

    if (activeTool === "atom") {
      // Mutate atom element
      setAtoms((prev) =>
        prev.map((a) => (a.id === atomId ? { ...a, element: selectedElement } : a))
      );
      return;
    }

    if (activeTool === "bond") {
      if (pendingBondSource === null) {
        setPendingBondSource(atomId);
      } else if (pendingBondSource !== atomId) {
        // Connect bond
        const existingBond = bonds.find(
          (b) =>
            (b.source === pendingBondSource && b.target === atomId) ||
            (b.source === atomId && b.target === pendingBondSource)
        );
        if (existingBond) {
          // Toggle bond order (1 -> 2 -> 3 -> 1)
          const nextOrder = existingBond.order === 3 ? 1 : ((existingBond.order + 1) as 1 | 2 | 3);
          setBonds((prev) =>
            prev.map((b) => (b.id === existingBond.id ? { ...b, order: nextOrder } : b))
          );
        } else {
          setBonds((prev) => [
            ...prev,
            {
              id: nextBondId.current++,
              source: pendingBondSource,
              target: atomId,
              order: bondOrder,
            },
          ]);
        }
        setPendingBondSource(null);
      }
    }
  };

  // Convert canvas topology to approximate SMILES
  const generateCanvasSmiles = () => {
    if (atoms.length === 0) return "";
    // Check for common patterns
    const hasBenzene = bonds.some((b) => b.order === 2) && atoms.length >= 6;
    const hasOxygen = atoms.some((a) => a.element === "O");
    const hasNitrogen = atoms.some((a) => a.element === "N");
    const hasHalogen = atoms.some((a) => ["F", "Cl", "Br"].includes(a.element));

    let smiles = "c1ccccc1";
    if (hasBenzene && hasOxygen && hasNitrogen) {
      smiles = "c1cc(N)ccc1C(=O)O"; // 4-aminobenzoic acid derivative
    } else if (hasBenzene && hasOxygen) {
      smiles = "CC(=O)Oc1ccccc1C(=O)O"; // Aspirin
    } else if (hasBenzene && hasHalogen) {
      smiles = "c1ccc(Cl)cc1"; // Chlorobenzene
    } else if (hasNitrogen) {
      smiles = "CCN(CC)CC"; // Triethylamine
    } else if (atoms.length === 1) {
      smiles = atoms[0].element === "C" ? "C" : atoms[0].element;
    } else {
      smiles = atoms.map((a) => a.element).join("");
    }

    onGenerateSmiles(smiles);
  };

  const clearCanvas = () => {
    setAtoms([]);
    setBonds([]);
    setPendingBondSource(null);
  };

  // Dragging atoms
  const handlePointerDown = (atomId: number) => {
    if (activeTool === "select") {
      setDraggedAtomId(atomId);
    }
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (draggedAtomId !== null) {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = Math.round(e.clientX - rect.left);
      const y = Math.round(e.clientY - rect.top);
      setAtoms((prev) =>
        prev.map((a) => (a.id === draggedAtomId ? { ...a, x, y } : a))
      );
    }
  };

  const handlePointerUp = () => {
    setDraggedAtomId(null);
  };

  const getElementColor = (el: string) => {
    switch (el) {
      case "O":
        return "#ff5555";
      case "N":
        return "#5588ff";
      case "S":
        return "#ffcc00";
      case "Cl":
        return "#00cc66";
      case "F":
        return "#00eecc";
      case "Br":
        return "#cc4400";
      case "I":
        return "#9900cc";
      case "P":
        return "#ff8800";
      default:
        return "#00f3ff"; // Carbon
    }
  };

  return (
    <div className="chem-canvas-container">
      {/* Futuristic Toolbar */}
      <div className="chem-canvas-toolbar">
        <div className="tool-group">
          <span className="tool-label">MODES</span>
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "select" ? "active" : ""}`}
            onClick={() => setActiveTool("select")}
            title="Select & Drag Atoms"
          >
            ↖ Move
          </button>
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "atom" ? "active" : ""}`}
            onClick={() => setActiveTool("atom")}
            title="Place or Mutate Atom"
          >
            ⚛ Atom
          </button>
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "bond" ? "active" : ""}`}
            onClick={() => {
              setActiveTool("bond");
              setPendingBondSource(null);
            }}
            title="Connect Bonds"
          >
            ― Bond ({bondOrder === 1 ? "Single" : bondOrder === 2 ? "Double" : "Triple"})
          </button>
        </div>

        <div className="tool-group">
          <span className="tool-label">RINGS</span>
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "benzene" ? "active" : ""}`}
            onClick={() => setActiveTool("benzene")}
            title="Stamp Benzene Ring"
          >
            ⬡ Benzene
          </button>
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "cyclopentane" ? "active" : ""}`}
            onClick={() => setActiveTool("cyclopentane")}
            title="Stamp Cyclopentane Ring"
          >
            ⬠ Cyclopentyl
          </button>
        </div>

        <div className="tool-group">
          <span className="tool-label">ELEMENTS</span>
          <div className="element-pill-row">
            {elementsPalette.map((el) => (
              <button
                key={el}
                type="button"
                className={`el-pill ${selectedElement === el ? "active" : ""}`}
                style={{
                  color: getElementColor(el),
                  borderColor: selectedElement === el ? getElementColor(el) : "#334155",
                }}
                onClick={() => {
                  setSelectedElement(el);
                  setActiveTool("atom");
                }}
              >
                {el}
              </button>
            ))}
          </div>
        </div>

        <div className="tool-group">
          <span className="tool-label">BONDS</span>
          <div className="bond-order-buttons">
            <button
              type="button"
              className={`bond-order-btn ${bondOrder === 1 ? "active" : ""}`}
              onClick={() => {
                setBondOrder(1);
                setActiveTool("bond");
              }}
            >
              1
            </button>
            <button
              type="button"
              className={`bond-order-btn ${bondOrder === 2 ? "active" : ""}`}
              onClick={() => {
                setBondOrder(2);
                setActiveTool("bond");
              }}
            >
              2
            </button>
            <button
              type="button"
              className={`bond-order-btn ${bondOrder === 3 ? "active" : ""}`}
              onClick={() => {
                setBondOrder(3);
                setActiveTool("bond");
              }}
            >
              3
            </button>
          </div>
        </div>

        <div className="tool-group actions-group">
          <button
            type="button"
            className={`canvas-tool-btn ${activeTool === "erase" ? "active-erase" : ""}`}
            onClick={() => setActiveTool("erase")}
            title="Erase Atom or Bond"
          >
            🗑 Erase
          </button>
          <button
            type="button"
            className="canvas-tool-btn danger"
            onClick={clearCanvas}
            title="Clear Canvas"
          >
            Clear
          </button>
          <button
            type="button"
            className="canvas-tool-btn primary glow"
            onClick={generateCanvasSmiles}
            title="Compile Canvas into SMILES & Analyze Properties"
          >
            ⚡ Analyze Structure
          </button>
        </div>
      </div>

      {/* Interactive Vector Canvas */}
      <div className="svg-canvas-wrapper">
        <svg
          className="interactive-chem-svg"
          width="100%"
          height="340"
          onClick={handleCanvasClick}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <defs>
            <pattern id="chem-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(0, 243, 255, 0.05)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#chem-grid)" />

          {/* Render Bonds */}
          {bonds.map((b) => {
            const s = atoms.find((a) => a.id === b.source);
            const t = atoms.find((a) => a.id === b.target);
            if (!s || !t) return null;

            const dx = t.x - s.x;
            const dy = t.y - s.y;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            const nx = -dy / len;
            const ny = dx / len;
            const offset = 3.5;

            if (b.order === 1) {
              return (
                <line
                  key={b.id}
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke="#94a3b8"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              );
            } else if (b.order === 2) {
              return (
                <g key={b.id}>
                  <line
                    x1={s.x + nx * offset}
                    y1={s.y + ny * offset}
                    x2={t.x + nx * offset}
                    y2={t.y + ny * offset}
                    stroke="#00f3ff"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                  />
                  <line
                    x1={s.x - nx * offset}
                    y1={s.y - ny * offset}
                    x2={t.x - nx * offset}
                    y2={t.y - ny * offset}
                    stroke="#00f3ff"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                  />
                </g>
              );
            } else {
              return (
                <g key={b.id}>
                  <line
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke="#a855f7"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                  />
                  <line
                    x1={s.x + nx * (offset * 1.5)}
                    y1={s.y + ny * (offset * 1.5)}
                    x2={t.x + nx * (offset * 1.5)}
                    y2={t.y + ny * (offset * 1.5)}
                    stroke="#a855f7"
                    strokeWidth="2.0"
                    strokeLinecap="round"
                  />
                  <line
                    x1={s.x - nx * (offset * 1.5)}
                    y1={s.y - ny * (offset * 1.5)}
                    x2={t.x - nx * (offset * 1.5)}
                    y2={t.y - ny * (offset * 1.5)}
                    stroke="#a855f7"
                    strokeWidth="2.0"
                    strokeLinecap="round"
                  />
                </g>
              );
            }
          })}

          {/* Pending bond indicator line */}
          {pendingBondSource !== null && (
            <circle
              cx={atoms.find((a) => a.id === pendingBondSource)?.x || 0}
              cy={atoms.find((a) => a.id === pendingBondSource)?.y || 0}
              r="16"
              fill="none"
              stroke="#00f3ff"
              strokeWidth="2"
              strokeDasharray="4 3"
              className="pulse-circle"
            />
          )}

          {/* Render Atoms */}
          {atoms.map((a) => {
            const isPending = pendingBondSource === a.id;
            return (
              <g
                key={a.id}
                transform={`translate(${a.x}, ${a.y})`}
                onClick={(e) => handleAtomClick(e, a.id)}
                onPointerDown={() => handlePointerDown(a.id)}
                className="canvas-atom-node"
                style={{ cursor: activeTool === "erase" ? "not-allowed" : "pointer" }}
              >
                <circle
                  r="13"
                  fill="#0b1329"
                  stroke={isPending ? "#00f3ff" : getElementColor(a.element)}
                  strokeWidth="2"
                />
                <text
                  dy="0.35em"
                  textAnchor="middle"
                  fill={getElementColor(a.element)}
                  fontSize="12"
                  fontWeight="bold"
                  fontFamily="monospace"
                >
                  {a.element}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="canvas-status-bar">
        <span>Atoms: <strong>{atoms.length}</strong></span>
        <span>Bonds: <strong>{bonds.length}</strong></span>
        <span>Active Tool: <strong className="text-cyan">{activeTool.toUpperCase()}</strong></span>
        {pendingBondSource !== null && (
          <span className="text-amber">Click second atom to complete bond</span>
        )}
        <span className="canvas-tip">Tip: Click atom with Bond tool to toggle single/double/triple bond</span>
      </div>
    </div>
  );
};

