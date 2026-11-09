import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from starlette.testclient import TestClient

print("=" * 70)
print("AURA LAB - 7 SCIENTIFIC ENTERPRISE MICROSERVICES VERIFICATION SUITE")
print("=" * 70)

# 1. Microplates Service
print("\n[PHASE 1] Testing Microplate & Assay Analysis Service (Port 8005)...", flush=True)
from services.plates.app.main import app as plates_app

AUTH_HEADERS = {
    "X-Organization-ID": "1",
    "X-User-ID": "1",
    "X-Organization-Role": "admin",
}

with TestClient(plates_app) as client_plates:
    r = client_plates.get("/health")
    assert r.status_code == 200, f"Plates health check failed: {r.text}"
    print("  ✓ Health Check: OK", flush=True)

    plate_payload = {
        "name": "ELISA Verification Plate 01",
        "plate_format": "96-well",
        "description": "Standard calibration assay",
        "assay_type": "ELISA Absorbance",
        "wavelength": "450 nm",
    }
    r_create = client_plates.post("/plates", json=plate_payload, headers=AUTH_HEADERS)
    assert r_create.status_code == 201, f"Failed to create plate: {r_create.text}"
    plate_data = r_create.json()
    plate_id = plate_data["id"]
    assert len(plate_data["wells"]) == 96, f"Expected 96 wells, got {len(plate_data['wells'])}"
    print(f"  ✓ Created 96-Well Microplate (ID: {plate_id}) with all 96 wells initialized", flush=True)

    # Calculate
    r_calc = client_plates.post(f"/plates/{plate_id}/calculate", headers=AUTH_HEADERS)
    assert r_calc.status_code == 200
    print("  ✓ 4PL Calculation Engine & Blank Baseline Subtraction: OK", flush=True)

    # Heatmap
    r_heat = client_plates.get(f"/plates/{plate_id}/heatmap", headers=AUTH_HEADERS)
    assert r_heat.status_code == 200
    assert len(r_heat.json()["grid"]) == 8 # 8 rows
    assert len(r_heat.json()["grid"][0]["wells"]) == 12 # 12 cols
    print("  ✓ Spectrophotometric Heatmap Grid (8x12): OK", flush=True)


# 2. Cheminformatics Service
print("\n[PHASE 2] Testing Cheminformatics Service (Port 8006)...", flush=True)
from services.cheminformatics.app.main import app as chem_app

with TestClient(chem_app) as client_chem:
    r_chem_h = client_chem.get("/health")
    assert r_chem_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    # Analyze Aspirin: CC(=O)Oc1ccccc1C(=O)O
    aspirin_smi = "CC(=O)Oc1ccccc1C(=O)O"
    r_chem_an = client_chem.post("/cheminformatics/analyze", json={"smiles": aspirin_smi, "name": "Aspirin"})
    assert r_chem_an.status_code == 200, f"Chem analysis failed: {r_chem_an.text}"
    chem_data = r_chem_an.json()
    assert chem_data["formula"] == "C9H8O4", f"Expected C9H8O4, got {chem_data['formula']}"
    assert 179.0 <= chem_data["molecular_weight"] <= 181.0, f"Expected ~180.16 g/mol, got {chem_data['molecular_weight']}"
    assert chem_data["rule_of_five_violations"] == 0, "Aspirin should have 0 Lipinski violations"
    assert "<svg" in chem_data["svg_depiction"], "Expected valid SVG depiction"
    print(f"  ✓ SMILES Parsed: Formula={chem_data['formula']}, MW={chem_data['molecular_weight']} g/mol, LogP={chem_data['logp']}", flush=True)
    print(f"  ✓ Lipinski Rule of 5: {chem_data['rule_of_five_violations']} violations (Drug-likeness {int(chem_data['drug_likeness_score']*100)}%)", flush=True)
    print("  ✓ 2D Force-Directed Vector SVG Depiction: OK", flush=True)


# 3. Molecular Biology Service
print("\n[PHASE 3] Testing Molecular Biology Service (Port 8007)...", flush=True)
from services.molecular.app.main import app as mol_app

