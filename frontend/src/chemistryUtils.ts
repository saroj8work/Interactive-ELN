// Chemical elements and standard atomic weights (IUPAC)
export const ATOMIC_WEIGHTS: Record<string, number> = {
  H: 1.008,
  He: 4.0026,
  Li: 6.94,
  Be: 9.0122,
  B: 10.81,
  C: 12.011,
  N: 14.007,
  O: 15.999,
  F: 18.9984,
  Ne: 20.1797,
  Na: 22.9898,
  Mg: 24.305,
  Al: 26.9815,
  Si: 28.085,
  P: 30.9738,
  S: 32.06,
  Cl: 35.45,
  Ar: 39.948,
  K: 39.0983,
  Ca: 40.078,
  Sc: 44.9559,
  Ti: 47.867,
  V: 50.9415,
  Cr: 51.9961,
  Mn: 54.938,
  Fe: 55.845,
  Co: 58.9332,
  Ni: 58.6934,
  Cu: 63.546,
  Zn: 65.38,
  Ga: 69.723,
  Ge: 72.63,
  As: 74.9216,
  Se: 78.96,
  Br: 79.904,
  Kr: 83.798,
  Rb: 85.4678,
  Sr: 87.62,
  Y: 88.9058,
  Zr: 91.224,
  Nb: 92.9064,
  Mo: 95.95,
  Ru: 101.07,
  Rh: 102.9055,
  Pd: 106.42,
  Ag: 107.8682,
  Cd: 112.411,
  In: 114.818,
  Sn: 118.71,
  Sb: 121.76,
  Te: 127.6,
  I: 126.9045,
  Xe: 131.293,
  Cs: 132.9055,
  Ba: 137.327,
  La: 138.9055,
  Ce: 140.116,
  Pt: 195.084,
  Au: 196.9666,
  Hg: 200.592,
  Pb: 207.2,
  Bi: 208.9804,
};

export interface FormulaResult {
  formula: string;
  hillFormula: string;
  molecularWeight: number;
  atomCounts: Record<string, number>;
}

/**
 * Parses a chemical formula (supports parentheses, brackets, e.g. "C6H12O6", "(CH3)2CHOH", "Pd(PPh3)4", "Fe2(SO4)3").
 */
export function parseChemicalFormula(input: string): FormulaResult | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  type Counts = Record<string, number>;
  const stack: Counts[] = [{}];

  let i = 0;
  const n = trimmed.length;

  while (i < n) {
    const char = trimmed[i];

    if (char === "(" || char === "[" || char === "{") {
      stack.push({});
      i++;
    } else if (char === ")" || char === "]" || char === "}") {
      if (stack.length <= 1) return null; // Unbalanced
      const top = stack.pop()!;
      i++;

      // Check for multiplier number following closing bracket
      let numStr = "";
      while (i < n && /\d/.test(trimmed[i])) {
        numStr += trimmed[i];
        i++;
      }
      const multiplier = numStr ? parseInt(numStr, 10) : 1;

      const current = stack[stack.length - 1];
      for (const [elem, count] of Object.entries(top)) {
        current[elem] = (current[elem] ?? 0) + count * multiplier;
      }
    } else if (/[A-Z]/.test(char)) {
      // Element symbol
      let symbol = char;
      i++;
      if (i < n && /[a-z]/.test(trimmed[i])) {
        symbol += trimmed[i];
        i++;
      }

      // Check if valid element
      if (!ATOMIC_WEIGHTS[symbol]) {
        return null;
      }

      // Number count
      let numStr = "";
      while (i < n && /\d/.test(trimmed[i])) {
        numStr += trimmed[i];
        i++;
      }
      const count = numStr ? parseInt(numStr, 10) : 1;

      const current = stack[stack.length - 1];
      current[symbol] = (current[symbol] ?? 0) + count;
    } else if (/\s/.test(char) || char === "." || char === "·") {
      // Hydrate dot or space
      i++;
    } else {
      // Invalid character
      return null;
    }
  }

  if (stack.length !== 1) return null; // Unbalanced brackets
  const finalCounts = stack[0];

  // Calculate molecular weight
  let totalMw = 0;
  for (const [elem, count] of Object.entries(finalCounts)) {
    const weight = ATOMIC_WEIGHTS[elem];
    if (!weight) return null;
    totalMw += weight * count;
  }

  // Format into Hill System formula: C first, H second, then alphabetical
  const elements = Object.keys(finalCounts);
  const hasCarbon = "C" in finalCounts;

  const sortedElements = elements.sort((a, b) => {
    if (hasCarbon) {
      if (a === "C") return -1;
      if (b === "C") return 1;
      if (a === "H") return -1;
      if (b === "H") return 1;
    }
    return a.localeCompare(b);
  });

  const hillFormula = sortedElements
    .map((elem) => `${elem}${finalCounts[elem] > 1 ? finalCounts[elem] : ""}`)
    .join("");

  return {
    formula: trimmed,
    hillFormula,
    molecularWeight: Math.round(totalMw * 1000) / 1000,
    atomCounts: finalCounts,
  };
}

