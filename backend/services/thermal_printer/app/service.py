import json
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import ThermalLabelTemplate, ImportedProtocol


STANDARD_LABEL_PRESETS = [
    {
        "name": "1.5mL / 2.0mL Cryovial Label",
        "label_type": "cryovial",
        "width_mm": 25,
        "height_mm": 12,
        "dpi": 203,
        "barcode_type": "DATAMATRIX",
    },
    {
        "name": "96-Well Microplate Skirt Barcode",
        "label_type": "microplate",
        "width_mm": 50,
        "height_mm": 8,
        "dpi": 300,
        "barcode_type": "CODE128",
    },
    {
        "name": "Chemical Reagent Bottle (with GHS)",
        "label_type": "reagent_bottle",
        "width_mm": 70,
        "height_mm": 35,
        "dpi": 203,
        "barcode_type": "QR",
    },
]

CURATED_PROTOCOLS_IO = [
    {
        "protocol_id_ext": "pr-89211",
        "title": "Direct-zol RNA Miniprep Plus High-Yield Protocol",
        "authors": "Dr. Sarah Chen, Genomics Core",
        "doi": "dx.doi.org/10.17504/protocols.io.89211",
        "description": "Column-based isolation of high quality total RNA (>17 nt) from cells, tissues, and viral biological samples without chloroform phase separation.",
        "steps": [
            {"step_num": 1, "title": "Cell Lysis & TRIzol Homogenization", "duration_min": 15, "temp_c": 20, "notes": "Add 300 µL TRI Reagent directly to pellet, pipette thoroughly."},
            {"step_num": 2, "title": "Ethanol Addition (1:1 Ratio)", "duration_min": 5, "temp_c": 20, "notes": "Add 300 µL 100% molecular biology grade ethanol and vortex 10 seconds."},
            {"step_num": 3, "title": "Zymo-Spin Column Binding", "duration_min": 10, "temp_c": 20, "notes": "Centrifuge at 12,000 x g for 30 seconds at room temperature."},
            {"step_num": 4, "title": "In-Column DNase I Digestion", "duration_min": 15, "temp_c": 25, "notes": "Incubate with 5 µL DNase I and 75 µL DNA Digestion Buffer for 15 min."},
            {"step_num": 5, "title": "RNA Wash & High-Speed Spin Drying", "duration_min": 10, "temp_c": 20, "notes": "Wash twice with 700 µL Direct-zol RNA Wash Buffer."},
            {"step_num": 6, "title": "Nuclease-Free Water Elution", "duration_min": 5, "temp_c": 20, "notes": "Elute in 50 µL DNase/RNase-free water into sterile cryovial."},
        ],
    },
    {
        "protocol_id_ext": "pr-44120",
        "title": "Multiplex TaqMan RT-qPCR Detection Assay",
        "authors": "Molecular Diagnostics Consortium",
        "doi": "dx.doi.org/10.17504/protocols.io.44120",
        "description": "High-sensitivity dual-target fluorogenic probe amplification with automated baseline cycle threshold determination.",
        "steps": [
            {"step_num": 1, "title": "Master Mix Preparation", "duration_min": 20, "temp_c": 4, "notes": "Combine 2x RT-qPCR buffer, primers (400 nM), and FAM/HEX hydrolysis probes."},
            {"step_num": 2, "title": "96-Well Plate Dispensing", "duration_min": 15, "temp_c": 4, "notes": "Dispense 15 µL master mix per well using calibrated multichannel pipette."},
            {"step_num": 3, "title": "Template RNA Addition & Microplate Sealing", "duration_min": 15, "temp_c": 4, "notes": "Add 5 µL extracted RNA template; apply optical adhesive seal firmly."},
            {"step_num": 4, "title": "Thermocycling: Reverse Transcription", "duration_min": 15, "temp_c": 50, "notes": "Reverse transcriptase synthesis cycle @ 50°C for 15 min."},
            {"step_num": 5, "title": "Polymerase Activation & 40-Cycle Amplification", "duration_min": 65, "temp_c": 95, "notes": "Initial denaturation 95°C for 2 min, followed by 40 cycles (95°C 10s, 60°C 30s)."},
        ],
    },
]


