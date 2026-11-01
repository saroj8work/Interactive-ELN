import { useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { detectStereocenters, detectDoubleBondStereo } from "./chemistryUtils";

export type Atom = { id: number; element: string; formalCharge: number; x: number; y: number };
export type Bond = { id: number; from: number; to: number; order: 1 | 2 | 3 | 4; stereo: 0 | 1 | 4 | 6 };
export type Structure = { atoms: Atom[]; bonds: Bond[] };
type Tool = "atom" | "bond" | "select";

const ELEMENTS = ["C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "H", "B", "Si", "Se", "Na", "K", "Ca", "Mg", "Li", "Al", "Fe", "Cu", "Zn"];
const WIDTH = 840;
const HEIGHT = 320;
const MAX_VALENCE: Record<string, number> = {
  H: 1, B: 3, C: 4, N: 3, O: 2, F: 1, Cl: 1, Br: 1, I: 1,
  Si: 4, P: 5, S: 6, Se: 6,
};
const CHARGED_MAX_VALENCE: Record<string, Record<number, number>> = {
  B: { [-1]: 4, 1: 2 },
  C: { [-1]: 3, 1: 3 },
  N: { [-1]: 2, 1: 4 },
  O: { [-1]: 1, 1: 3 },
  P: { [-1]: 6, 1: 4 },
  S: { [-1]: 5, 1: 5 },
  Se: { [-1]: 5, 1: 5 },
};

function structureIssues(structure: Structure): string[] {
  const issues: string[] = [];
  const atoms = new Map<number, Atom>();
  for (const atom of structure.atoms) {
    if (!Number.isInteger(atom.id) || atoms.has(atom.id)) {
      issues.push("Atom IDs must be unique integers.");
      continue;
    }
    if (!ELEMENTS.includes(atom.element) || !Number.isFinite(atom.x) || !Number.isFinite(atom.y)) {
      issues.push(`Atom ${atom.id} has an unsupported element or invalid coordinates.`);
    }
    if (!Number.isInteger(atom.formalCharge) || atom.formalCharge < -15 || atom.formalCharge > 15) {
      issues.push(`Atom ${atom.id} has an invalid formal charge.`);
    } else if (atom.formalCharge !== 0 && MAX_VALENCE[atom.element] !== undefined
      && CHARGED_MAX_VALENCE[atom.element]?.[atom.formalCharge] === undefined) {
      issues.push(`${atom.element} atom ${atom.id} has a charge state without a supported valence check.`);
    }
    atoms.set(atom.id, atom);
  }

  const bondIds = new Set<number>();
  const pairs = new Set<string>();
  const valence = new Map<number, number>();
  for (const bond of structure.bonds) {
    const pair = [bond.from, bond.to].sort((a, b) => a - b).join(":");
    if (!Number.isInteger(bond.id) || bondIds.has(bond.id)) issues.push("Bond IDs must be unique integers.");
    if (bond.from === bond.to || !atoms.has(bond.from) || !atoms.has(bond.to)) {
      issues.push(`Bond ${bond.id} must connect two different existing atoms.`);
      continue;
    }
    if (pairs.has(pair)) issues.push(`Atoms ${bond.from} and ${bond.to} have duplicate bonds.`);
    if (![1, 2, 3, 4].includes(bond.order)) issues.push(`Bond ${bond.id} has an unsupported bond order.`);
    if (![0, 1, 4, 6].includes(bond.stereo) || (bond.stereo !== 0 && bond.order !== 1)) issues.push(`Bond ${bond.id} has unsupported stereochemistry.`);
    bondIds.add(bond.id);
    pairs.add(pair);
    const contribution = bond.order === 4 ? 1.5 : bond.order;
    valence.set(bond.from, (valence.get(bond.from) ?? 0) + contribution);
    valence.set(bond.to, (valence.get(bond.to) ?? 0) + contribution);
  }
  for (const [atomId, used] of valence) {
    const atom = atoms.get(atomId);
    const maximum = atom
      ? CHARGED_MAX_VALENCE[atom.element]?.[atom.formalCharge] ?? MAX_VALENCE[atom.element]
      : undefined;
    if (maximum !== undefined && used > maximum) {
      issues.push(`${atom?.element} atom ${atomId} has bond order ${used}, above its supported valence of ${maximum}.`);
    }
  }
  return [...new Set(issues)];
}

function moleculeSvg(structure: Structure): string {
  const atoms = new Map(structure.atoms.map((atom) => [atom.id, atom]));
  const lines = structure.bonds.flatMap((bond) => {
    const from = atoms.get(bond.from);
    const to = atoms.get(bond.to);
    if (!from || !to) return [];
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy) || 1;
    const offsetX = (-dy / length) * 4;
    const offsetY = (dx / length) * 4;
    if (bond.order === 1 && bond.stereo !== 0) {
      const px = -dy / length; const py = dx / length;
      if (bond.stereo === 4) {
        const points = Array.from({ length: 9 }, (_, index) => { const ratio = index / 8; const wave = index === 0 || index === 8 ? 0 : (index % 2 ? 1 : -1) * 3; return `${from.x + dx * ratio + px * wave},${from.y + dy * ratio + py * wave}`; }).join(" ");
        return [`<polyline points="${points}" fill="none" />`];
      }
      if (bond.stereo === 1) return [`<polygon points="${from.x},${from.y} ${to.x + px * 5},${to.y + py * 5} ${to.x - px * 5},${to.y - py * 5}" fill="#34443d" stroke="none" />`];
      return Array.from({ length: 7 }, (_, index) => { const ratio = (index + 1) / 8; const half = ratio * 5; const cx = from.x + dx * ratio; const cy = from.y + dy * ratio; return `<line x1="${cx - px * half}" y1="${cy - py * half}" x2="${cx + px * half}" y2="${cy + py * half}" />`; });
    }
    const lineCount = bond.order === 4 ? 2 : bond.order;
    return Array.from({ length: lineCount }, (_, index) => {
      const offset = (index - (bond.order === 4 ? 0.5 : (bond.order - 1) / 2)) * 8;
      const dash = bond.order === 4 && index === 1 ? ' stroke-dasharray="2 3"' : "";
      return `<line x1="${from.x + offsetX * offset}" y1="${from.y + offsetY * offset}" x2="${to.x + offsetX * offset}" y2="${to.y + offsetY * offset}"${dash} />`;
    });
  });
  const labels = structure.atoms.flatMap((atom) => [
    `<text x="${atom.x}" y="${atom.y}" text-anchor="middle" dominant-baseline="central">${atom.element}</text>`,
    ...(atom.formalCharge ? [`<text x="${atom.x + 11}" y="${atom.y - 11}" font-size="12" text-anchor="middle">${atom.formalCharge > 0 ? "+" : "-"}${Math.abs(atom.formalCharge) === 1 ? "" : Math.abs(atom.formalCharge)}</text>`] : []),
  ]);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Molecule structure"><g fill="none" stroke="#34443d" stroke-width="2.5" stroke-linecap="round">${lines.join("")}</g><g fill="#253b2d" font-family="Arial,sans-serif" font-size="18" font-weight="600">${labels.join("")}</g></svg>`;
}

function parseMolfile(text: string): Structure {
  const lines = text.split(/\r?\n/);
  if (lines.length < 5 || !lines[3].includes("V2000")) throw new Error("Only MDL V2000 MOL/SDF files are supported.");
  const counts = lines[3].trim().split(/\s+/);
  const atomCount = Number(counts[0]);
  const bondCount = Number(counts[1]);
  if (!Number.isInteger(atomCount) || !Number.isInteger(bondCount) || atomCount < 1 || atomCount > 500 || bondCount < 0 || bondCount > 1000) throw new Error("Invalid MOL file counts.");
  if (lines.length < 4 + atomCount + bondCount) throw new Error("MOL file ended before its atom and bond records.");
  const rawAtoms = lines.slice(4, 4 + atomCount).map((line, index) => {
    const columns = line.trim().split(/\s+/);
    const x = Number(columns[0]); const y = Number(columns[1]); const symbol = columns[3];
    if (!Number.isFinite(x) || !Number.isFinite(y) || !ELEMENTS.includes(symbol)) throw new Error(`Invalid MOL atom ${index + 1}.`);
    const chargeCodes: Record<number, number> = { 1: 3, 2: 2, 3: 1, 5: -1, 6: -2, 7: -3 };
    return { x, y, element: symbol, formalCharge: chargeCodes[Number(columns[5])] ?? 0 };
  });
  const minX = Math.min(...rawAtoms.map((atom) => atom.x)); const maxX = Math.max(...rawAtoms.map((atom) => atom.x));
  const minY = Math.min(...rawAtoms.map((atom) => atom.y)); const maxY = Math.max(...rawAtoms.map((atom) => atom.y));
  const scale = Math.min(1, (WIDTH - 80) / Math.max(1, maxX - minX), (HEIGHT - 80) / Math.max(1, maxY - minY));
  const atoms = rawAtoms.map((atom, index) => ({
    id: index + 1,
    element: atom.element,
    formalCharge: atom.formalCharge,
    x: WIDTH / 2 + (atom.x - (minX + maxX) / 2) * scale,
    y: HEIGHT / 2 - (atom.y - (minY + maxY) / 2) * scale,
  }));
  const bonds = lines.slice(4 + atomCount, 4 + atomCount + bondCount).map((line, index) => {
    const columns = line.trim().split(/\s+/).map(Number);
    const from = columns[0]; const to = columns[1]; const order = columns[2]; const stereo = columns[3] ?? 0;
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1 || from > atomCount || to < 1 || to > atomCount || from === to || ![1, 2, 3, 4].includes(order) || ![0, 1, 4, 6].includes(stereo) || (stereo !== 0 && order !== 1)) throw new Error(`Invalid or unsupported MOL bond ${index + 1}.`);
    return { id: index + 1, from, to, order: order as Bond["order"], stereo: stereo as Bond["stereo"] };
  });
  const chargeLines = lines.slice(4 + atomCount + bondCount).filter((line) => /^M\s+CHG\s+\d+/i.test(line));
  if (chargeLines.length > 0) {
    for (const atom of atoms) atom.formalCharge = 0;
    for (const line of chargeLines) {
      const columns = line.trim().split(/\s+/);
      const pairCount = Number(columns[2]);
      if (!Number.isInteger(pairCount) || pairCount < 0 || columns.length !== 3 + pairCount * 2) {
        throw new Error("Invalid MOL charge property.");
      }
      for (let index = 0; index < pairCount; index += 1) {
        const atomIndex = Number(columns[3 + index * 2]);
        const charge = Number(columns[4 + index * 2]);
        if (!Number.isInteger(atomIndex) || atomIndex < 1 || atomIndex > atoms.length || !Number.isInteger(charge) || charge < -15 || charge > 15) {
          throw new Error("Invalid MOL atom charge.");
        }
        atoms[atomIndex - 1].formalCharge = charge;
      }
    }
  }
  return { atoms, bonds };
}

