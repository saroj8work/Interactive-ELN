import math
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from .models import Compound

# IUPAC standard atomic weights (g/mol)
ATOMIC_WEIGHTS = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "P": 30.974,
    "S": 32.065,
    "Cl": 35.453,
    "Br": 79.904,
    "I": 126.904,
    "Na": 22.990,
    "K": 39.098,
    "Ca": 40.078,
    "Fe": 55.845,
    "Zn": 65.38,
}

# Standard valencies for neutral atoms in SMILES
STANDARD_VALENCIES = {
    "C": 4,
    "c": 3,
    "N": 3,
    "n": 2,
    "O": 2,
    "o": 2,
    "S": 2,
    "s": 2,
    "P": 3,
    "p": 3,
    "F": 1,
    "Cl": 1,
    "Br": 1,
    "I": 1,
    "H": 1,
}

# Atom colors for SVG rendering
ATOM_COLORS = {
    "C": "#94a3b8",
    "c": "#94a3b8",
    "O": "#ef4444",
    "o": "#ef4444",
    "N": "#3b82f6",
    "n": "#3b82f6",
    "S": "#eab308",
    "s": "#eab308",
    "P": "#f97316",
    "p": "#f97316",
    "F": "#10b981",
    "Cl": "#10b981",
    "Br": "#b91c1c",
    "I": "#7c3aed",
    "H": "#cbd5e1",
}


def parse_smiles_atoms_and_bonds(smiles: str) -> Tuple[List[Dict[str, Any]], List[Tuple[int, int, int]]]:
    """
    Parses a SMILES string into a graph of atoms and bonds.
    Returns:
        atoms: list of dicts with atom symbol, aromatic flag, ring connections, etc.
        bonds: list of (atom_idx_1, atom_idx_2, bond_order)
    """
    cleaned = re.sub(r"\[([^\]]+)\]", lambda m: m.group(1), smiles) # simplify bracket atoms for initial parsing
    atoms = []
    bonds = []
    
    # Track branch stack and ring closures
    branch_stack: List[int] = []
    prev_atom_idx: Optional[int] = None
    ring_openings: Dict[int, Tuple[int, int]] = {} # ring_digit -> (atom_idx, bond_order)
    current_bond_order = 1

    i = 0
    n = len(cleaned)
    while i < n:
        char = cleaned[i]

        if char == "(":
            if prev_atom_idx is not None:
                branch_stack.append(prev_atom_idx)
            i += 1
            continue
        elif char == ")":
            if branch_stack:
                prev_atom_idx = branch_stack.pop()
            i += 1
            continue
        elif char == "=":
            current_bond_order = 2
            i += 1
            continue
        elif char == "#":
            current_bond_order = 3
            i += 1
            continue
        elif char == ":":
            current_bond_order = 1
            i += 1
            continue
        elif char.isdigit():
            ring_num = int(char)
            curr_idx = len(atoms) - 1
            if ring_num in ring_openings:
                orig_idx, b_order = ring_openings.pop(ring_num)
                bonds.append((orig_idx, curr_idx, b_order))
            else:
                ring_openings[ring_num] = (curr_idx, current_bond_order)
            current_bond_order = 1
            i += 1
            continue

        # Check two-letter element like Cl, Br
        symbol = None
        if i + 1 < n and cleaned[i:i+2] in ["Cl", "Br", "Na", "Ca", "Fe", "Zn"]:
            symbol = cleaned[i:i+2]
            i += 2
        elif char.isalpha():
            symbol = char
            i += 1
        else:
            i += 1
            continue

        if symbol:
            is_aromatic = symbol.islower()
            element = symbol.capitalize()
            atom_idx = len(atoms)
            atoms.append({
                "index": atom_idx,
                "symbol": symbol,
                "element": element,
                "is_aromatic": is_aromatic,
            })

            if prev_atom_idx is not None:
                bonds.append((prev_atom_idx, atom_idx, current_bond_order))

            prev_atom_idx = atom_idx
            current_bond_order = 1

    return atoms, bonds


