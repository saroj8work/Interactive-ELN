/**
 * Chemical Substructure and Tanimoto Similarity Search Engine
 * Supports SMILES parsing, functional group queries, formula matching,
 * and topological bit fingerprints.
 */

export interface ChemicalSearchResult {
  id: string | number;
  type: "experiment" | "entry" | "inventory";
  title: string;
  smiles?: string;
  formula?: string;
  mw?: number;
  isSubstructureMatch: boolean;
  similarityScore: number; // 0 to 100%
  matchedGroup?: string;
  referenceId: number;
}

// Canonical functional group fingerprints for common laboratory queries
export const COMMON_FUNCTIONAL_GROUPS: { name: string; smiles: string; pattern: RegExp; description: string }[] = [
  { name: "Benzene / Phenyl Ring", smiles: "c1ccccc1", pattern: /c1ccccc1|C1=CC=CC=C1/i, description: "Aromatic 6-membered ring" },
  { name: "Carboxylic Acid", smiles: "C(=O)O", pattern: /C\(=O\)O|COOH/i, description: "-COOH acid group" },
  { name: "Amide", smiles: "C(=O)N", pattern: /C\(=O\)N|CONH/i, description: "-CONH- peptide / amide bond" },
  { name: "Ester", smiles: "C(=O)OC", pattern: /C\(=O\)O[A-Za-z0-9]/i, description: "-COOR ester group" },
  { name: "Ketone", smiles: "CC(=O)C", pattern: /[A-Za-z0-9]C\(=O\)[A-Za-z0-9]/i, description: "Carbonyl ketone" },
  { name: "Aldehyde", smiles: "C=O", pattern: /C=O|CH=O/i, description: "Carbonyl aldehyde" },
  { name: "Amine (Primary/Secondary)", smiles: "CCN", pattern: /\[NH2\]|\[NH\]|NH2|NH/i, description: "Amine nitrogen group" },
  { name: "Alcohol / Phenol", smiles: "CO", pattern: /\[OH\]|OH/i, description: "Hydroxyl group -OH" },
  { name: "Halide (F, Cl, Br, I)", smiles: "CCl", pattern: /F|Cl|Br|I/i, description: "Halogen substituent" },
  { name: "Nitro Group", smiles: "[N+](=O)[O-]", pattern: /\[N\+\]\(=O\)\[O-\]|NO2/i, description: "Nitro group -NO2" },
  { name: "Alkyne (Triple Bond)", smiles: "C#C", pattern: /C#C/i, description: "Carbon-carbon triple bond" },
  { name: "Pyridine Ring", smiles: "c1ccncc1", pattern: /c1ccncc1/i, description: "Heteroaromatic pyridine" },
];

/**
 * Generate a 64-bit pseudo-fingerprint array from a chemical structure (SMILES or Formula)
 */
export function generateFingerprint(input: string): boolean[] {
  const fp = new Array(64).fill(false);
  const str = input.trim();
  if (!str) return fp;

  // Bit 0-11: Common functional groups
  COMMON_FUNCTIONAL_GROUPS.forEach((fg, idx) => {
    if (fg.pattern.test(str) || str.toLowerCase().includes(fg.smiles.toLowerCase())) {
      fp[idx] = true;
    }
  });

  // Bit 12-25: Heteroatom presence
  if (/O/i.test(str)) fp[12] = true;
  if (/N/i.test(str)) fp[13] = true;
  if (/S/i.test(str)) fp[14] = true;
  if (/P/i.test(str)) fp[15] = true;
  if (/F/i.test(str)) fp[16] = true;
  if (/Cl/i.test(str)) fp[17] = true;
  if (/Br/i.test(str)) fp[18] = true;
  if (/I/i.test(str)) fp[19] = true;
  if (/B/i.test(str)) fp[20] = true;
  if (/Si/i.test(str)) fp[21] = true;

  // Bit 26-35: Ring sizes and aromatics
  if (/c|n|o|s/.test(str)) fp[26] = true; // lowercase aromatic atoms
  if (/1/.test(str)) fp[27] = true; // Ring 1
  if (/2/.test(str)) fp[28] = true; // Ring 2
  if (/3/.test(str)) fp[29] = true; // Ring 3
  if (/=/i.test(str)) fp[30] = true; // Double bond
  if (/#/i.test(str)) fp[31] = true; // Triple bond
  if (/@/i.test(str)) fp[32] = true; // Chiral center

  // Bit 36-63: Character bigram hashing
  const clean = str.replace(/[^A-Za-z0-9#=()]/g, "");
  for (let i = 0; i < clean.length - 1; i++) {
    const bigram = clean.slice(i, i + 2);
    let hash = 0;
    for (let c = 0; c < bigram.length; c++) {
      hash = (hash * 31 + bigram.charCodeAt(c)) & 0xffffffff;
    }
    const bitPos = 36 + (Math.abs(hash) % 28);
    fp[bitPos] = true;
  }

  return fp;
}

/**
 * Calculate Tanimoto Similarity between two structures (0.0 to 1.0)
 */
export function calculateTanimotoSimilarity(str1: string, str2: string): number {
  if (!str1 || !str2) return 0;
  if (str1.toLowerCase() === str2.toLowerCase()) return 1.0;

  const fp1 = generateFingerprint(str1);
  const fp2 = generateFingerprint(str2);

  let both = 0;
  let either = 0;

  for (let i = 0; i < fp1.length; i++) {
    if (fp1[i] && fp2[i]) both++;
    if (fp1[i] || fp2[i]) either++;
  }

  return either === 0 ? 0 : both / either;
}

/**
 * Check if query is a substructure of target
 */
export function isSubstructure(query: string, target: string): boolean {
  if (!query || !target) return false;
  const qClean = query.trim().toLowerCase();
  const tClean = target.trim().toLowerCase();

  // Exact substring check
  if (tClean.includes(qClean)) return true;

  // Check matching functional group pattern
  const matchedFg = COMMON_FUNCTIONAL_GROUPS.find(
    (fg) => fg.smiles.toLowerCase() === qClean || fg.name.toLowerCase() === qClean
  );
  if (matchedFg) {
    return matchedFg.pattern.test(target);
  }

  // Check fingerprint containment (all 1 bits of query must be in target)
  const fpQuery = generateFingerprint(query);
  const fpTarget = generateFingerprint(target);

  for (let i = 0; i < fpQuery.length; i++) {
    if (fpQuery[i] && !fpTarget[i]) {
      return false;
    }
  }

  return true;
}

