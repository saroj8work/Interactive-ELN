import math
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from .models import MolecularSequence


STANDARD_GENETIC_CODE = {
    "ATA": "I", "ATC": "I", "ATT": "I", "ATG": "M",
    "ACA": "T", "ACC": "T", "ACG": "T", "ACT": "T",
    "AAC": "N", "AAT": "N", "AAA": "K", "AAG": "K",
    "AGC": "S", "AGT": "S", "AGA": "R", "AGG": "R",
    "CTA": "L", "CTC": "L", "CTG": "L", "CTT": "L",
    "CCA": "P", "CCC": "P", "CCG": "P", "CCT": "P",
    "CAC": "H", "CAT": "H", "CAA": "Q", "CAG": "Q",
    "CGA": "R", "CGC": "R", "CGG": "R", "CGT": "R",
    "GTA": "V", "GTC": "V", "GTG": "V", "GTT": "V",
    "GCA": "A", "GCC": "A", "GCG": "A", "GCT": "A",
    "GAC": "D", "GAT": "D", "GAA": "E", "GAG": "E",
    "GGA": "G", "GGC": "G", "GGG": "G", "GGT": "G",
    "TCA": "S", "TCC": "S", "TCG": "S", "TCT": "S",
    "TTC": "F", "TTT": "F", "TTA": "L", "TTG": "L",
    "TAC": "Y", "TAT": "Y", "TAA": "*", "TAG": "*",
    "TGC": "C", "TGT": "C", "TGA": "*", "TGG": "W",
}

RESTRICTION_ENZYMES = [
    {"name": "EcoRI", "motif": "GAATTC", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "BamHI", "motif": "GGATCC", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "HindIII", "motif": "AAGCTT", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "XhoI", "motif": "CTCGAG", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "NotI", "motif": "GCGGCCGC", "cut_offset": 2, "overhang": "5'", "type": "sticky"},
    {"name": "BglII", "motif": "AGATCT", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "PstI", "motif": "CTGCAG", "cut_offset": 5, "overhang": "3'", "type": "sticky"},
    {"name": "SalI", "motif": "GTCGAC", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "NdeI", "motif": "CATATG", "cut_offset": 2, "overhang": "5'", "type": "sticky"},
    {"name": "XbaI", "motif": "TCTAGA", "cut_offset": 1, "overhang": "5'", "type": "sticky"},
    {"name": "EcoRV", "motif": "GATATC", "cut_offset": 3, "overhang": "blunt", "type": "blunt"},
    {"name": "SmaI", "motif": "CCCGGG", "cut_offset": 3, "overhang": "blunt", "type": "blunt"},
    {"name": "KpnI", "motif": "GGTACC", "cut_offset": 5, "overhang": "3'", "type": "sticky"},
]

COMPLEMENT_MAP = str.maketrans("ATCGURYKMBDHVN", "TAGCAYRMKVHDBN")


def clean_sequence(raw: str) -> str:
    # Remove fasta headers if present
    lines = raw.strip().splitlines()
    seq_lines = [l.strip() for l in lines if not l.strip().startswith(">")]
    seq = "".join(seq_lines).upper()
    return re.sub(r"[^A-Z]", "", seq)


def reverse_complement(seq: str) -> str:
    return seq.translate(COMPLEMENT_MAP)[::-1]


def calculate_melting_temperature(seq: str) -> float:
    n = len(seq)
    if n == 0:
        return 0.0
    a_count = seq.count("A")
    t_count = seq.count("T")
    g_count = seq.count("G")
    c_count = seq.count("C")
    
    if n < 14:
        # Wallace rule
        tm = (a_count + t_count) * 2.0 + (g_count + c_count) * 4.0
    else:
        # Marmur and Doty salt-adjusted approximation formula
        gc_count = g_count + c_count
        tm = 64.9 + 41.0 * (gc_count - 16.4) / float(n)
    return round(float(tm), 2)


def calculate_sequence_stats(seq: str, seq_type: str = "dna") -> Dict[str, Any]:
    n = len(seq)
    if n == 0:
        return {
            "length": 0,
            "gc_content": 0.0,
            "melting_temp": 0.0,
            "molecular_weight": 0.0,
            "base_counts": {},
        }

    counts = {
        "A": seq.count("A"),
        "T": seq.count("T"),
        "C": seq.count("C"),
        "G": seq.count("G"),
    }
    ambiguous = n - sum(counts.values())
    if ambiguous > 0:
        counts["Other"] = ambiguous

    gc_sum = counts.get("G", 0) + counts.get("C", 0)
    at_sum = counts.get("A", 0) + counts.get("T", 0)
    total_canonical = gc_sum + at_sum
    gc_percent = round((gc_sum / float(total_canonical or 1)) * 100.0, 2)
    tm = calculate_melting_temperature(seq)

    # MW calculation
    if seq_type == "dna":
        mw = (counts["A"] * 313.21) + (counts["T"] * 304.2) + (counts["C"] * 289.18) + (counts["G"] * 329.21) - 61.96
    elif seq_type == "rna":
        mw = (counts["A"] * 329.21) + (counts.get("U", seq.count("T")) * 306.17) + (counts["C"] * 305.18) + (counts["G"] * 345.21) + 159.0
    else:
        # Protein average 110 Da per aa
        mw = n * 110.0

    return {
        "length": n,
        "gc_content": gc_percent,
        "melting_temp": tm,
        "molecular_weight": round(float(mw), 2),
        "base_counts": counts,
        "reverse_complement": reverse_complement(seq) if seq_type == "dna" else "",
    }


