import { useState } from "react";
import { generateCode39Svg, generateQrCodeSvg } from "./barcodeUtils";

export interface LabelData {
  title: string;
  idCode: string;
  type: string;
  date?: string;
  creator?: string;
  extraInfo?: string;
}

interface LabLabelGeneratorProps {
  data: LabelData;
  onClose: () => void;
}

type LabelSize = "cryo" | "standard" | "plate";

interface LabelFormat {
  name: string;
  widthMm: number;
  heightMm: number;
  description: string;
}

const FORMATS: Record<LabelSize, LabelFormat> = {
  cryo: {
    name: "Cryovial / 1.5mL Tube",
    widthMm: 25,
    heightMm: 12,
    description: "Compact 1.0\" x 0.5\" cryotube label",
  },
  standard: {
    name: "Standard Vial / Slide",
    widthMm: 38,
    heightMm: 25,
    description: "Standard 1.5\" x 1.0\" specimen vial or slide",
  },
  plate: {
    name: "Bottle / Plate / Box",
    widthMm: 50,
    heightMm: 25,
    description: "Large 2.0\" x 1.0\" bottle or 96-well plate label",
  },
};

export function LabLabelGenerator({ data, onClose }: LabLabelGeneratorProps) {
  const [format, setFormat] = useState<LabelSize>("standard");
  const [barcodeType, setBarcodeType] = useState<"qr" | "1d">("qr");

  const qrSvg = generateQrCodeSvg(data.idCode || data.title, 3);
  const code39Svg = generateCode39Svg(data.idCode || "ITEM-01", 30);

  function handlePrint() {
    window.print();
  }

  return (
    <div
      className="modal-backdrop"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(15, 23, 42, 0.65)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "1rem",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card print-label-modal"
        style={{
          background: "#ffffff",
          borderRadius: "8px",
          width: "100%",
          maxWidth: "520px",
          padding: "1.5rem",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.2rem" }}>Print Laboratory Label</h3>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", fontSize: "1.25rem", cursor: "pointer", color: "#64748b" }}
          >
            &times;
          </button>
        </div>

        {/* Format Selectors */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
              Label Format:
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as LabelSize)}
              style={{ width: "100%", padding: "0.4rem", borderRadius: "4px" }}
            >
              {Object.entries(FORMATS).map(([k, f]) => (
                <option key={k} value={k}>
                  {f.name} ({f.widthMm}x{f.heightMm}mm)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>
              Code Type:
            </label>
            <select
              value={barcodeType}
              onChange={(e) => setBarcodeType(e.target.value as "qr" | "1d")}
              style={{ width: "100%", padding: "0.4rem", borderRadius: "4px" }}
            >
              <option value="qr">2D QR Code (Recommended)</option>
              <option value="1d">1D Code-39 Barcode</option>
            </select>
          </div>
        </div>

        {/* Label Preview Area */}
        <div
          style={{
            background: "#f8fafc",
            border: "2px dashed #cbd5e1",
            borderRadius: "6px",
            padding: "1.5rem",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            marginBottom: "1.5rem",
          }}
        >
          <div
            id="printable-lab-label"
            style={{
              background: "#ffffff",
              border: "1px solid #1e293b",
              borderRadius: "4px",
              padding: "6px 8px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: format === "cryo" ? "220px" : format === "standard" ? "280px" : "340px",
              minHeight: format === "cryo" ? "70px" : "90px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.06)",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {/* Barcode/QR Graphic */}
            <div style={{ flexShrink: 0 }}>
              {barcodeType === "qr" ? (
                <div dangerouslySetInnerHTML={{ __html: qrSvg }} />
              ) : (
                <div
                  style={{ maxWidth: format === "cryo" ? "90px" : "110px", overflow: "hidden" }}
                  dangerouslySetInnerHTML={{ __html: code39Svg }}
                />
              )}
            </div>

            {/* Label Metadata Text */}
            <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
              <div
                style={{
                  fontSize: format === "cryo" ? "0.75rem" : "0.85rem",
                  fontWeight: 700,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  color: "#0f172a",
                }}
                title={data.title}
              >
                {data.title}
              </div>

              <div
                style={{
                  fontSize: format === "cryo" ? "0.65rem" : "0.75rem",
                  fontFamily: "monospace",
                  color: "#334155",
                  marginTop: "1px",
                }}
              >
                {data.idCode || "NO-ID"}
              </div>

              <div
                style={{
                  display: "inline-block",
                  fontSize: "0.6rem",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  padding: "1px 4px",
                  borderRadius: "2px",
                  background: "#e2e8f0",
                  color: "#475569",
                  marginTop: "2px",
                }}
              >
                {data.type}
              </div>

              {format !== "cryo" && (
                <div style={{ fontSize: "0.65rem", color: "#64748b", marginTop: "2px" }}>
                  {data.date || new Date().toISOString().split("T")[0]}
                  {data.creator ? ` | ${data.creator}` : ""}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <button className="button button-outline" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button button-primary" type="button" onClick={handlePrint}>
            Print Label (Thermal / Paper)
          </button>
        </div>
      </div>
    </div>
  );
}