export type Atom = { id: number; element: string; formalCharge: number; x: number; y: number };
export type Bond = { id: number; from: number; to: number; order: 1 | 2 | 3 | 4; stereo: 0 | 1 | 4 | 6 };
export type Structure = { atoms: Atom[]; bonds: Bond[] };

const STANDARD_VALENCE: Record<string, number> = {
  H: 1,
  B: 3,
  C: 4,
  N: 3,
  O: 2,
  F: 1,
  Cl: 1,
  Br: 1,
  I: 1,
  Si: 4,
  P: 3, // or 5
  S: 2, // or 6
};

/**
 * Calculates chemical formula, Hill formula, and MW directly from a 2D drawn Structure.
 * Implicit hydrogens are added based on formal charge and standard neutral valence.
 */
export function structureToFormula(structure: Structure): FormulaResult {
  const counts: Record<string, number> = {};

  // Map atom ID to connected bond order sum
  const atomBonds = new Map<number, number>();
  for (const bond of structure.bonds) {
    const orderVal = bond.order === 4 ? 1.5 : bond.order;
    atomBonds.set(bond.from, (atomBonds.get(bond.from) ?? 0) + orderVal);
    atomBonds.set(bond.to, (atomBonds.get(bond.to) ?? 0) + orderVal);
  }

  let totalImplicitH = 0;

  for (const atom of structure.atoms) {
    counts[atom.element] = (counts[atom.element] ?? 0) + 1;

    // Calculate implicit hydrogens for non-hydrogen atoms
    if (atom.element !== "H") {
      const standardValence = STANDARD_VALENCE[atom.element] ?? 4;
      const bondedOrder = atomBonds.get(atom.id) ?? 0;
      // Valence adjusted by charge
      const targetValence = standardValence + atom.formalCharge;
      const implicitH = Math.max(0, Math.round(targetValence - bondedOrder));
      totalImplicitH += implicitH;
    }
  }

  if (totalImplicitH > 0) {
    counts["H"] = (counts["H"] ?? 0) + totalImplicitH;
  }

  let totalMw = 0;
  for (const [elem, count] of Object.entries(counts)) {
    const w = ATOMIC_WEIGHTS[elem] ?? 0;
    totalMw += w * count;
  }

  const elements = Object.keys(counts);
  const hasCarbon = "C" in counts;
  const sorted = elements.sort((a, b) => {
    if (hasCarbon) {
      if (a === "C") return -1;
      if (b === "C") return 1;
      if (a === "H") return -1;
      if (b === "H") return 1;
    }
    return a.localeCompare(b);
  });

  const hillFormula = sorted.map((el) => `${el}${counts[el] > 1 ? counts[el] : ""}`).join("");

  return {
    formula: hillFormula,
    hillFormula,
    molecularWeight: Math.round(totalMw * 1000) / 1000,
    atomCounts: counts,
  };
}

export interface StereocenterInfo {
  atomId: number;
  element: string;
  isChiral: boolean;
  type: "chiral-center" | "pseudo-asymmetric";
  neighborCount: number;
  implicitH: number;
}

/**
 * Detects potential stereocenters (chiral tetrahedral carbons/atoms) in a structure.
 * A tetrahedral carbon with 4 distinct groups (or 3 distinct neighbors + 1 implicit H) is chiral.
 */