function moleculeMolfile(structure: Structure): string {
  const atomIds = new Map(structure.atoms.map((atom, index) => [atom.id, index + 1]));
  const lines = ["Interactive ELN", "  Interactive-ELN", "", `${String(structure.atoms.length).padStart(3)}${String(structure.bonds.length).padStart(3)}  0  0  0  0            999 V2000`];
  for (const atom of structure.atoms) {
    const x = ((atom.x - WIDTH / 2) / 40).toFixed(4).padStart(10);
    const y = ((HEIGHT / 2 - atom.y) / 40).toFixed(4).padStart(10);
    lines.push(`${x}${y}${"0.0000".padStart(10)} ${atom.element.padEnd(3)} 0  0  0  0  0  0  0  0  0  0  0  0`);
  }
  for (const bond of structure.bonds) {
    lines.push(`${String(atomIds.get(bond.from) ?? 0).padStart(3)}${String(atomIds.get(bond.to) ?? 0).padStart(3)}${String(bond.order).padStart(3)}${String(bond.stereo).padStart(3)}  0  0  0`);
  }
  const chargedAtoms = structure.atoms.flatMap((atom, index) => atom.formalCharge
    ? [{ atomIndex: index + 1, charge: atom.formalCharge }]
    : []);
  for (let offset = 0; offset < chargedAtoms.length; offset += 8) {
    const chunk = chargedAtoms.slice(offset, offset + 8);
    lines.push(`M  CHG${String(chunk.length).padStart(3)}${chunk.map(({ atomIndex, charge }) => `${String(atomIndex).padStart(4)}${String(charge).padStart(4)}`).join("")}`);
  }
  lines.push("M  END", "");
  return lines.join("\n");
}

