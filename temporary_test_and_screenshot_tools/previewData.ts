import type { Project, Experiment, NotebookEntry, InventoryItem, SampleRecord } from "./types";
import type { AuthUser } from "./api";

export const MOCK_PREVIEW_USER: AuthUser = {
  id: 1,
  email: "dr.elena.rostova@biosynth.org",
  display_name: "Dr. Elena Rostova",
  role: "admin",
  organization_id: 1,
};

export const MOCK_PREVIEW_PROJECTS: Project[] = [
  {
    id: 1,
    organization_id: 1,
    name: "Kinase Inhibitor Optimization & Synthesis",
    description: "Development of potent, selective small-molecule ATP-competitive tyrosine kinase inhibitors.",
    created_at: "2026-10-01T09:00:00Z",
  },
  {
    id: 2,
    organization_id: 1,
    name: "CRISPR-Cas9 Gene Editing Screening in Hepatocytes",
    description: "Targeted knockout of lipogenic regulator genes in primary human hepatocytes.",
    created_at: "2026-10-05T14:30:00Z",
  },
  {
    id: 3,
    organization_id: 1,
    name: "Preclinical Pharmacokinetics & ADMET Profiling",
    description: "Assessing metabolic stability, CYP450 inhibition, and pharmacokinetic parameters.",
    created_at: "2026-10-12T11:15:00Z",
  },
];

export const MOCK_PREVIEW_EXPERIMENTS: Experiment[] = [
  {
    id: 1,
    organization_id: 1,
    project_id: 1,
    name: "Palladium-Catalyzed Suzuki-Miyaura Cross-Coupling for Lead BS-8042",
    description: "Synthesis of biaryl kinase inhibitor core through optimized cross-coupling protocol.",
    status: "completed",
    created_at: "2026-10-02T10:00:00Z",
    updated_at: "2026-10-30T17:00:00Z",
  },
  {
    id: 2,
    organization_id: 1,
    project_id: 1,
    name: "High-Throughput Tyrosine Kinase IC50 Enzyme Inhibition Assay",
    description: "Multi-point dilution dose-response profiling in 384-well format.",
    status: "in_progress",
    created_at: "2026-10-15T09:30:00Z",
    updated_at: "2026-10-31T14:00:00Z",
  },
];

export const MOCK_PREVIEW_ENTRIES: NotebookEntry[] = [
  {
    id: 1,
    experiment_id: 1,
    title: "Reaction Setup & In-Situ Monitoring",
    content: `Coupling executed under inert argon atmosphere using [@4-Bromobenzaldehyde](#inv:2) (5.0 mmol, 925 mg) and [@Phenylboronic Acid](#inv:3) (6.0 mmol, 731 mg) catalyzed by [@Tetrakis(triphenylphosphine)palladium(0)](#inv:4) (0.1 mmol, 115 mg) and base [@Potassium Carbonate](#inv:5) (12.5 mmol, 1.73 g) in 30 mL anhydrous [@1,4-Dioxane (Anhydrous)](#inv:6) / water (4:1).

Kinetics observed follow pseudo-first order rate expression:
$$r = -\\frac{d[ArBr]}{dt} = k_{obs} [ArBr]$$
$$k_{obs} = A e^{-\\frac{E_a}{RT}}$$

Reaction heated to 85°C with continuous overhead magnetic stirring (650 RPM). Aliquots sampled at t = 15, 30, 60, 120 min for HPLC analysis. Product crystallized upon cooling to 4°C as pale yellow needles.
Isolated yield = 87.4% (802.4 mg pure BS-8042). Sample archived as [#Kinase Inhibitor Lead Compound BS-8042](#smp:3).`,
    created_at: "2026-10-04T11:00:00Z",
    updated_at: "2026-10-04T16:30:00Z",
  },
  {
    id: 2,
    experiment_id: 1,
    title: "Chromatographic Purification & Isolated Yield Analysis",
    content: `The reaction mixture was filtered through celite, extracted with ethyl acetate (3 x 40 mL), dried over anhydrous Na2SO4, and concentrated under reduced pressure.

Purified by automated silica flash column chromatography (gradient 0-25% EtOAc/Hexanes).
Isolated mass: 802.4 mg (Theoretical yield: 917.9 mg -> Isolated yield = 87.4%).

1H-NMR (400 MHz, CDCl3): 10.06 (s, 1H, CHO), 7.97 (d, J = 8.4 Hz, 2H), 7.76 (d, J = 8.4 Hz, 2H), 7.65 (d, J = 7.2 Hz, 2H), 7.49 (t, J = 7.4 Hz, 2H), 7.42 (t, J = 7.2 Hz, 1H).
Conforms with pure 4-phenylbenzaldehyde core.`,
    created_at: "2026-10-06T13:45:00Z",
    updated_at: "2026-10-06T18:00:00Z",
  },
];

