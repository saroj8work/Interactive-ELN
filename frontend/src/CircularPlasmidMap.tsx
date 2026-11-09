import { FC, useState } from "react";

export interface PlasmidFeature {
  id: string;
  name: string;
  type: "promoter" | "resistance" | "origin" | "mcs" | "tag";
  startBp: number;
  endBp: number;
  strand: 1 | -1;
  color: string;
  description: string;
}

export interface PlasmidCutSite {
  enzyme: string;
  positionBp: number;
  overhang: string;
}

interface CircularPlasmidMapProps {
  plasmidName: string;
  totalBp: number;
  gcPercent: number;
  topology?: "circular" | "linear";
}

export const CircularPlasmidMap: FC<CircularPlasmidMapProps> = ({
  plasmidName,
  totalBp,
  gcPercent,
  topology = "circular",
}) => {
  const [rotation, setRotation] = useState<number>(0);
  const [zoom, setZoom] = useState<number>(1.0);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<any | null>(null);

  // Standard cloning features normalized to totalBp
  const len = totalBp || 2686;
  const features: PlasmidFeature[] = [
    {
      id: "feat-amp",
      name: "AmpR (β-lactamase)",
      type: "resistance",
      startBp: Math.round(len * 0.08),
      endBp: Math.round(len * 0.40),
      strand: -1,
      color: "#f59e0b", // Amber glow
      description: "Confers ampicillin/carbenicillin resistance in E. coli selection.",
    },
    {
      id: "feat-ori",
      name: "ori (pMB1 origin)",
      type: "origin",
      startBp: Math.round(len * 0.48),
      endBp: Math.round(len * 0.72),
      strand: 1,
      color: "#8b5cf6", // Purple glow
      description: "High-copy number bacterial replication origin.",
    },
    {
      id: "feat-plac",
      name: "lac Promoter",
      type: "promoter",
      startBp: Math.round(len * 0.76),
      endBp: Math.round(len * 0.82),
      strand: 1,
      color: "#06b6d4", // Cyan glow
      description: "IPTG-inducible promoter for recombinant expression.",
    },
    {
      id: "feat-mcs",
      name: "MCS / Polylinker",
      type: "mcs",
      startBp: Math.round(len * 0.84),
      endBp: Math.round(len * 0.94),
      strand: 1,
      color: "#ec4899", // Pink glow
      description: "Multiple Cloning Site containing unique restriction endonuclease sites.",
    },
  ];

  const cutSites: PlasmidCutSite[] = [
    { enzyme: "EcoRI", positionBp: Math.round(len * 0.85), overhang: "5' AATT" },
    { enzyme: "BamHI", positionBp: Math.round(len * 0.87), overhang: "5' GATC" },
    { enzyme: "SmaI", positionBp: Math.round(len * 0.89), overhang: "Blunt" },
    { enzyme: "SalI", positionBp: Math.round(len * 0.91), overhang: "5' TCGA" },
    { enzyme: "PstI", positionBp: Math.round(len * 0.93), overhang: "3' TGCA" },
    { enzyme: "HindIII", positionBp: Math.round(len * 0.95), overhang: "5' AGCT" },
    { enzyme: "NdeI", positionBp: Math.round(len * 0.22), overhang: "5' TATG" },
    { enzyme: "PvuI", positionBp: Math.round(len * 0.35), overhang: "5' ATCG" },
  ];

  const cx = 260;
  const cy = 260;
  const radius = 150 * zoom;
  const trackWidth = 18 * zoom;

  // Convert bp coordinate to radians / degrees
  const bpToAngle = (bp: number) => {
    const fraction = (bp % len) / len;
    return fraction * 360 + rotation;
  };

  const polarToCartesian = (centerX: number, centerY: number, r: number, angleInDegrees: number) => {
    const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
    return {
      x: centerX + r * Math.cos(angleInRadians),
      y: centerY + r * Math.sin(angleInRadians),
    };
  };

  const describeArc = (x: number, y: number, r: number, startAngle: number, endAngle: number) => {
    const start = polarToCartesian(x, y, r, endAngle);
    const end = polarToCartesian(x, y, r, startAngle);
    let diff = endAngle - startAngle;
    if (diff < 0) diff += 360;
    const largeArcFlag = diff <= 180 ? "0" : "1";
    return ["M", start.x, start.y, "A", r, r, 0, largeArcFlag, 0, end.x, end.y].join(" ");
  };

  return (
    <div className="plasmid-map-container">
      {/* Interactive Controls Bar */}
      <div className="plasmid-controls-bar">
        <div className="control-group">
          <label>Rotate Map: <strong>{rotation}°</strong></label>
          <input
            type="range"
            min="-180"
            max="180"
            value={rotation}
            onChange={(e) => setRotation(+e.target.value)}
            className="plasmid-slider"
          />
          <button type="button" className="button button-outline button-xs" onClick={() => setRotation(0)}>
            Reset
          </button>
        </div>

        <div className="control-group">
          <label>Zoom: <strong>{zoom.toFixed(1)}×</strong></label>
          <input
            type="range"
            min="0.75"
            max="1.5"
            step="0.05"
            value={zoom}
            onChange={(e) => setZoom(+e.target.value)}
            className="plasmid-slider"
          />
        </div>

        <div className="plasmid-meta-badges">
          <span className="badge-cyan">{topology.toUpperCase()} PLASMID</span>
          <span className="badge-purple">{len.toLocaleString()} bp</span>
          <span className="badge-amber">{gcPercent.toFixed(1)}% GC</span>
        </div>
      </div>

      <div className="plasmid-viewport">
        {/* SVG Plasmid Map */}
        <div className="svg-plasmid-wrapper">
          <svg
            width="520"
            height="520"
            viewBox="0 0 520 520"
            className="plasmid-svg"
          >
            <defs>
              <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Circular Backbone Track */}
            <circle
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke="#1e293b"
              strokeWidth={trackWidth}
            />
            <circle
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke="#334155"
              strokeWidth="2"
            />

            {/* Scale Ticks (every ~10% of length) */}
            {Array.from({ length: 10 }).map((_, i) => {
              const tickBp = Math.round((len / 10) * i);
              const angle = bpToAngle(tickBp);
              const p1 = polarToCartesian(cx, cy, radius - trackWidth / 2 - 3, angle);
              const p2 = polarToCartesian(cx, cy, radius + trackWidth / 2 + 5, angle);
              const textPos = polarToCartesian(cx, cy, radius - trackWidth / 2 - 16, angle);
              return (
                <g key={i}>
                  <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke="#64748b" strokeWidth="1.5" />
                  <text
                    x={textPos.x}
                    y={textPos.y}
                    fill="#94a3b8"
                    fontSize="9"
                    fontWeight="600"
                    textAnchor="middle"
                    dominantBaseline="middle"
                  >
                    {tickBp}
                  </text>
                </g>
              );
            })}

            {/* Features Curved Arcs */}
            {features.map((f) => {
              const startAngle = bpToAngle(f.startBp);
              const endAngle = bpToAngle(f.endBp);
              const arcPath = describeArc(cx, cy, radius, startAngle, endAngle);
              const isHovered = hoveredItem === f.id;

              return (
                <g
                  key={f.id}
                  className="plasmid-feature-group"
                  onMouseEnter={() => setHoveredItem(f.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                  onClick={() => setSelectedItem(f)}
                  style={{ cursor: "pointer" }}
                >
                  <path
                    d={arcPath}
                    fill="none"
                    stroke={f.color}
                    strokeWidth={isHovered ? trackWidth + 4 : trackWidth - 2}
                    strokeLinecap="round"
                    filter={isHovered ? "url(#neon-glow)" : "none"}
                    opacity={isHovered ? 1 : 0.9}
                  />
                </g>
              );
            })}

            {/* Restriction Cut Sites (Radial Flags) */}
            {cutSites.map((site, idx) => {
              const angle = bpToAngle(site.positionBp);
              const pInner = polarToCartesian(cx, cy, radius + trackWidth / 2, angle);
              const pOuter = polarToCartesian(cx, cy, radius + trackWidth / 2 + 28, angle);
              const textAngle = angle % 360;
              const isRightSide = textAngle > 0 && textAngle < 180;
              const isHovered = hoveredItem === `site-${idx}`;

              return (
                <g
                  key={idx}
                  className="plasmid-cut-site"
                  onMouseEnter={() => setHoveredItem(`site-${idx}`)}
                  onMouseLeave={() => setHoveredItem(null)}
                  onClick={() => setSelectedItem(site)}
                  style={{ cursor: "pointer" }}
                >
                  <line
                    x1={pInner.x}
                    y1={pInner.y}
                    x2={pOuter.x}
                    y2={pOuter.y}
                    stroke={isHovered ? "#00f3ff" : "#ef4444"}
                    strokeWidth={isHovered ? "2.5" : "1.5"}
                    strokeDasharray="2 2"
                  />
                  <circle
                    cx={pOuter.x}
                    cy={pOuter.y}
                    r={isHovered ? 4 : 2.5}
                    fill={isHovered ? "#00f3ff" : "#ef4444"}
                  />
                  <text
                    x={pOuter.x + (isRightSide ? 5 : -5)}
                    y={pOuter.y + 3}
                    fill={isHovered ? "#00f3ff" : "#f8fafc"}
                    fontSize="10"
                    fontWeight="700"
                    textAnchor={isRightSide ? "start" : "end"}
                  >
                    {site.enzyme} ({site.positionBp})
                  </text>
                </g>
              );
            })}

            {/* Central Plasmid Information Hub */}
            <circle cx={cx} cy={cy} r={72 * zoom} fill="#0b1329" stroke="#1e293b" strokeWidth="3" />
            <text
              x={cx}
              y={cy - 18 * zoom}
              fill="#00f3ff"
              fontSize={14 * zoom}
              fontWeight="800"
              textAnchor="middle"
            >
              {plasmidName.length > 16 ? plasmidName.slice(0, 15) + "…" : plasmidName}
            </text>
            <text
              x={cx}
              y={cy + 6 * zoom}
              fill="#94a3b8"
              fontSize={12 * zoom}
              fontFamily="monospace"
              fontWeight="600"
              textAnchor="middle"
            >
              {len.toLocaleString()} bp
            </text>
            <text
              x={cx}
              y={cy + 24 * zoom}
              fill="#a855f7"
              fontSize={11 * zoom}
              fontWeight="600"
              textAnchor="middle"
            >
              GC: {gcPercent.toFixed(1)}%
            </text>
          </svg>
        </div>

        {/* Feature Inspector Sidebar */}
        <div className="plasmid-inspector-card">
          <h4>Annotation & Cut Site Inspector</h4>
          {selectedItem ? (
            <div className="inspector-content">
              {selectedItem.enzyme ? (
                <>
                  <div className="inspector-badge cut-site-badge">Restriction Endonuclease</div>
                  <h3 className="text-cyan">{selectedItem.enzyme}</h3>
                  <div className="inspector-field">
                    <span>Cut Position:</span> <strong>{selectedItem.positionBp} bp</strong>
                  </div>
                  <div className="inspector-field">
                    <span>Overhang:</span> <strong>{selectedItem.overhang}</strong>
                  </div>
                  <p className="inspector-note">Unique single-cutter site suitable for linear plasmid linearization or directional insert ligation.</p>
                </>
              ) : (
                <>
                  <div className="inspector-badge" style={{ background: selectedItem.color, color: "#000" }}>
                    {selectedItem.type.toUpperCase()}
                  </div>
                  <h3 style={{ color: selectedItem.color }}>{selectedItem.name}</h3>
                  <div className="inspector-field">
                    <span>Coordinates:</span> <strong>{selectedItem.startBp} – {selectedItem.endBp} bp</strong>
                  </div>
                  <div className="inspector-field">
                    <span>Span:</span> <strong>{selectedItem.endBp - selectedItem.startBp} bp</strong>
                  </div>
                  <div className="inspector-field">
                    <span>Strand:</span> <strong>{selectedItem.strand === 1 ? "Sense (+)" : "Antisense (-)"}</strong>
                  </div>
                  <p className="inspector-note">{selectedItem.description}</p>
                </>
              )}
            </div>
          ) : (
            <div className="empty-inspector">
              <p>Hover or click any feature arc or restriction site on the circular map to inspect coordinates, overhangs, and cloning parameters.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