export function detectStereocenters(structure: Structure): StereocenterInfo[] {
  const centers: StereocenterInfo[] = [];
  const atomMap = new Map(structure.atoms.map((a) => [a.id, a]));

  // Adjacency map: atomId -> list of { neighborId, bondOrder, stereo }
  const adj = new Map<number, Array<{ neighborId: number; order: number; stereo: number }>>();
  for (const atom of structure.atoms) {
    adj.set(atom.id, []);
  }
  for (const bond of structure.bonds) {
    adj.get(bond.from)?.push({ neighborId: bond.to, order: bond.order, stereo: bond.stereo });
    adj.get(bond.to)?.push({ neighborId: bond.from, order: bond.order, stereo: bond.stereo });
  }

  for (const atom of structure.atoms) {
    // Primarily check Carbon (and Silicon/Nitrogen if substituted)
    if (atom.element !== "C" && atom.element !== "Si") continue;

    const neighbors = adj.get(atom.id) ?? [];
    // Must be sp3: only single bonds (order 1)
    const hasMultipleBonds = neighbors.some((n) => n.order > 1);
    if (hasMultipleBonds) continue;

    const neighborCount = neighbors.length;
    const bondedOrder = neighbors.reduce((acc, n) => acc + n.order, 0);
    const implicitH = Math.max(0, 4 - bondedOrder);

    // To be a candidate for chiral center:
    // Either 4 explicit neighbors OR 3 explicit neighbors + 1 implicit H
    if (neighborCount === 4 || (neighborCount === 3 && implicitH === 1)) {
      // Check whether neighbor branches are distinct
      // Quick constitutional distinction check (elements and direct branch signatures)
      const branchSignatures: string[] = [];

      for (const n of neighbors) {
        const neighborAtom = atomMap.get(n.neighborId);
        if (!neighborAtom) continue;
        const subNeighbors = (adj.get(n.neighborId) ?? [])
          .filter((sn) => sn.neighborId !== atom.id)
          .map((sn) => {
            const el = atomMap.get(sn.neighborId)?.element ?? "?";
            return `${el}(order=${sn.order})`;
          })
          .sort()
          .join("-");
        branchSignatures.push(`${neighborAtom.element}[${subNeighbors}]`);
      }

      if (implicitH === 1) {
        branchSignatures.push("H[implicit]");
      }

      // Check uniqueness of signatures
      const uniqueBranches = new Set(branchSignatures);
      const isChiral = uniqueBranches.size === branchSignatures.length;

      if (isChiral) {
        centers.push({
          atomId: atom.id,
          element: atom.element,
          isChiral: true,
          type: "chiral-center",
          neighborCount,
          implicitH,
        });
      }
    }
  }

  return centers;
}

export interface DoubleBondStereoInfo {
  bondId: number;
  fromId: number;
  toId: number;
  configuration: "E" | "Z" | "unspecified";
}

/**
 * Analyzes double bonds for E/Z or cis/trans geometrical stereochemistry based on 2D coordinates.
 */
export function detectDoubleBondStereo(structure: Structure): DoubleBondStereoInfo[] {
  const result: DoubleBondStereoInfo[] = [];
  const atomMap = new Map(structure.atoms.map((a) => [a.id, a]));

  const adj = new Map<number, number[]>();
  for (const a of structure.atoms) adj.set(a.id, []);
  for (const b of structure.bonds) {
    adj.get(b.from)?.push(b.to);
    adj.get(b.to)?.push(b.from);
  }

  for (const bond of structure.bonds) {
    if (bond.order !== 2) continue; // Only double bonds

    const a1 = atomMap.get(bond.from);
    const a2 = atomMap.get(bond.to);
    if (!a1 || !a2) continue;

    const n1 = (adj.get(bond.from) ?? []).filter((id) => id !== bond.to);
    const n2 = (adj.get(bond.to) ?? []).filter((id) => id !== bond.from);

    // For E/Z consideration, each carbon should have at least 1 other neighbor
    if (n1.length >= 1 && n2.length >= 1) {
      // Vector of double bond
      const dbx = a2.x - a1.x;
      const dby = a2.y - a1.y;

      const sub1 = atomMap.get(n1[0]);
      const sub2 = atomMap.get(n2[0]);

      if (sub1 && sub2) {
        // Cross product / normal side check
        // Vector from a1 to sub1
        const v1x = sub1.x - a1.x;
        const v1y = sub1.y - a1.y;
        const cross1 = dbx * v1y - dby * v1x;

        // Vector from a2 to sub2
        const v2x = sub2.x - a2.x;
        const v2y = sub2.y - a2.y;
        const cross2 = dbx * v2y - dby * v2x;

        // If on same side of the line -> cis / Z, opposite side -> trans / E
        if (Math.sign(cross1) !== 0 && Math.sign(cross2) !== 0) {
          const isSameSide = Math.sign(cross1) === Math.sign(cross2);
          result.push({
            bondId: bond.id,
            fromId: bond.from,
            toId: bond.to,
            configuration: isSameSide ? "Z" : "E",
          });
        }
      }
    }
  }

  return result;
}