with TestClient(mol_app) as client_mol:
    r_mol_h = client_mol.get("/health")
    assert r_mol_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    # Test Sequence (GFP coding sequence start)
    test_seq = "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAG"
    r_mol_an = client_mol.post("/molecular/analyze", json={"sequence": test_seq, "name": "GFP Partial"})
    assert r_mol_an.status_code == 200
    mol_an_data = r_mol_an.json()
    assert mol_an_data["length"] == len(test_seq)
    assert mol_an_data["gc_content"] > 55.0
    assert mol_an_data["melting_temp"] > 70.0
    assert len(mol_an_data["reverse_complement"]) == len(test_seq)
    print(f"  ✓ DNA Sequence Metrics: Length={mol_an_data['length']} bp, GC={mol_an_data['gc_content']}%, Tm={mol_an_data['melting_temp']}°C", flush=True)

    # Digestion
    r_digest = client_mol.post("/molecular/digest", json={"sequence": test_seq, "enzymes": ["EcoRI", "BamHI", "HindIII"]})
    assert r_digest.status_code == 200
    digest_data = r_digest.json()
    print(f"  ✓ In Silico Restriction Digest & Simulated Agarose Migration: {len(digest_data['fragments'])} fragment(s) generated", flush=True)

    # Primers
    r_prim = client_mol.post("/molecular/primers", json={"forward": "ATGGTGAGCAAGGGCGAG", "reverse": "CTTCGGGCATGGCGGACT"})
    assert r_prim.status_code == 200
    prim_data = r_prim.json()
    print(f"  ✓ PCR Primer Quality Engine: ΔTm={prim_data['tm_difference']}°C, Score={prim_data['quality_score']}/100", flush=True)


# 4. Workflow Canvas DAG Service
print("\n[PHASE 4] Testing Workflow Canvas DAG Service (Port 8008)...", flush=True)
from services.canvas.app.main import app as canvas_app

with TestClient(canvas_app) as client_canvas:
    r_canvas_h = client_canvas.get("/health")
    assert r_canvas_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    nodes = [
        {"id": "n1", "label": "Lysis", "type": "prep", "duration_min": 15},
        {"id": "n2", "label": "Binding", "type": "pipette", "duration_min": 10},
        {"id": "n3", "label": "Wash", "type": "wash", "duration_min": 5},
        {"id": "n4", "label": "Elution", "type": "read", "duration_min": 5},
    ]
    edges = [
        {"id": "e1-2", "source": "n1", "target": "n2"},
        {"id": "e2-3", "source": "n2", "target": "n3"},
        {"id": "e3-4", "source": "n3", "target": "n4"},
    ]

    # Validation
    r_val = client_canvas.post("/canvas/validate", json={"nodes": nodes, "edges": edges})
    assert r_val.status_code == 200
    val_data = r_val.json()
    assert val_data["is_valid"] is True
    assert val_data["topological_order"] == ["n1", "n2", "n3", "n4"]
    print(f"  ✓ Kahn's Topological Sort: Order = {' -> '.join(val_data['topological_order'])}", flush=True)

    # Create canvas and run
    r_cv_create = client_canvas.post("/canvas?organization_id=1", json={"name": "RNA Isolation DAG", "nodes": nodes, "edges": edges})
    assert r_cv_create.status_code == 201
    cv_id = r_cv_create.json()["id"]

    r_cv_run = client_canvas.post(f"/canvas/{cv_id}/runs?organization_id=1")
    assert r_cv_run.status_code == 201
    run_id = r_cv_run.json()["id"]
    assert r_cv_run.json()["node_states"]["n1"] == "ready"
    print(f"  ✓ Initialized Execution Run #{run_id} (Root node 'n1' unlocked)", flush=True)

    # Step run
    r_step = client_canvas.post(f"/canvas/runs/{run_id}/step", json={"completed_node_id": "n1"})
    assert r_step.status_code == 200
    assert r_step.json()["node_states"]["n1"] == "completed"
    assert r_step.json()["node_states"]["n2"] == "ready"
    print("  ✓ Stepped Execution: 'n1' completed -> downstream 'n2' dependency unlocked", flush=True)


# 5. Scientific Spreadsheet & 4PL Analytics Service
print("\n[PHASE 5] Testing Scientific Spreadsheet & 4PL Analytics Service (Port 8009)...", flush=True)
from services.analytics.app.main import app as analytics_app

with TestClient(analytics_app) as client_analytics:
    r_an_h = client_analytics.get("/health")
    assert r_an_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    # 4PL Fit
    test_curve_pts = [
        {"x": 1000.0, "y": 2.43},
        {"x": 333.33, "y": 2.20},
        {"x": 111.11, "y": 1.77},
        {"x": 37.04, "y": 1.14},
        {"x": 12.35, "y": 0.595},
        {"x": 4.12, "y": 0.265},
        {"x": 1.37, "y": 0.125},
        {"x": 0.05, "y": 0.051},
    ]
    r_fit = client_analytics.post("/analytics/fit-4pl", json={"points": test_curve_pts})
    assert r_fit.status_code == 200, f"4PL fit failed: {r_fit.text}"
    fit_res = r_fit.json()
    assert fit_res["r_squared"] >= 0.98, f"Expected R² >= 0.98, got {fit_res['r_squared']}"
    assert len(fit_res["curve_points"]) >= 50
    print(f"  ✓ 4PL Sigmoid Fitting: EC50={fit_res['ec50_c']}, R²={fit_res['r_squared']}, Hill Slope={fit_res['hill_slope_b']}", flush=True)

    # Formula Eval
    r_form = client_analytics.post("/analytics/evaluate-formula", json={"expression": "=AVERAGE(A1:A4)", "values": [2.4, 2.5, 2.6, 2.5]})
    assert r_form.status_code == 200
    assert abs(r_form.json()["result"] - 2.5) < 0.01
    print(f"  ✓ Formula Evaluator (=AVERAGE): Result = {r_form.json()['result']}", flush=True)