def calculate_molecular_properties(smiles: str, atoms: List[Dict[str, Any]], bonds: List[Tuple[int, int, int]]) -> Dict[str, Any]:
    # Calculate explicit and implicit hydrogens
    # Count bonds per atom
    atom_bonds: Dict[int, int] = {a["index"]: 0 for a in atoms}
    for u, v, order in bonds:
        atom_bonds[u] = atom_bonds.get(u, 0) + order
        atom_bonds[v] = atom_bonds.get(v, 0) + order

    element_counts: Dict[str, int] = {}
    implicit_h_count = 0
    hbd = 0
    hba = 0
    rotatable_bonds = 0
    tpsa = 0.0

    # Calculate atom contributions
    for a in atoms:
        elem = a["element"]
        idx = a["index"]
        element_counts[elem] = element_counts.get(elem, 0) + 1

        valency = STANDARD_VALENCIES.get(a["symbol"], 4)
        current_bonds = atom_bonds.get(idx, 0)
        h_count = max(0, valency - current_bonds)
        implicit_h_count += h_count

        # H-bond donors: -OH, -NH, -NH2
        if elem in ["O", "N"] and h_count > 0:
            hbd += h_count

        # H-bond acceptors: N or O
        if elem in ["O", "N"]:
            hba += 1

        # TPSA contributions
        if elem == "O":
            tpsa += 20.23 if h_count == 1 else (9.23 if h_count == 0 else 23.06)
        elif elem == "N":
            tpsa += 26.02 if h_count >= 2 else (12.03 if h_count == 1 else 3.24)
        elif elem == "P":
            tpsa += 13.59
        elif elem == "S":
            tpsa += 28.24

    # Rotatable bonds: single bonds between heavy non-terminal atoms not in a small ring
    for u, v, order in bonds:
        if order == 1:
            u_elem = atoms[u]["element"]
            v_elem = atoms[v]["element"]
            if u_elem != "H" and v_elem != "H":
                # Check degree
                deg_u = sum(1 for a1, a2, _ in bonds if a1 == u or a2 == u)
                deg_v = sum(1 for a1, a2, _ in bonds if a1 == v or a2 == v)
                if deg_u > 1 and deg_v > 1 and not (atoms[u]["is_aromatic"] and atoms[v]["is_aromatic"]):
                    rotatable_bonds += 1

    element_counts["H"] = element_counts.get("H", 0) + implicit_h_count

    # Hill system formula formatting (C first, then H, then alphabetical)
    formula_parts = []
    if "C" in element_counts:
        c_num = element_counts.pop("C")
        formula_parts.append(f"C{c_num if c_num > 1 else ''}")
        if "H" in element_counts:
            h_num = element_counts.pop("H")
            formula_parts.append(f"H{h_num if h_num > 1 else ''}")
    for elem in sorted(element_counts.keys()):
        num = element_counts[elem]
        formula_parts.append(f"{elem}{num if num > 1 else ''}")
    formula = "".join(formula_parts) or "Unknown"

    # Molecular Weight
    mw = 0.0
    for elem, count in element_counts.items():
        mw += ATOMIC_WEIGHTS.get(elem, 12.0) * count
    # Add back C and H if popped
    if "C" in formula:
        c_m = re.search(r"C(\d+)?", formula)
        if c_m:
            c_count = int(c_m.group(1)) if c_m.group(1) else 1
            mw += ATOMIC_WEIGHTS["C"] * c_count
    if "H" in formula:
        h_m = re.search(r"H(\d+)?", formula)
        if h_m:
            h_count = int(h_m.group(1)) if h_m.group(1) else 1
            mw += ATOMIC_WEIGHTS["H"] * h_count

    # Approximate Wildman-Crippen LogP estimation
    c_count = sum(1 for a in atoms if a["element"] == "C")
    o_count = sum(1 for a in atoms if a["element"] == "O")
    n_count = sum(1 for a in atoms if a["element"] == "N")
    halogen_count = sum(1 for a in atoms if a["element"] in ["F", "Cl", "Br", "I"])
    logp = (c_count * 0.28) + (halogen_count * 0.55) - (o_count * 0.65) - (n_count * 0.45) - 0.15
    logp = round(float(logp), 2)
    mw = round(float(mw), 2)
    tpsa = round(float(tpsa), 2)

    # Lipinski's Rule of Five
    violations = 0
    if mw > 500:
        violations += 1
    if logp > 5.0:
        violations += 1
    if hbd > 5:
        violations += 1
    if hba > 10:
        violations += 1

    drug_likeness_score = round(max(0.1, 1.0 - (violations * 0.25)), 2)

    # GHS Hazard analysis
    ghs_codes = []
    ghs_pictograms = []
    upper_smi = smiles.upper()
    if any(k in upper_smi for k in ["[N+](=O)[O-]", "N(=O)=O", "OO"]):
        ghs_codes.extend(["H240", "H270"])
        ghs_pictograms.extend(["GHS01", "GHS03"]) # Explosive / Oxidizer
    if mw < 120 and c_count >= 1 and o_count <= 1:
        ghs_codes.append("H225") # Highly flammable liquid
        ghs_pictograms.append("GHS02")
    if halogen_count >= 2 or any(k in upper_smi for k in ["C(=O)CL", "N=C=O"]):
        ghs_codes.extend(["H314", "H330"])
        ghs_pictograms.extend(["GHS05", "GHS06"]) # Corrosive / Acute Toxic
    if violations == 0 and not ghs_codes:
        ghs_codes.append("H302") # Harmful if swallowed
        ghs_pictograms.append("GHS07")

    return {
        "formula": formula,
        "molecular_weight": mw,
        "monoisotopic_mass": mw - (implicit_h_count * 0.0005),
        "logp": logp,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable_bonds,
        "tpsa": tpsa,
        "rule_of_five_violations": violations,
        "drug_likeness_score": drug_likeness_score,
        "ghs_hazard_codes": ",".join(dict.fromkeys(ghs_codes)),
        "ghs_pictograms": ",".join(dict.fromkeys(ghs_pictograms)),
    }