def perform_restriction_digest(seq: str, enzyme_names: List[str], topology: str = "linear") -> Dict[str, Any]:
    n = len(seq)
    cut_sites: List[Dict[str, Any]] = []

    target_enzymes = [e for e in RESTRICTION_ENZYMES if not enzyme_names or e["name"] in enzyme_names]

    # Handle circular sequence wrap-around for motif matching
    extended_seq = seq + seq[:20] if topology == "circular" else seq

    for enz in target_enzymes:
        motif = enz["motif"]
        offset = enz["cut_offset"]
        for match in re.finditer(motif, extended_seq):
            site_pos = match.start() + offset
            if site_pos < n:
                cut_sites.append({
                    "enzyme": enz["name"],
                    "position": site_pos, # 1-based or 0-based coordinate
                    "motif": motif,
                    "overhang": enz["overhang"],
                    "type": enz["type"],
                })

    # Sort cut positions
    cut_sites.sort(key=lambda s: s["position"])

    # Calculate fragments
    unique_cut_positions = sorted(list(set(s["position"] for s in cut_sites)))
    fragments: List[Dict[str, Any]] = []

    if not unique_cut_positions:
        fragments.append({
            "start": 0,
            "end": n,
            "length": n,
            "label": "Full Length (Undigested)",
        })
    else:
        if topology == "circular":
            # Circular fragments
            for i in range(len(unique_cut_positions)):
                start = unique_cut_positions[i]
                end = unique_cut_positions[(i + 1) % len(unique_cut_positions)]
                frag_len = (end - start) if end > start else (n - start + end)
                fragments.append({
                    "start": start,
                    "end": end,
                    "length": frag_len,
                    "label": f"Fragment {i+1} ({frag_len} bp)",
                })
        else:
            # Linear fragments
            prev = 0
            for i, pos in enumerate(unique_cut_positions):
                frag_len = pos - prev
                fragments.append({
                    "start": prev,
                    "end": pos,
                    "length": frag_len,
                    "label": f"Fragment {i+1} ({frag_len} bp)",
                })
                prev = pos
            # Final linear tail
            if prev < n:
                frag_len = n - prev
                fragments.append({
                    "start": prev,
                    "end": n,
                    "length": frag_len,
                    "label": f"Fragment {len(unique_cut_positions)+1} ({frag_len} bp)",
                })

    # Sort fragments largest to smallest like a gel
    fragments.sort(key=lambda f: f["length"], reverse=True)

    # Calculate relative migration distance in 1% agarose gel
    max_len = max((f["length"] for f in fragments), default=n)
    for f in fragments:
        # migration approx ~ log(max_len / f["length"])
        ratio = max(0.05, f["length"] / float(max_len or 1))
        # 0 = top of gel, 100 = bottom of gel
        f["migration_percent"] = round(10.0 + (1.0 - math.log10(ratio * 9.0 + 1.0)) * 80.0, 1)

    return {
        "sequence_length": n,
        "topology": topology,
        "total_cut_sites": len(cut_sites),
        "cut_sites": cut_sites,
        "fragments": fragments,
    }


def find_open_reading_frames(seq: str, min_length_aa: int = 30) -> List[Dict[str, Any]]:
    n = len(seq)
    rev_seq = reverse_complement(seq)
    orfs: List[Dict[str, Any]] = []

    strands = [("+", seq), ("-", rev_seq)]

    for strand, s in strands:
        for frame in range(3):
            codons = [s[i:i+3] for i in range(frame, len(s) - 2, 3)]
            current_start_codon_idx: Optional[int] = None

            for idx, codon in enumerate(codons):
                if codon == "ATG" and current_start_codon_idx is None:
                    current_start_codon_idx = idx
                elif codon in ["TAA", "TAG", "TGA"] and current_start_codon_idx is not None:
                    orf_codons = codons[current_start_codon_idx : idx]
                    if len(orf_codons) >= min_length_aa:
                        aa_seq = "".join(STANDARD_GENETIC_CODE.get(c, "X") for c in orf_codons)
                        start_pos = frame + (current_start_codon_idx * 3)
                        end_pos = frame + (idx * 3) + 3

                        if strand == "-":
                            # Map coordinates back to forward strand
                            orig_start = n - end_pos
                            orig_end = n - start_pos
                        else:
                            orig_start = start_pos
                            orig_end = end_pos

                        orfs.append({
                            "strand": strand,
                            "frame": f"{strand}{frame + 1}",
                            "start": orig_start,
                            "end": orig_end,
                            "length_bp": len(orf_codons) * 3 + 3,
                            "length_aa": len(aa_seq),
                            "protein_sequence": aa_seq,
                        })
                    current_start_codon_idx = None

    orfs.sort(key=lambda o: o["length_aa"], reverse=True)
    return orfs