function parseSmiles(input: string): Structure {
  const source = input.trim();
  if (!source || source.length > 5000) throw new Error("SMILES must contain 1 to 5000 characters.");
  const atoms: Atom[] = [];
  const bonds: Bond[] = [];
  const branches: number[] = [];
  const rings = new Map<string, { atom: number; order: number | null }>();
  let current: number | null = null;
  let pendingOrder: number | null = null;
  let position = 0;
  const aromaticAtoms = new Set<number>();
  const addBond = (from: number, to: number, order: number) => {
    if (bonds.some((bond) => (bond.from === from && bond.to === to) || (bond.from === to && bond.to === from))) throw new Error("SMILES contains a duplicate bond.");
    bonds.push({ id: bonds.length + 1, from, to, order: order as Bond["order"], stereo: 0 });
  };
  while (position < source.length) {
    const character = source[position];
    if (character === "(") {
      if (current === null) throw new Error("SMILES branch has no preceding atom.");
      branches.push(current); position += 1; continue;
    }
    if (character === ")") {
      const branch = branches.pop();
      if (branch === undefined) throw new Error("SMILES has an unmatched branch close.");
      current = branch; position += 1; continue;
    }
    if (character === ".") {
      if (current === null || pendingOrder !== null) throw new Error("Invalid disconnected component in SMILES.");
      current = null; position += 1; continue;
    }
    if (character === "-" || character === "=" || character === "#" || character === ":") {
      if (pendingOrder !== null) throw new Error("SMILES has consecutive bond symbols.");
      pendingOrder = character === "=" ? 2 : character === "#" ? 3 : character === ":" ? 4 : 1;
      position += 1; continue;
    }
    if (character === "/" || character === "\\" || character === "@") throw new Error("SMILES stereochemical annotations are not supported yet.");
    if (/[0-9%]/.test(character)) {
      if (current === null) throw new Error("SMILES ring label has no atom.");
      let label: string;
      if (character === "%") {
        label = source.slice(position + 1, position + 3);
        if (!/^\d{2}$/.test(label)) throw new Error("Invalid percent ring label in SMILES.");
        position += 3;
      } else { label = character; position += 1; }
      const prior = rings.get(label);
      if (!prior) rings.set(label, { atom: current, order: pendingOrder });
      else {
        if (prior.atom === current) throw new Error("SMILES ring cannot close to the same atom.");
        if (prior.order !== null && pendingOrder !== null && prior.order !== pendingOrder) throw new Error("SMILES ring bond orders do not match.");
        const atomAromatic = aromaticAtoms.has(prior.atom); const currentAromatic = aromaticAtoms.has(current);
        addBond(prior.atom, current, pendingOrder ?? prior.order ?? (atomAromatic && currentAromatic ? 4 : 1));
        rings.delete(label);
      }
      pendingOrder = null; continue;
    }
    if (current === null && pendingOrder !== null) throw new Error("SMILES cannot start a component with a bond.");
    let element = ""; let aromatic = false; let formalCharge = 0; let explicitHydrogens = 0;
    if (character === "[") {
      const end = source.indexOf("]", position + 1);
      if (end < 0) throw new Error("SMILES bracket atom is not closed.");
      const body = source.slice(position + 1, end);
      const match = body.match(/^(Cl|Br|[A-Z][a-z]?|[bcnops])(H\d*)?([+-]\d*|\++|--+|-)?$/);
      if (!match) throw new Error(`Unsupported SMILES atom [${body}].`);
      element = match[1].length === 1 && match[1] === match[1].toLowerCase() ? match[1].toUpperCase() : match[1];
      aromatic = match[1] === match[1].toLowerCase();
      explicitHydrogens = match[2] ? Number(match[2].slice(1) || 1) : 0;
      const charge = match[3] ?? "";
      formalCharge = charge ? (/[0-9]/.test(charge) ? Number(charge.slice(1)) : charge.length) * (charge[0] === "-" ? -1 : 1) : 0;
      position = end + 1;
    } else {
      const pair = source.slice(position, position + 2);
      if (pair === "Cl" || pair === "Br") { element = pair; position += 2; }
      else if (/[BCNOPSFI]/.test(character)) { element = character; position += 1; }
      else if (/[bcnops]/.test(character)) { element = character.toUpperCase(); aromatic = true; position += 1; }
      else throw new Error(`Unsupported SMILES token at position ${position + 1}.`);
    }
    if (!ELEMENTS.includes(element)) throw new Error(`Unsupported element ${element} in SMILES.`);
    const id = atoms.length + 1;
    atoms.push({ id, element, formalCharge, x: 0, y: 0 });
    if (aromatic) aromaticAtoms.add(id);
    if (current !== null) addBond(current, id, pendingOrder ?? (aromatic && aromaticAtoms.has(current) ? 4 : 1));
    for (let index = 0; index < explicitHydrogens; index += 1) {
      const hydrogenId = atoms.length + 1;
      atoms.push({ id: hydrogenId, element: "H", formalCharge: 0, x: 0, y: 0 });
      addBond(id, hydrogenId, 1);
    }
    current = id; pendingOrder = null;
  }
  if (atoms.length === 0 || branches.length || rings.size || pendingOrder !== null) throw new Error("SMILES has an incomplete branch, ring, or bond.");
  const radius = Math.min(110, 22 + atoms.length * 4);
  atoms.forEach((atom, index) => {
    const angle = (2 * Math.PI * index) / atoms.length - Math.PI / 2;
    atom.x = Math.round(WIDTH / 2 + Math.cos(angle) * radius);
    atom.y = Math.round(HEIGHT / 2 + Math.sin(angle) * radius);
  });
  return { atoms, bonds };
}