def generate_molecule_svg(atoms: List[Dict[str, Any]], bonds: List[Tuple[int, int, int]], width: int = 420, height: int = 280) -> str:
    """
    Generates an aesthetic vector SVG depiction of the molecule using 2D force-directed spring layout.
    """
    n = len(atoms)
    if n == 0:
        return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#0f172a"/><text x="50%" y="50%" fill="#64748b" text-anchor="middle" font-family="sans-serif">No Structure Available</text></svg>'

    # Initialize coordinates in a gentle ring or zigzag
    coords: List[List[float]] = []
    radius = min(width, height) * 0.35
    cx = width / 2.0
    cy = height / 2.0

    for i in range(n):
        angle = (2.0 * math.pi * i) / max(1, n)
        # add slight zigzag for linear chains
        r_offset = 20.0 * (1 if i % 2 == 0 else -1) if n > 6 else 0
        coords.append([cx + (radius + r_offset) * math.cos(angle), cy + (radius + r_offset) * math.sin(angle)])

    # Iterative relaxation (Spring embedder)
    iterations = 60
    k_bond = 0.08
    target_bond_length = 42.0
    c_repulsion = 1200.0

    for _ in range(iterations):
        forces = [[0.0, 0.0] for _ in range(n)]

        # Repulsion between all atom pairs
        for i in range(n):
            for j in range(i + 1, n):
                dx = coords[j][0] - coords[i][0]
                dy = coords[j][1] - coords[i][1]
                dist_sq = dx * dx + dy * dy + 0.1
                dist = math.sqrt(dist_sq)
                rep = c_repulsion / dist_sq
                fx = (dx / dist) * rep
                fy = (dy / dist) * rep
                forces[i][0] -= fx
                forces[i][1] -= fy
                forces[j][0] += fx
                forces[j][1] += fy

        # Bond springs
        for u, v, _ in bonds:
            dx = coords[v][0] - coords[u][0]
            dy = coords[v][1] - coords[u][1]
            dist = math.sqrt(dx * dx + dy * dy) + 0.001
            displacement = dist - target_bond_length
            fx = (dx / dist) * displacement * k_bond
            fy = (dy / dist) * displacement * k_bond
            forces[u][0] += fx
            forces[u][1] += fy
            forces[v][0] -= fx
            forces[v][1] -= fy

        # Update positions
        for i in range(n):
            coords[i][0] += max(-8.0, min(8.0, forces[i][0]))
            coords[i][1] += max(-8.0, min(8.0, forces[i][1]))

    # Normalize within bounding box with padding
    min_x = min(c[0] for c in coords)
    max_x = max(c[0] for c in coords)
    min_y = min(c[1] for c in coords)
    max_y = max(c[1] for c in coords)
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)

    padding = 45.0
    scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)
    offset_x = (width - span_x * scale) / 2.0 - min_x * scale
    offset_y = (height - span_y * scale) / 2.0 - min_y * scale

    for i in range(n):
        coords[i][0] = coords[i][0] * scale + offset_x
        coords[i][1] = coords[i][1] * scale + offset_y

    # Build SVG XML
    svg_elements = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="background:#090d16; border-radius:8px;">',
        '<defs>',
        '  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feGaussianBlur stdDeviation="3" result="blur" />',
        '    <feComposite in="SourceGraphic" in2="blur" operator="over" />',
        '  </filter>',
        '</defs>',
    ]

    # Draw bonds
    for u, v, order in bonds:
        x1, y1 = coords[u][0], coords[u][1]
        x2, y2 = coords[v][0], coords[v][1]

        if order == 1:
            svg_elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="2.5" stroke-linecap="round"/>')
        elif order == 2:
            # Parallel double bond
            dx = x2 - x1
            dy = y2 - y1
            length = math.sqrt(dx * dx + dy * dy) or 1.0
            perp_x = -dy / length * 2.5
            perp_y = dx / length * 2.5
            svg_elements.append(f'<line x1="{x1+perp_x:.1f}" y1="{y1+perp_y:.1f}" x2="{x2+perp_x:.1f}" y2="{y2+perp_y:.1f}" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"/>')
            svg_elements.append(f'<line x1="{x1-perp_x:.1f}" y1="{y1-perp_y:.1f}" x2="{x2-perp_x:.1f}" y2="{y2-perp_y:.1f}" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"/>')
        elif order == 3:
            # Triple bond
            dx = x2 - x1
            dy = y2 - y1
            length = math.sqrt(dx * dx + dy * dy) or 1.0
            perp_x = -dy / length * 3.5
            perp_y = dx / length * 3.5
            svg_elements.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#a855f7" stroke-width="2" stroke-linecap="round"/>')
            svg_elements.append(f'<line x1="{x1+perp_x:.1f}" y1="{y1+perp_y:.1f}" x2="{x2+perp_x:.1f}" y2="{y2+perp_y:.1f}" stroke="#a855f7" stroke-width="1.8" stroke-linecap="round"/>')
            svg_elements.append(f'<line x1="{x1-perp_x:.1f}" y1="{y1-perp_y:.1f}" x2="{x2-perp_x:.1f}" y2="{y2-perp_y:.1f}" stroke="#a855f7" stroke-width="1.8" stroke-linecap="round"/>')

    # Draw atom nodes and labels
    for a in atoms:
        elem = a["element"]
        idx = a["index"]
        x, y = coords[idx][0], coords[idx][1]
        color = ATOM_COLORS.get(elem, "#94a3b8")

        # Carbon vertex circle (small dot) or Heteroatom text label
        if elem == "C":
            svg_elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1e293b" stroke="{color}" stroke-width="2"/>')
        else:
            svg_elements.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#0b1120" stroke="{color}" stroke-width="1.5"/>')
            svg_elements.append(f'<text x="{x:.1f}" y="{y+4.5:.1f}" fill="{color}" text-anchor="middle" font-size="12" font-weight="700" font-family="system-ui, sans-serif">{elem}</text>')

    svg_elements.append("</svg>")
    return "\n".join(svg_elements)