def generate_zebra_zpl(
    label_type: str,
    barcode_data: str,
    sample_name: str,
    lot_number: str = "LOT-2026-001",
    storage_temp: str = "-80°C",
    expiry_date: str = "2027-12-31",
    hazard_symbol: str = "GHS07",
    dpi: int = 203,
) -> Dict[str, Any]:
    """
    Generates exact Zebra ZPL II printer commands and an SVG label preview.
    """
    scale = 1.0 if dpi == 203 else 1.48
    width_dots = int(25 * 8 * scale) if label_type == "cryovial" else (int(50 * 8 * scale) if label_type == "microplate" else int(70 * 8 * scale))
    height_dots = int(12 * 8 * scale) if label_type == "cryovial" else (int(8 * 8 * scale) if label_type == "microplate" else int(35 * 8 * scale))

    zpl_lines = [
        "^XA",
        f"^PW{width_dots}",
        f"^LL{height_dots}",
        "^LH0,0",
    ]

    if label_type == "cryovial":
        # 2D DataMatrix barcode on left, sample name & LOT on right
        zpl_lines.extend([
            "^FO15,15^BXN,3,200^FD" + barcode_data + "^FS",
            "^FO85,15^A0N,18,18^FD" + sample_name[:16] + "^FS",
            "^FO85,38^A0N,14,14^FDLot: " + lot_number + "^FS",
            "^FO85,56^A0N,14,14^FDTemp: " + storage_temp + "^FS",
            "^FO85,74^A0N,12,12^FD" + barcode_data + "^FS",
        ])
        svg_preview = f"""<svg viewBox="0 0 240 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background:#fff; border:1px solid #000; border-radius:4px;">
            <rect x="12" y="12" width="60" height="60" fill="#000"/>
            <rect x="16" y="16" width="12" height="12" fill="#fff"/>
            <rect x="34" y="34" width="12" height="12" fill="#fff"/>
            <rect x="52" y="52" width="12" height="12" fill="#fff"/>
            <text x="85" y="28" font-family="monospace" font-size="13" font-weight="bold" fill="#000">{sample_name[:16]}</text>
            <text x="85" y="48" font-family="monospace" font-size="11" fill="#333">Lot: {lot_number}</text>
            <text x="85" y="66" font-family="monospace" font-size="11" fill="#333">Temp: {storage_temp}</text>
            <text x="85" y="84" font-family="monospace" font-size="9" fill="#666">{barcode_data}</text>
        </svg>"""

    elif label_type == "microplate":
        # Code 128 linear barcode on microplate skirt
        zpl_lines.extend([
            "^FO20,10^BCN,35,Y,N,N^FD" + barcode_data + "^FS",
            "^FO320,15^A0N,18,18^FD" + sample_name[:20] + "^FS",
            "^FO320,40^A0N,14,14^FD" + storage_temp + " | Exp: " + expiry_date + "^FS",
        ])
        svg_preview = f"""<svg viewBox="0 0 460 70" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background:#fff; border:1px solid #000; border-radius:4px;">
            <!-- Barcode stripes -->
            <rect x="20" y="10" width="4" height="35" fill="#000"/>
            <rect x="28" y="10" width="8" height="35" fill="#000"/>
            <rect x="40" y="10" width="3" height="35" fill="#000"/>
            <rect x="48" y="10" width="10" height="35" fill="#000"/>
            <rect x="64" y="10" width="4" height="35" fill="#000"/>
            <rect x="72" y="10" width="6" height="35" fill="#000"/>
            <rect x="84" y="10" width="4" height="35" fill="#000"/>
            <rect x="94" y="10" width="8" height="35" fill="#000"/>
            <rect x="108" y="10" width="5" height="35" fill="#000"/>
            <rect x="120" y="10" width="4" height="35" fill="#000"/>
            <text x="20" y="58" font-family="monospace" font-size="10" fill="#000">{barcode_data}</text>
            <text x="200" y="28" font-family="monospace" font-size="14" font-weight="bold" fill="#000">{sample_name[:20]}</text>
            <text x="200" y="50" font-family="monospace" font-size="11" fill="#444">{storage_temp} • Exp: {expiry_date}</text>
        </svg>"""

    else:
        # Chemical reagent bottle with QR code & GHS symbol
        zpl_lines.extend([
            "^FO25,25^BQN,2,4^FDQA," + barcode_data + "^FS",
            "^FO140,25^A0N,22,22^FD" + sample_name[:24] + "^FS",
            "^FO140,55^A0N,16,16^FDLot: " + lot_number + " | Exp: " + expiry_date + "^FS",
            "^FO140,80^A0N,16,16^FDStorage: " + storage_temp + "^FS",
            "^FO140,110^A0N,14,14^FDHazard Moieties: " + hazard_symbol + "^FS",
            "^FO140,140^A0N,12,12^FDSN: " + barcode_data + "^FS",
        ])
        svg_preview = f"""<svg viewBox="0 0 460 180" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background:#fff; border:2px solid #000; border-radius:4px;">
            <rect x="25" y="25" width="80" height="80" fill="#000"/>
            <rect x="35" y="35" width="20" height="20" fill="#fff"/>
            <rect x="40" y="40" width="10" height="10" fill="#000"/>
            <rect x="75" y="75" width="20" height="20" fill="#fff"/>
            <text x="135" y="45" font-family="sans-serif" font-size="16" font-weight="bold" fill="#000">{sample_name}</text>
            <text x="135" y="75" font-family="monospace" font-size="12" fill="#333">Lot: {lot_number} • Exp: {expiry_date}</text>
            <text x="135" y="100" font-family="monospace" font-size="12" fill="#333">Storage: {storage_temp}</text>
            <rect x="135" y="115" width="70" height="22" fill="#fef2f2" stroke="#ef4444" rx="3"/>
            <text x="142" y="131" font-family="sans-serif" font-size="11" font-weight="bold" fill="#ef4444">⚠️ {hazard_symbol}</text>
            <text x="135" y="160" font-family="monospace" font-size="10" fill="#666">{barcode_data}</text>
        </svg>"""

    zpl_lines.append("^XZ")
    zpl_code = "\n".join(zpl_lines)

    return {
        "label_type": label_type,
        "width_dots": width_dots,
        "height_dots": height_dots,
        "dpi": dpi,
        "zpl_code": zpl_code,
        "svg_preview": svg_preview,
    }