function moleculeSmiles(structure: Structure): string {
  const atomMap = new Map(structure.atoms.map((atom) => [atom.id, atom]));
  const adjacency = new Map<number, Bond[]>();
  for (const atom of structure.atoms) adjacency.set(atom.id, []);
  for (const bond of structure.bonds) {
    adjacency.get(bond.from)?.push(bond);
    adjacency.get(bond.to)?.push(bond);
  }
  for (const list of adjacency.values()) list.sort((a, b) => a.id - b.id);
  const hydrogenParent = new Map<number, number>();
  for (const atom of structure.atoms) {
    if (atom.element !== "H") continue;
    const links = adjacency.get(atom.id) ?? [];
    if (links.length === 1 && links[0].order === 1) {
      hydrogenParent.set(atom.id, links[0].from === atom.id ? links[0].to : links[0].from);
    }
  }
  const visited = new Set<number>();
  const treeBonds = new Set<number>();
  const components: number[] = [];
  const markTree = (id: number) => {
    visited.add(id);
    for (const bond of adjacency.get(id) ?? []) {
      const other = bond.from === id ? bond.to : bond.from;
      if (!visited.has(other)) { treeBonds.add(bond.id); markTree(other); }
    }
  };
  for (const atom of structure.atoms) if (!visited.has(atom.id) && !hydrogenParent.has(atom.id)) { components.push(atom.id); markTree(atom.id); }
  const ringLabels = new Map<number, string[]>();
  const bondSymbol = (order: number) => order === 2 ? "=" : order === 3 ? "#" : order === 4 ? ":" : "";
  let ringNumber = 1;
  for (const bond of structure.bonds) {
    if (treeBonds.has(bond.id)) continue;
    if (ringNumber > 99) throw new Error("SMILES export supports at most 99 ring closures.");
    const label = ringNumber < 10 ? String(ringNumber) : `%${String(ringNumber).padStart(2, "0")}`;
    ringNumber += 1;
    const fromLabels = ringLabels.get(bond.from) ?? [];
    fromLabels.push(`${bondSymbol(bond.order)}${label}`);
    ringLabels.set(bond.from, fromLabels);
    const toLabels = ringLabels.get(bond.to) ?? [];
    toLabels.push(label);
    ringLabels.set(bond.to, toLabels);
  }
  const atomToken = (atom: Atom) => {
    const symbol = atom.element;
    const organic = ["B", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"].includes(symbol);
    const aromatic = (adjacency.get(atom.id) ?? []).some((bond) => bond.order === 4);
    const explicitHydrogenCount = (adjacency.get(atom.id) ?? []).filter((bond) => {
      const otherId = bond.from === atom.id ? bond.to : bond.from;
      return bond.order === 1 && atomMap.get(otherId)?.element === "H" && hydrogenParent.get(otherId) === atom.id;
    }).length;
    if (atom.formalCharge !== 0 || !organic || explicitHydrogenCount > 0) {
      const hydrogenPart = explicitHydrogenCount ? `H${explicitHydrogenCount === 1 ? "" : explicitHydrogenCount}` : "";
      const chargePart = atom.formalCharge ? `${atom.formalCharge > 0 ? "+" : "-"}${Math.abs(atom.formalCharge) === 1 ? "" : Math.abs(atom.formalCharge)}` : "";
      return `[${aromatic ? symbol.toLowerCase() : symbol}${hydrogenPart}${chargePart}]`;
    }
    return aromatic ? symbol.toLowerCase() : symbol;
  };
  const render = (id: number, parentBond?: number): string => {
    const atom = atomMap.get(id);
    if (!atom) return "";
    let result = atomToken(atom) + (ringLabels.get(id) ?? []).join("");
    const children = (adjacency.get(id) ?? []).filter((bond) => {
      const childId = bond.from === id ? bond.to : bond.from;
      return treeBonds.has(bond.id) && bond.id !== parentBond && hydrogenParent.get(childId) !== id;
    });
    children.forEach((bond, index) => {
      const child = bond.from === id ? bond.to : bond.from;
      const part = bondSymbol(bond.order) + render(child, bond.id);
      result += index === children.length - 1 ? part : `(${part})`;
    });
    return result;
  };
  return components.map((id) => render(id)).join(".");
}

export function MoleculeEditor({
  disabled,
  onSave,
  onStructureChange,
  t,
}: {
  disabled: boolean;
  onSave: (files: File[]) => Promise<void>;
  onStructureChange?: (structure: Structure) => void;
  t: (text: string) => string;
}) {
  const [structure, setStructure] = useState<Structure>({ atoms: [], bonds: [] });
  const [previous, setPrevious] = useState<Structure | null>(null);
  const [tool, setTool] = useState<Tool>("atom");
  const [element, setElement] = useState("C");
  const [bondOrder, setBondOrder] = useState<1 | 2 | 3 | 4>(1);
  const [selected, setSelected] = useState<number | null>(null);
  const [selectedBond, setSelectedBond] = useState<number | null>(null);
  const [bondStart, setBondStart] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const canvasRef = useRef<SVGSVGElement>(null);
  const dragging = useRef<number | null>(null);
  const dragSnapshot = useRef<Structure | null>(null);
  const preview = useMemo(() => moleculeSvg(structure), [structure]);
  const issues = useMemo(() => structureIssues(structure), [structure]);

  const stereocenters = useMemo(() => detectStereocenters(structure), [structure]);
  const doubleBonds = useMemo(() => detectDoubleBondStereo(structure), [structure]);
  const chiralAtomIds = useMemo(() => new Set(stereocenters.map((c) => c.atomId)), [stereocenters]);
  const doubleBondMap = useMemo(() => new Map(doubleBonds.map((b) => [b.bondId, b])), [doubleBonds]);

  useEffect(() => {
    onStructureChange?.(structure);
  }, [structure, onStructureChange]);

  function commit(next: Structure) {
    setPrevious(structure);
    setStructure(next);
  }

  function placeAtom(event: MouseEvent<SVGSVGElement>) {
    if (disabled || tool !== "atom") return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (bounds.width === 0 || bounds.height === 0) return;
    const x = Math.round(((event.clientX - bounds.left) / bounds.width) * WIDTH);
    const y = Math.round(((event.clientY - bounds.top) / bounds.height) * HEIGHT);
    const id = Math.max(Date.now(), ...structure.atoms.map((atom) => atom.id + 1));
    commit({ atoms: [...structure.atoms, { id, element, formalCharge: 0, x, y }], bonds: structure.bonds });
    setSelected(id);
    setSelectedBond(null);
  }

  function clickAtom(id: number) {
    if (disabled) return;
    if (tool === "bond") {
      if (bondStart === null) setBondStart(id);
      else if (bondStart === id) setBondStart(null);
      else {
        const duplicate = structure.bonds.some((bond) =>
          (bond.from === bondStart && bond.to === id) || (bond.from === id && bond.to === bondStart),
        );
        if (!duplicate) {
          const bond = { id: Math.max(Date.now(), ...structure.bonds.map((item) => item.id + 1)), from: bondStart, to: id, order: bondOrder, stereo: 0 as const };
          commit({ ...structure, bonds: [...structure.bonds, bond] });
        }
        setBondStart(null);
      }
    }
    setSelected(id);
    setSelectedBond(null);
  }

  function startMove(event: PointerEvent<SVGGElement>, id: number) {
    if (disabled || tool !== "select") return;
    clickAtom(id);
    event.stopPropagation();
    canvasRef.current?.setPointerCapture(event.pointerId);
    dragging.current = id;
    dragSnapshot.current = structure;
  }

  function moveAtom(event: PointerEvent<SVGSVGElement>) {
    const id = dragging.current;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (id === null || bounds.width === 0 || bounds.height === 0) return;
    const x = Math.max(8, Math.min(WIDTH - 8, Math.round(((event.clientX - bounds.left) / bounds.width) * WIDTH)));
    const y = Math.max(8, Math.min(HEIGHT - 8, Math.round(((event.clientY - bounds.top) / bounds.height) * HEIGHT)));
    setStructure((current) => ({ ...current, atoms: current.atoms.map((atom) => atom.id === id ? { ...atom, x, y } : atom) }));
  }

  function finishMove() {
    if (dragging.current !== null && dragSnapshot.current) setPrevious(dragSnapshot.current);
    dragging.current = null;
    dragSnapshot.current = null;
  }

  function changeElement(value: string) {
    setElement(value);
    if (selected === null) return;
    commit({ ...structure, atoms: structure.atoms.map((atom) => atom.id === selected ? { ...atom, element: value } : atom) });
  }

  function changeFormalCharge(value: number) {
    if (selected === null) return;
    commit({
      ...structure,
      atoms: structure.atoms.map((atom) => atom.id === selected ? { ...atom, formalCharge: value } : atom),
    });
  }

  function changeBondStereo(value: Bond["stereo"]) {
    if (selectedBond === null) return;
    commit({ ...structure, bonds: structure.bonds.map((bond) => bond.id === selectedBond ? { ...bond, stereo: value } : bond) });
  }

  function deleteSelected() {
    if (disabled) return;
    if (selectedBond !== null) {
      commit({ ...structure, bonds: structure.bonds.filter((bond) => bond.id !== selectedBond) });
      setSelectedBond(null);
      return;
    }
    if (selected === null) return;
    commit({
      atoms: structure.atoms.filter((atom) => atom.id !== selected),
      bonds: structure.bonds.filter((bond) => bond.from !== selected && bond.to !== selected),
    });
    setSelected(null);
    setBondStart(null);
  }

  function downloadSvg() {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([preview], { type: "image/svg+xml" }));
    link.download = "molecule-structure.svg";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
  }

  async function attachSvg() {
    if (disabled || saving || structure.atoms.length === 0) return;
    setSaving(true);
    try {
      const date = new Date().toISOString().slice(0, 10);
      await onSave([
        new File([preview], `molecule-structure-${date}.svg`, { type: "image/svg+xml" }),
        new File([JSON.stringify(structure, null, 2)], `molecule-structure-${date}.json`, { type: "application/json" }),
      ]);
    } catch {
      // The parent displays the upload error and the drawing remains available for retry.
    } finally {
      setSaving(false);
    }
  }

  function downloadSmiles() {
    try {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([moleculeSmiles(structure)], { type: "chemical/x-daylight-smiles;charset=utf-8" }));
      link.download = "molecule-structure.smi";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : t("Unable to export this structure as SMILES."));
    }
  }

  async function loadStructure(file?: File) {
    if (!file) return;
    try {
      const source = await file.text();
      const value = /\.(smi|smiles)$/i.test(file.name) ? parseSmiles(source) : /\.(mol|sdf)$/i.test(file.name) ? parseMolfile(source) : JSON.parse(source) as Partial<Structure>;
      if (!Array.isArray(value.atoms) || !Array.isArray(value.bonds) || value.atoms.length > 500 || value.bonds.length > 1000) throw new Error("Invalid structure file.");
      const atoms = (value.atoms as Partial<Atom>[]).map((atom) => ({
        ...atom,
        formalCharge: atom.formalCharge === undefined ? 0 : atom.formalCharge,
      } as Atom));
      const bonds = (value.bonds as Partial<Bond>[]).map((bond) => ({ ...bond, stereo: bond.stereo ?? 0 } as Bond));
      const ids = new Set<number>();
      for (const atom of atoms) {
        if (!Number.isInteger(atom.id) || ids.has(atom.id) || !ELEMENTS.includes(atom.element) || !Number.isFinite(atom.x) || !Number.isFinite(atom.y) || atom.x < 0 || atom.x > WIDTH || atom.y < 0 || atom.y > HEIGHT || !Number.isInteger(atom.formalCharge) || atom.formalCharge < -15 || atom.formalCharge > 15) throw new Error("Structure contains an invalid atom.");
        ids.add(atom.id);
      }
      const bondIds = new Set<number>();
      for (const bond of bonds) {
        if (!Number.isInteger(bond.id) || bondIds.has(bond.id) || bond.from === bond.to || !ids.has(bond.from) || !ids.has(bond.to) || ![1, 2, 3, 4].includes(bond.order) || ![0, 1, 4, 6].includes(bond.stereo) || (bond.stereo !== 0 && bond.order !== 1)) throw new Error("Structure contains an invalid bond.");
        bondIds.add(bond.id);
      }
      if (structureIssues({ atoms, bonds }).some((issue) => issue.includes("duplicate bonds") || issue.includes("invalid formal charge"))) throw new Error("Structure contains an invalid bond or formal charge.");
      commit({ atoms, bonds });
      setSelected(null); setSelectedBond(null); setBondStart(null);
    } catch {
      window.alert(t("This file is not a supported molecule structure."));
    }
  }

  return (
    <div className="molecule-editor">
      <p className="auth-copy">{t("Create a simple 2D structure, then download it or attach the SVG to this notebook entry.")}</p>
      <div className="molecule-toolbar" aria-label={t("Molecule drawing tools")}>
        <label>{t("Tool")}<select value={tool} disabled={disabled} onChange={(event) => { setTool(event.target.value as Tool); setBondStart(null); }}>
          <option value="atom">{t("Add atom")}</option><option value="bond">{t("Add bond")}</option><option value="select">{t("Select")}</option>
        </select></label>
        <label>{t("Bond stereo")}<select value={structure.bonds.find((bond) => bond.id === selectedBond)?.stereo ?? 0} disabled={disabled || selectedBond === null || structure.bonds.find((bond) => bond.id === selectedBond)?.order !== 1} onChange={(event) => changeBondStereo(Number(event.target.value) as Bond["stereo"])}>
          <option value={0}>{t("None")}</option><option value={1}>{t("Wedge")}</option><option value={4}>{t("Either")}</option><option value={6}>{t("Hash")}</option>
        </select></label>
        <label>{t(selected === null ? "New atom" : "Selected atom")}<select value={structure.atoms.find((atom) => atom.id === selected)?.element ?? element} disabled={disabled} onChange={(event) => changeElement(event.target.value)}>
          {ELEMENTS.map((item) => <option key={item}>{item}</option>)}
        </select></label>
        <label>{t("Formal charge")}<select
          value={structure.atoms.find((atom) => atom.id === selected)?.formalCharge ?? 0}
          disabled={disabled || selected === null}
          onChange={(event) => changeFormalCharge(Number(event.target.value))}
        >
          {Array.from({ length: 31 }, (_, index) => index - 15).map((charge) => (
            <option key={charge} value={charge}>{charge > 0 ? `+${charge}` : charge}</option>
          ))}
        </select></label>
        <label>{t("Bond")}<select value={bondOrder} disabled={disabled} onChange={(event) => setBondOrder(Number(event.target.value) as 1 | 2 | 3)}>
          <option value={1}>{t("Single")}</option><option value={2}>{t("Double")}</option><option value={3}>{t("Triple")}</option><option value={4}>{t("Aromatic")}</option>
        </select></label>
        <button className="button button-outline button-small" type="button" onClick={() => { if (previous) { setStructure(previous); setPrevious(null); setSelected(null); setSelectedBond(null); } }} disabled={disabled || !previous}>{t("Undo")}</button>
        <button className="button button-outline button-small" type="button" onClick={deleteSelected} disabled={disabled || (selected === null && selectedBond === null)}>{t("Delete selected")}</button>
        <button className="button button-outline button-small" type="button" onClick={() => { commit({ atoms: [], bonds: [] }); setSelected(null); setSelectedBond(null); setBondStart(null); }} disabled={disabled || structure.atoms.length === 0}>{t("Clear")}</button>
      </div>
      <svg
        ref={canvasRef}
        className="molecule-canvas" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="application" tabIndex={disabled ? -1 : 0}
        aria-label={t("Molecule editor canvas. Choose Add atom and click to place atoms; choose Add bond and click two atoms to connect them.")}
        onClick={placeAtom}
        onPointerMove={moveAtom}
        onPointerUp={finishMove}
        onPointerCancel={finishMove}
        onKeyDown={(event) => { if (event.key === "Delete" || event.key === "Backspace") deleteSelected(); }}
      >
        <rect width={WIDTH} height={HEIGHT} fill="#fff" />
        <g fill="none" stroke="#52675a" strokeWidth="2.5" strokeLinecap="round">
          {structure.bonds.map((bond) => {
            const from = structure.atoms.find((atom) => atom.id === bond.from);
            const to = structure.atoms.find((atom) => atom.id === bond.to);
            if (!from || !to) return null;
            const dx = to.x - from.x; const dy = to.y - from.y; const length = Math.hypot(dx, dy) || 1;
            const ox = -dy / length * 4; const oy = dx / length * 4;
            if (bond.order === 1 && bond.stereo !== 0) {
              const px = -dy / length; const py = dx / length;
              const selectedClass = selectedBond === bond.id ? "is-selected" : "";
              const onSelectBond = (event: MouseEvent<SVGElement>) => { event.stopPropagation(); setSelectedBond(bond.id); setSelected(null); };
              if (bond.stereo === 4) {
                const points = Array.from({ length: 9 }, (_, index) => { const ratio = index / 8; const wave = index === 0 || index === 8 ? 0 : (index % 2 ? 1 : -1) * 3; return `${from.x + dx * ratio + px * wave},${from.y + dy * ratio + py * wave}`; }).join(" ");
                return <polyline key={bond.id} className={selectedClass} points={points} fill="none" onClick={onSelectBond} />;
              }
              if (bond.stereo === 1) return <polygon key={bond.id} className={selectedClass} points={`${from.x},${from.y} ${to.x + px * 5},${to.y + py * 5} ${to.x - px * 5},${to.y - py * 5}`} fill="#52675a" stroke="#52675a" onClick={onSelectBond} />;
              return Array.from({ length: 7 }, (_, index) => { const ratio = (index + 1) / 8; const half = ratio * 5; const cx = from.x + dx * ratio; const cy = from.y + dy * ratio; return <line key={`${bond.id}-${index}`} className={selectedClass} x1={cx - px * half} y1={cy - py * half} x2={cx + px * half} y2={cy + py * half} onClick={onSelectBond} />; });
            }
            const lineCount = bond.order === 4 ? 2 : bond.order;
            const dbInfo = doubleBondMap.get(bond.id);
            return (
              <g key={bond.id}>
                {Array.from({ length: lineCount }, (_, index) => {
                  const offset = (index - (bond.order === 4 ? 0.5 : (bond.order - 1) / 2)) * 8;
                  return <line key={`${bond.id}-${index}`} className={selectedBond === bond.id ? "is-selected" : ""}
                    strokeDasharray={bond.order === 4 && index === 1 ? "2 3" : undefined}
                    x1={from.x + ox * offset} y1={from.y + oy * offset} x2={to.x + ox * offset} y2={to.y + oy * offset}
                    onClick={(event) => { event.stopPropagation(); setSelectedBond(bond.id); setSelected(null); }} />;
                })}
                {dbInfo && dbInfo.configuration !== "unspecified" && (
                  <text
                    x={(from.x + to.x) / 2 + ox * 3}
                    y={(from.y + to.y) / 2 + oy * 3}
                    fontSize="11"
                    fontWeight="bold"
                    fill="#a0522d"
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    ({dbInfo.configuration})
                  </text>
                )}
              </g>
            );
          })}
        </g>
        {structure.atoms.map((atom) => (
          <g key={atom.id} className="molecule-atom" role="button" tabIndex={disabled ? -1 : 0} aria-label={`${atom.element} atom`}
            onClick={(event) => { event.stopPropagation(); clickAtom(atom.id); }}
            onPointerDown={(event) => startMove(event, atom.id)}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); clickAtom(atom.id); } }}>
            <circle cx={atom.x} cy={atom.y} r="17" className={selected === atom.id || bondStart === atom.id ? "is-selected" : ""} />
            <text x={atom.x} y={atom.y} textAnchor="middle" dominantBaseline="central">{atom.element}</text>
            {atom.formalCharge !== 0 && <text x={atom.x + 12} y={atom.y - 11} fontSize="11" textAnchor="middle">{atom.formalCharge > 0 ? "+" : "-"}{Math.abs(atom.formalCharge) === 1 ? "" : Math.abs(atom.formalCharge)}</text>}
            {chiralAtomIds.has(atom.id) && (
              <text x={atom.x - 13} y={atom.y - 12} fontSize="14" fill="#1b633b" fontWeight="bold" textAnchor="middle"><title>{t("Chiral stereocenter")}</title>*</text>
            )}
          </g>
        ))}
        {structure.atoms.length === 0 && <text x={WIDTH / 2} y={HEIGHT / 2} textAnchor="middle" className="molecule-placeholder">{t("Click to place the first atom")}</text>}
      </svg>
      {stereocenters.length > 0 && (
        <div style={{ fontSize: "11px", color: "#1b633b", fontWeight: 600 }}>
          ★ {t("Chiral stereocenters detected:")} {stereocenters.map((c) => `${c.element}${c.atomId}`).join(", ")}
        </div>
      )}
      {doubleBonds.length > 0 && (
        <div style={{ fontSize: "11px", color: "#a0522d", fontWeight: 600 }}>
          ⚯ {t("Geometric configurations:")} {doubleBonds.map((b) => `Bond #${b.bondId} (${b.configuration})`).join(", ")}
        </div>
      )}
      {issues.length > 0 && <div className="inline-error molecule-validation" role="alert">{issues.join(" ")}</div>}
      <small>{t("Charge-aware valence checks cover common charged states for B, C, N, O, P, S, and Se. Other charge states are preserved in JSON and V2000 files but are not chemically validated here.")}</small>
      {structure.bonds.some((bond) => bond.stereo !== 0) && <small>{t("SMILES export is disabled while wedge, hash, or either bond markers are present because this editor does not assign stereochemical SMILES notation.")}</small>}
      <div className="molecule-actions">
        <button className="button button-outline" type="button" onClick={downloadSvg} disabled={structure.atoms.length === 0}>{t("Download SVG")}</button>
        <button className="button button-outline" type="button" onClick={() => { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([moleculeMolfile(structure)], { type: "chemical/x-mdl-molfile" })); link.download = "molecule-structure.mol"; link.click(); window.setTimeout(() => URL.revokeObjectURL(link.href), 0); }} disabled={structure.atoms.length === 0}>{t("Download MOL")}</button>
        <button className="button button-outline" type="button" onClick={downloadSmiles} disabled={structure.atoms.length === 0 || structure.bonds.some((bond) => bond.stereo !== 0)}>{t("Download SMILES")}</button>
        <button className="button button-outline" type="button" onClick={() => { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([JSON.stringify(structure, null, 2)], { type: "application/json" })); link.download = "molecule-structure.json"; link.click(); window.setTimeout(() => URL.revokeObjectURL(link.href), 0); }} disabled={structure.atoms.length === 0}>{t("Download editable JSON")}</button>
        <label className="button button-outline button-small">{t("Load structure")}<input type="file" accept="application/json,.json,.mol,.sdf,.smi,.smiles" hidden disabled={disabled} onChange={(event) => { void loadStructure(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} /></label>
        <button className="button button-primary" type="button" onClick={() => void attachSvg()} disabled={disabled || saving || structure.atoms.length === 0 || issues.length > 0}>{saving ? t("Attaching…") : t("Attach structure")}</button>
      </div>
      {disabled && <small>{t("Editing access is required to attach a structure.")}</small>}
    </div>
  );
}