PRESET_COMPOUNDS = [
    {
        "name": "Aspirin (Acetylsalicylic Acid)",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "description": "NSAID inhibitor of COX-1 and COX-2 enzymes",
    },
    {
        "name": "Caffeine",
        "smiles": "Cn1cnc2c1c(=O)n(c(=O)n2C)C",
        "description": "Central nervous system stimulant and adenosine receptor antagonist",
    },
    {
        "name": "Ibuprofen",
        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        "description": "Non-steroidal anti-inflammatory analgesic",
    },
    {
        "name": "Paracetamol (Acetaminophen)",
        "smiles": "CC(=O)Nc1ccc(O)cc1",
        "description": "Antipyretic and analgesic compound",
    },
    {
        "name": "Doxorubicin",
        "smiles": "COC1=C2C(=O)C3=C(C(=O)C2=C(C=C1)O)C(CC(C3)(O)C(=O)CO)OC4CC(C(C(O4)C)O)N",
        "description": "Anthracycline topoisomerase II inhibitor antineoplastic agent",
    },
    {
        "name": "Remdesivir",
        "smiles": "CCC(CC)COC(=O)C(C)NP(=O)(OCC1C(C(C(O1)C#N)C2=CC=C3N2N=CN=C3N)O)OC4=CC=CC=C4",
        "description": "Broad-spectrum nucleoside analog antiviral targeting RNA-dependent RNA polymerase",
    },
]