class ThermalPrinterService:
    def __init__(self, db: Session):
        self.db = db

    def generate_label(
        self,
        label_type: str,
        barcode_data: str,
        sample_name: str,
        lot_number: str = "LOT-2026-001",
        storage_temp: str = "-80°C",
        expiry_date: str = "2027-12-31",
        hazard_symbol: str = "GHS07",
        dpi: int = 203,
    ) -> Dict[str, Any]:
        return generate_zebra_zpl(
            label_type,
            barcode_data,
            sample_name,
            lot_number,
            storage_temp,
            expiry_date,
            hazard_symbol,
            dpi,
        )

    def get_presets(self) -> List[Dict[str, Any]]:
        return STANDARD_LABEL_PRESETS

    def search_protocols_io(self, query: str = "") -> List[Dict[str, Any]]:
        if not query:
            return CURATED_PROTOCOLS_IO
        q = query.lower()
        return [
            p for p in CURATED_PROTOCOLS_IO
            if q in p["title"].lower() or q in p["description"].lower() or q in p["authors"].lower()
        ]

    def import_protocol(
        self,
        organization_id: int,
        protocol_id_ext: str,
    ) -> Optional[ImportedProtocol]:
        p = next((proto for proto in CURATED_PROTOCOLS_IO if proto["protocol_id_ext"] == protocol_id_ext), None)
        if not p:
            return None

        record = ImportedProtocol(
            organization_id=organization_id,
            protocol_id_ext=p["protocol_id_ext"],
            title=p["title"],
            authors=p["authors"],
            doi=p["doi"],
            description=p["description"],
            steps_json=json.dumps(p["steps"]),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_imported_protocols(self, organization_id: int) -> List[ImportedProtocol]:
        stmt = select(ImportedProtocol).where(ImportedProtocol.organization_id == organization_id)
        return list(self.db.scalars(stmt).all())