def check_primer_pair(forward_primer: str, reverse_primer: str) -> Dict[str, Any]:
    f_clean = clean_sequence(forward_primer)
    r_clean = clean_sequence(reverse_primer)

    f_stats = calculate_sequence_stats(f_clean)
    r_stats = calculate_sequence_stats(r_clean)

    tm_diff = round(abs(f_stats["melting_temp"] - r_stats["melting_temp"]), 2)

    # 3' GC clamp check
    f_3prime_clamp = sum(1 for b in f_clean[-5:] if b in ["G", "C"])
    r_3prime_clamp = sum(1 for b in r_clean[-5:] if b in ["G", "C"])

    warnings = []
    if tm_diff > 5.0:
        warnings.append(f"Melting temperature difference (ΔTm = {tm_diff}°C) exceeds recommended 5°C limit.")
    if f_stats["length"] < 18 or f_stats["length"] > 30:
        warnings.append(f"Forward primer length ({f_stats['length']} nt) is outside optimal 18-30 nt window.")
    if r_stats["length"] < 18 or r_stats["length"] > 30:
        warnings.append(f"Reverse primer length ({r_stats['length']} nt) is outside optimal 18-30 nt window.")
    if f_stats["gc_content"] < 40 or f_stats["gc_content"] > 60:
        warnings.append(f"Forward primer GC% ({f_stats['gc_content']}%) is outside optimal 40-60% range.")
    if r_stats["gc_content"] < 40 or r_stats["gc_content"] > 60:
        warnings.append(f"Reverse primer GC% ({r_stats['gc_content']}%) is outside optimal 40-60% range.")

    quality_score = max(0, 100 - (len(warnings) * 20))

    return {
        "forward": {
            "sequence": f_clean,
            **f_stats,
            "gc_clamp_score": f_3prime_clamp,
        },
        "reverse": {
            "sequence": r_clean,
            **r_stats,
            "gc_clamp_score": r_3prime_clamp,
        },
        "tm_difference": tm_diff,
        "quality_score": quality_score,
        "warnings": warnings,
        "recommended_annealing_temp": round(min(f_stats["melting_temp"], r_stats["melting_temp"]) - 5.0, 1),
    }