export const MOCK_PREVIEW_INVENTORY: InventoryItem[] = [
  {
    id: 1,
    organization_id: 1,
    name: "Sodium Borohydride",
    category: "Reducing Agent",
    catalog_number: "SBH-01",
    lot_number: "LOT-9921",
    expires_on: "2027-05-15",
    quantity: 49.62,
    unit: "g",
    low_stock_threshold: 10.0,
    location: "Shelf 2",
    notes: "Anhydrous grade, stored under dessication",
    custom_fields: { "CAS Number": "16940-66-2", "Purity %": "98.5", "Supplier": "Sigma-Aldrich", "SMILES Structure": "[Na+].[BH4-]" },
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-10-31T12:00:00Z",
    status: "active",
  },
  {
    id: 2,
    organization_id: 1,
    name: "4-Bromobenzaldehyde",
    category: "Building Block",
    catalog_number: "BBA-02",
    lot_number: "LOT-8410",
    expires_on: "2027-08-20",
    quantity: 100.0,
    unit: "g",
    low_stock_threshold: 15.0,
    location: "Shelf 2",
    notes: "Core aryl halide for cross-coupling",
    custom_fields: { "CAS Number": "1122-91-4", "Purity %": "99.0", "Supplier": "Enamine", "SMILES Structure": "O=Cc1ccc(Br)cc1" },
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-10-31T12:00:00Z",
    status: "active",
  },
  {
    id: 3,
    organization_id: 1,
    name: "Phenylboronic Acid",
    category: "Organoboron",
    catalog_number: "PBA-03",
    lot_number: "LOT-7731",
    expires_on: "2027-11-10",
    quantity: 50.0,
    unit: "g",
    low_stock_threshold: 10.0,
    location: "Shelf 2",
    notes: "Suzuki-Miyaura nucleophile",
    custom_fields: { "CAS Number": "98-80-6", "Purity %": "98.0", "Supplier": "Combi-Blocks", "SMILES Structure": "OB(O)c1ccccc1" },
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-10-31T12:00:00Z",
    status: "active",
  },
  {
    id: 4,
    organization_id: 1,
    name: "Tetrakis(triphenylphosphine)palladium(0)",
    category: "Catalyst",
    catalog_number: "PD-TET-04",
    lot_number: "LOT-6612",
    expires_on: "2027-03-30",
    quantity: 15.0,
    unit: "g",
    low_stock_threshold: 2.0,
    location: "CryoVault-3",
    notes: "Air-sensitive yellow solid, stored at -20°C under argon",
    custom_fields: { "CAS Number": "14221-01-3", "Purity %": "99.5", "Supplier": "Strem Chemicals", "SMILES Structure": "c1ccccc1P(c2ccccc2)(c3ccccc3)[Pd]" },
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-10-31T12:00:00Z",
    status: "active",
  },
];

export const MOCK_PREVIEW_SAMPLES: SampleRecord[] = [
  {
    id: 1,
    organization_id: 1,
    project_id: 1,
    name: "Crude Suzuki-Miyaura Reaction Aliquot t=120min",
    sample_type: "reaction aliquot",
    external_id: "SMP-1001",
    parent_sample_id: null,
    storage_location: "9x9 Cryo Box B-01 (Plate/Box Grid)",
    storage_location_id: 5,
    description: "HPLC sample vial (A1) filtered through PTFE 0.22 um",
    created_by_user_id: 1,
    current_custodian_user_id: 1,
    created_at: "2026-10-04T14:00:00Z",
    status: "active",
  },
  {
    id: 2,
    organization_id: 1,
    project_id: 1,
    name: "Kinase Inhibitor Lead Compound BS-8042",
    sample_type: "synthesized compound",
    external_id: "SMP-8042",
    parent_sample_id: 1,
    storage_location: "9x9 Cryo Box B-01 (Plate/Box Grid)",
    storage_location_id: 5,
    description: "Purified crystalline free base (A2). 99.4% purity by UHPLC.",
    created_by_user_id: 1,
    current_custodian_user_id: 1,
    created_at: "2026-10-06T15:30:00Z",
    status: "active",
  },
];