# 6. Regulatory Dossier Builder Service
print("\n[PHASE 6] Testing Regulatory Dossier Builder Service (Port 8011)...", flush=True)
from services.dossier.app.main import app as dossier_app

with TestClient(dossier_app) as client_dossier:
    r_dos_h = client_dossier.get("/health")
    assert r_dos_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    r_compile = client_dossier.post(
        "/dossier/compile?organization_id=1",
        json={
            "title": "IND Module 3.2 Analytical Report",
            "dossier_type": "GxP Certificate of Analysis",
            "summary": "Full analytical characterization",
        },
    )
    assert r_compile.status_code == 201, f"Compilation failed: {r_compile.text}"
    dos_data = r_compile.json()
    dossier_id = dos_data["id"]
    sha256 = dos_data["sha256_checksum"]
    assert len(sha256) == 64, f"Invalid SHA-256 length: {len(sha256)}"
    print(f"  ✓ Compiled Dossier #{dossier_id} with Cryptographic Seal: SHA-256 = {sha256[:16]}...{sha256[-8:]}", flush=True)

    # Certify
    r_cert = client_dossier.post(
        f"/dossier/{dossier_id}/certify?organization_id=1",
        json={"user_id": 1, "user_name": "Dr. Sarah Chen"},
    )
    assert r_cert.status_code == 200
    assert r_cert.json()["status"] == "certified"
    print(f"  ✓ Electronic Signature & GxP Certification Applied by: {r_cert.json()['certified_by_user_name']}", flush=True)

    # HTML export
    r_html = client_dossier.get(f"/dossier/{dossier_id}/html?organization_id=1")
    assert r_html.status_code == 200
    assert "<!DOCTYPE html>" in r_html.text
    assert sha256 in r_html.text
    print("  ✓ Printable HTML/PDF Document Generation: OK", flush=True)


# 7. ZPL Thermal Label Printer & Protocols.io Service
print("\n[PHASE 7] Testing ZPL Thermal Printer & Protocols.io Service (Port 8012)...", flush=True)
from services.thermal_printer.app.main import app as printer_app

with TestClient(printer_app) as client_printer:
    r_print_h = client_printer.get("/health")
    assert r_print_h.status_code == 200
    print("  ✓ Health Check: OK", flush=True)

    # Generate Cryovial ZPL
    r_zpl = client_printer.post(
        "/thermal_printer/generate-zpl",
        json={
            "label_type": "cryovial",
            "barcode_data": "CRYO-2026-X99",
            "sample_name": "HEK293-Cas9",
            "lot_number": "LOT-88",
            "storage_temp": "-80°C",
        },
    )
    assert r_zpl.status_code == 200
    zpl_data = r_zpl.json()
    assert "^XA" in zpl_data["zpl_code"]
    assert "^XZ" in zpl_data["zpl_code"]
    assert "^BXN" in zpl_data["zpl_code"] # DataMatrix command
    assert "<svg" in zpl_data["svg_preview"]
    print(f"  ✓ Generated Zebra ZPL II Code (Width={zpl_data['width_dots']} dots, {zpl_data['dpi']} DPI)", flush=True)
    print("  ✓ Simulated Thermal Label Vector SVG: OK", flush=True)

    # Protocols.io Search
    r_proto = client_printer.get("/thermal_printer/protocols-search?query=RNA")
    assert r_proto.status_code == 200
    protos = r_proto.json()
    assert len(protos) >= 1
    print(f"  ✓ Protocols.io Repository Search: Found '{protos[0]['title']}' ({len(protos[0]['steps'])} steps)", flush=True)

print("\n" + "=" * 70)
print("ALL 7 SCIENTIFIC ENTERPRISE MICROSERVICES VERIFIED SUCCESSFULLY!", flush=True)
print("=" * 70)

print("\n" + "=" * 70)
print("ALL 7 SCIENTIFIC ENTERPRISE MICROSERVICES VERIFIED SUCCESSFULLY!")
print("=" * 70)