PRESET_SEQUENCES = [
    {
        "name": "GFP (Green Fluorescent Protein) CDS",
        "topology": "linear",
        "sequence": "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGCCACAACGTCTATATCATGGCCGACAAGCAGAAGAACGGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCATCGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA",
        "description": "Aequorea victoria enhanced green fluorescent protein coding sequence (720 bp)",
    },
    {
        "name": "pUC19 Multiple Cloning Site (MCS) Region",
        "topology": "circular",
        "sequence": "AGCTTGCATGCCTGCAGGTCGACTCTAGAGGATCCCCGGGTACCGAGCTCGAATTCACTGGCCGTCGTTTTACAACGTCGTGACTGGGAAAACCCTGGCGTTACCCAACTTAATCGCCTTGCAGCACATCCCCCTTTCGCCAGCTGGCGTAATAGCGAAGAGGCCCGCACCGATCGCCCTTCCCAACAGTTGCGCAGCCTGAATGGCGAATGGCGCCTGATGCGGTATTTTCTCCTTACGCATCTGTGCGGTATTTCACACCGCATATGGTGCACTCTCAGTACAATCTGCTCTGATGCCGCATAGTTAAGCCAGCCCCGACACCCGCCAACACCCGCTGACGCGCCCTGACGGGCTTGTCTGCTCCCGGCATCCGCTTACAGACAAGCTGTGACCGTCTCCGGGAGCTGCATGTGTCAGAGGTTTTCACCGTCATCACCGAAACGCGCGAGACGAAAGGGCCTCGTGATACGCCTATTTTTATAGGTTAATGTCATGATAATAATGGTTTCTTAGACGTCAGGTGGCACTTTTCGGGGAAATGTGCGCGGAACCCCTATTTGTTTATTTTTCTAAATACATTCAAATATGTATCCGCTCATGAGACAATAACCCTGATAAATGCTTCAATAATATTGAAAAAGGAAGAGTATGAGTATTCAACATTTCCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTGTTTTTGCTCACCCAGAAACGCTGGTGAAAGTAAAAGATGCTGAAGATCAGTTGGGTGCACGAGTGGGTTACATCGAACTGGATCTCAACAGCGGTAAGATCCTTGAGAGTTTTCGCCCCGAAGAACGTTTTCCAATGATGAGCACTTTTAAAGTTCTGCTATGTGGCGCGGTATTATCCCGTATTGACGCCGGGCAAGAGCAACTCGGTCGCCGCATACACTATTCTCAGAATGACTTGGTTGAGTACTCACCAGTCACAGAAAAGCATCTTACGGATGGCATGACAGTAAGAGAATTATGCAGTGCTGCCATAACCATGAGTGATAACACTGCGGCCAACTTACTTCTGACAACGATCGGAGGACCGAAGGAGCTAACCGCTTTTTTGCACAACATGGGGGATCATGTAACTCGCCTTGATCGTTGGGAACCGGAGCTGAATGAAGCCATACCAAACGACGAGCGTGACACCACGATGCCTGTAGCAATGGCAACAACGTTGCGCAAACTATTAACTGGCGAACTACTTACTCTAGCTTCCCGGCAACAATTAATAGACTGGATGGAGGCGGATAAAGTTGCAGGACCACTTCTGCGCTCGGCCCTTCCGGCTGGCTGGTTTATTGCTGATAAATCTGGAGCCGGTGAGCGTGGGTCTCGCGGTATCATTGCAGCACTGGGGCCAGATGGTAAGCCCTCCCGTATCGTAGTTATCTACACGACGGGGAGTCAGGCAACTATGGATGAACGAAATAGACAGATCGCTGAGATAGGTGCCTCACTGATTAAGCATTGGTAA",
        "description": "Standard high-copy cloning vector MCS and beta-lactamase cassette (1350 bp)",
    },
]


class MolecularService:
    def __init__(self, db: Session):
        self.db = db

    def analyze_sequence(self, raw_seq: str, name: str = "Sequence", seq_type: str = "dna") -> Dict[str, Any]:
        seq = clean_sequence(raw_seq)
        stats = calculate_sequence_stats(seq, seq_type)
        return {
            "name": name,
            "sequence": seq,
            "sequence_type": seq_type,
            **stats,
        }

    def digest(self, raw_seq: str, enzyme_names: List[str], topology: str = "linear") -> Dict[str, Any]:
        seq = clean_sequence(raw_seq)
        return perform_restriction_digest(seq, enzyme_names, topology)

    def find_orfs(self, raw_seq: str, min_aa: int = 30) -> List[Dict[str, Any]]:
        seq = clean_sequence(raw_seq)
        return find_open_reading_frames(seq, min_aa)

    def test_primers(self, fwd: str, rev: str) -> Dict[str, Any]:
        return check_primer_pair(fwd, rev)

    def save_sequence(
        self,
        organization_id: int,
        name: str,
        sequence_data: str,
        sequence_type: str = "dna",
        topology: str = "linear",
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        description: str = "",
    ) -> MolecularSequence:
        cleaned = clean_sequence(sequence_data)
        stats = calculate_sequence_stats(cleaned, sequence_type)
        record = MolecularSequence(
            organization_id=organization_id,
            project_id=project_id,
            experiment_id=experiment_id,
            name=name,
            sequence_type=sequence_type,
            topology=topology,
            sequence_data=cleaned,
            length=stats["length"],
            gc_content=stats["gc_content"],
            melting_temp=stats["melting_temp"],
            molecular_weight=stats["molecular_weight"],
            description=description,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_sequences(
        self,
        organization_id: int,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[MolecularSequence]:
        stmt = select(MolecularSequence).where(MolecularSequence.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(MolecularSequence.project_id == project_id)
        if experiment_id is not None:
            stmt = stmt.where(MolecularSequence.experiment_id == experiment_id)
        if search:
            stmt = stmt.where(
                or_(
                    MolecularSequence.name.ilike(f"%{search}%"),
                    MolecularSequence.description.ilike(f"%{search}%"),
                )
            )
        stmt = stmt.order_by(MolecularSequence.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_sequence(self, sequence_id: int, organization_id: int) -> Optional[MolecularSequence]:
        stmt = select(MolecularSequence).where(
            MolecularSequence.id == sequence_id,
            MolecularSequence.organization_id == organization_id,
        )
        return self.db.scalars(stmt).first()

    def delete_sequence(self, sequence_id: int, organization_id: int) -> bool:
        rec = self.get_sequence(sequence_id, organization_id)
        if rec:
            self.db.delete(rec)
            self.db.commit()
            return True
        return False