class CheminformaticsService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_smiles(self, smiles: str, name: str = "Molecule") -> Dict[str, Any]:
        atoms, bonds = parse_smiles_atoms_and_bonds(smiles)
        props = calculate_molecular_properties(smiles, atoms, bonds)
        svg = generate_molecule_svg(atoms, bonds)
        return {
            "name": name,
            "smiles": smiles,
            "svg_depiction": svg,
            **props,
        }

    def save_compound(
        self,
        organization_id: int,
        name: str,
        smiles: str,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
    ) -> Compound:
        analysis = self.analyze_smiles(smiles, name)
        compound = Compound(
            organization_id=organization_id,
            project_id=project_id,
            experiment_id=experiment_id,
            name=name,
            smiles=smiles,
            formula=analysis["formula"],
            molecular_weight=analysis["molecular_weight"],
            monoisotopic_mass=analysis["monoisotopic_mass"],
            logp=analysis["logp"],
            hbd=analysis["hbd"],
            hba=analysis["hba"],
            rotatable_bonds=analysis["rotatable_bonds"],
            tpsa=analysis["tpsa"],
            rule_of_five_violations=analysis["rule_of_five_violations"],
            drug_likeness_score=analysis["drug_likeness_score"],
            ghs_hazard_codes=analysis["ghs_hazard_codes"],
            ghs_pictograms=analysis["ghs_pictograms"],
            svg_depiction=analysis["svg_depiction"],
        )
        self.db.add(compound)
        self.db.commit()
        self.db.refresh(compound)
        return compound

    def list_compounds(
        self,
        organization_id: int,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Compound]:
        stmt = select(Compound).where(Compound.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(Compound.project_id == project_id)
        if experiment_id is not None:
            stmt = stmt.where(Compound.experiment_id == experiment_id)
        if search:
            search_pat = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Compound.name.ilike(search_pat),
                    Compound.formula.ilike(search_pat),
                    Compound.smiles.ilike(search_pat),
                )
            )
        stmt = stmt.order_by(Compound.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_compound(self, compound_id: int, organization_id: int) -> Optional[Compound]:
        stmt = select(Compound).where(Compound.id == compound_id, Compound.organization_id == organization_id)
        return self.db.scalars(stmt).first()

    def delete_compound(self, compound_id: int, organization_id: int) -> bool:
        comp = self.get_compound(compound_id, organization_id)
        if comp:
            self.db.delete(comp)
            self.db.commit()
            return True
        return False

