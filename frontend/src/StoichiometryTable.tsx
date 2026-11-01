import { useState, useMemo } from "react";
import { parseChemicalFormula, type Structure, structureToFormula } from "./chemistryUtils";
import type { InventoryItem } from "./types";

export interface ReagentRow {
  id: string;
  role: "reactant" | "reagent" | "catalyst" | "solvent";
  name: string;
  formula: string;
  mw: number; // g/mol
  isLimiting: boolean;
  equivalents: number;
  moles: number; // mmol
  mass: number; // mg
  volume?: number; // mL
  density?: number; // g/mL
  purity: number; // wt% (0 - 100)
  matchedInventoryId?: number;
}

export interface ProductRow {
  id: string;
  name: string;
  formula: string;
  mw: number; // g/mol
  ratio: number; // stoichiometric ratio
  actualMass: number; // mg
}

export interface StoichiometryData {
  title: string;
  notes?: string;
  reagents: ReagentRow[];
  products: ProductRow[];
}

interface StoichiometryTableProps {
  initialData?: StoichiometryData;
  activeStructure?: Structure | null;
  disabled?: boolean;
  inventoryItems?: InventoryItem[];
  onDeductStock?: (deductions: { itemId: number; itemName: string; amount: number; unit: string }[]) => Promise<void>;
  onSaveAttachment?: (file: File) => Promise<void>;
  onInsertMarkdown?: (markdown: string) => void;
  t?: (key: string) => string;
}

const defaultTranslate = (s: string) => s;

export function StoichiometryTable({
  initialData,
  activeStructure,
  disabled = false,
  inventoryItems = [],
  onDeductStock,
  onSaveAttachment,
  onInsertMarkdown,
  t = defaultTranslate,
}: StoichiometryTableProps) {
  const [title, setTitle] = useState(initialData?.title || "Reaction Stoichiometry");
  const [showDeductModal, setShowDeductModal] = useState(false);
  const [deducting, setDeducting] = useState(false);
  const [deductSuccess, setDeductSuccess] = useState<string | null>(null);
  const [manualItemMappings, setManualItemMappings] = useState<Record<string, number>>({});
  const [reagents, setReagents] = useState<ReagentRow[]>(() => {
    if (initialData?.reagents && initialData.reagents.length > 0) {
      return initialData.reagents;
    }
    return [
      {
        id: "r-1",
        role: "reactant",
        name: "Reactant A",
        formula: "C6H5Br",
        mw: 157.01,
        isLimiting: true,
        equivalents: 1.0,
        moles: 5.0, // 5.0 mmol
        mass: 785.05, // 5.0 * 157.01 mg
        purity: 100,
      },
      {
        id: "r-2",
        role: "reactant",
        name: "Reactant B",
        formula: "C6H5B(OH)2",
        mw: 121.93,
        isLimiting: false,
        equivalents: 1.2,
        moles: 6.0,
        mass: 731.58,
        purity: 100,
      },
    ];
  });

  const [products, setProducts] = useState<ProductRow[]>(() => {
    if (initialData?.products && initialData.products.length > 0) {
      return initialData.products;
    }
    return [
      {
        id: "p-1",
        name: "Coupled Product",
        formula: "C12H10",
        mw: 154.21,
        ratio: 1.0,
        actualMass: 616.84, // isolated mg
      },
    ];
  });

  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  // Find limiting reagent
  const limitingReagent = useMemo(() => {
    return reagents.find((r) => r.isLimiting) ?? reagents[0];
  }, [reagents]);

  const limitingMoles = limitingReagent ? limitingReagent.moles : 0;

  // Handler for reagent updates with reactive auto-calculation
  function updateReagent(id: string, updates: Partial<ReagentRow>) {
    setReagents((prev) => {
      return prev.map((row) => {
        if (row.id !== id) {
          // If this update makes another row limiting, unmark this one
          if (updates.isLimiting && row.isLimiting) {
            return { ...row, isLimiting: false };
          }
          return row;
        }

        const merged: ReagentRow = { ...row, ...updates };

        // If formula changed and mw wasn't manually forced, auto-update mw
        if (updates.formula !== undefined && updates.mw === undefined) {
          const parsed = parseChemicalFormula(updates.formula);
          if (parsed && parsed.molecularWeight > 0) {
            merged.mw = parsed.molecularWeight;
          }
        }

        const mw = merged.mw > 0 ? merged.mw : 1.0;
        const purityFactor = (merged.purity > 0 ? merged.purity : 100) / 100;

        // Reactive chain:
        // 1. If Mass was changed:
        if (updates.mass !== undefined) {
          merged.moles = (merged.mass * purityFactor) / mw;
          if (merged.density && merged.density > 0) {
            merged.volume = merged.mass / (merged.density * 1000); // mass in mg -> volume in mL
          }
        }
        // 2. If Moles was changed:
        else if (updates.moles !== undefined) {
          merged.mass = (merged.moles * mw) / purityFactor;
          if (merged.density && merged.density > 0) {
            merged.volume = merged.mass / (merged.density * 1000);
          }
        }
        // 3. If Volume was changed:
        else if (updates.volume !== undefined && merged.density && merged.density > 0) {
          merged.mass = updates.volume * merged.density * 1000;
          merged.moles = (merged.mass * purityFactor) / mw;
        }
        // 4. If Equivalents was changed (for non-limiting reagent):
        else if (updates.equivalents !== undefined && !merged.isLimiting && limitingMoles > 0) {
          merged.moles = limitingMoles * updates.equivalents;
          merged.mass = (merged.moles * mw) / purityFactor;
          if (merged.density && merged.density > 0) {
            merged.volume = merged.mass / (merged.density * 1000);
          }
        }

        return merged;
      });
    });
  }

  // When limiting reagent moles change, update non-limiting reagents' equivalents
  function handleLimitingMolesChange(newLimitingMoles: number) {
    if (newLimitingMoles <= 0) return;
    setReagents((prev) =>
      prev.map((row) => {
        if (row.isLimiting) {
          return {
            ...row,
            moles: newLimitingMoles,
            mass: (newLimitingMoles * row.mw) / ((row.purity || 100) / 100),
            equivalents: 1.0,
          };
        } else {
          // Keep moles and update equivalents
          return {
            ...row,
            equivalents: Math.round((row.moles / newLimitingMoles) * 1000) / 1000,
          };
        }
      })
    );
  }

  function toggleLimiting(id: string) {
    setReagents((prev) => {
      const target = prev.find((r) => r.id === id);
      if (!target) return prev;
      const targetMoles = target.moles > 0 ? target.moles : 1.0;

      return prev.map((row) => {
        if (row.id === id) {
          return { ...row, isLimiting: true, equivalents: 1.0 };
        } else {
          return {
            ...row,
            isLimiting: false,
            equivalents: Math.round((row.moles / targetMoles) * 1000) / 1000,
          };
        }
      });
    });
  }

  function addReagent() {
    const nextId = `r-${Date.now()}`;
    setReagents((prev) => [
      ...prev,
      {
        id: nextId,
        role: "reagent",
        name: `Reagent ${prev.length + 1}`,
        formula: "",
        mw: 100.0,
        isLimiting: false,
        equivalents: 1.0,
        moles: limitingMoles > 0 ? limitingMoles : 1.0,
        mass: limitingMoles > 0 ? limitingMoles * 100 : 100,
        purity: 100,
      },
    ]);
  }

  function removeReagent(id: string) {
    if (reagents.length <= 1) return;
    setReagents((prev) => {
      const filtered = prev.filter((r) => r.id !== id);
      if (!filtered.some((r) => r.isLimiting) && filtered.length > 0) {
        filtered[0].isLimiting = true;
        filtered[0].equivalents = 1.0;
      }
      return filtered;
    });
  }

  function updateProduct(id: string, updates: Partial<ProductRow>) {
    setProducts((prev) => {
      return prev.map((row) => {
        if (row.id !== id) return row;
        const merged: ProductRow = { ...row, ...updates };
        if (updates.formula !== undefined && updates.mw === undefined) {
          const parsed = parseChemicalFormula(updates.formula);
          if (parsed && parsed.molecularWeight > 0) {
            merged.mw = parsed.molecularWeight;
          }
        }
        return merged;
      });
    });
  }

  function addProduct() {
    const nextId = `p-${Date.now()}`;
    setProducts((prev) => [
      ...prev,
      {
        id: nextId,
        name: `Product ${prev.length + 1}`,
        formula: "",
        mw: 150.0,
        ratio: 1.0,
        actualMass: 0,
      },
    ]);
  }

  function removeProduct(id: string) {
    if (products.length <= 1) return;
    setProducts((prev) => prev.filter((p) => p.id !== id));
  }

  // Import drawn structure from active MoleculeEditor
  function importMoleculeToReactant() {
    if (!activeStructure || activeStructure.atoms.length === 0) return;
    const res = structureToFormula(activeStructure);
    if (!res) return;

    setReagents((prev) => {
      const first = prev[0];
      const updatedFirst: ReagentRow = {
        ...first,
        name: "Drawn Molecule",
        formula: res.formula,
        mw: res.molecularWeight,
        mass: Math.round(first.moles * res.molecularWeight * 100) / 100,
      };
      return [updatedFirst, ...prev.slice(1)];
    });
    setNotice(t("Loaded drawn molecule into primary reactant."));
  }

  function importMoleculeToProduct() {
    if (!activeStructure || activeStructure.atoms.length === 0) return;
    const res = structureToFormula(activeStructure);
    if (!res) return;

    setProducts((prev) => {
      const first = prev[0];
      const updatedFirst: ProductRow = {
        ...first,
        name: "Target Product",
        formula: res.formula,
        mw: res.molecularWeight,
      };
      return [updatedFirst, ...prev.slice(1)];
    });
    setNotice(t("Loaded drawn molecule into target product."));
  }

  // Generate Markdown / LaTeX table representation for notebook entry
  function generateMarkdownTable(): string {
    let md = `### ${title}\n\n`;
    md += `**Limiting Reagent:** ${limitingReagent?.name ?? "None"} (${limitingReagent?.moles.toFixed(2)} mmol)\n\n`;
    md += `#### Reagents & Reactants\n\n`;
    md += `| Role | Compound | Formula | MW (g/mol) | Eq | Amount (mmol) | Mass (mg) | Purity (%) |\n`;
    md += `| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n`;

    for (const r of reagents) {
      const roleBadge = r.isLimiting ? `**${r.role} (limiting)**` : r.role;
      md += `| ${roleBadge} | ${r.name} | $${r.formula || "- "}$ | ${r.mw.toFixed(2)} | ${r.equivalents.toFixed(2)} | ${r.moles.toFixed(2)} | ${r.mass.toFixed(1)} | ${r.purity}% |\n`;
    }

    md += `\n#### Products & Isolated Yield\n\n`;
    md += `| Product | Formula | MW (g/mol) | Theo. Moles (mmol) | Theo. Mass (mg) | Actual Mass (mg) | **Yield (%)** |\n`;
    md += `| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n`;

    for (const p of products) {
      const theoMoles = limitingMoles * (p.ratio || 1.0);
      const theoMass = theoMoles * p.mw;
      const actualMoles = p.mw > 0 ? p.actualMass / p.mw : 0;
      const yieldPct = theoMoles > 0 ? (actualMoles / theoMoles) * 100 : 0;
      md += `| ${p.name} | $${p.formula || "- "}$ | ${p.mw.toFixed(2)} | ${theoMoles.toFixed(2)} | ${theoMass.toFixed(1)} | ${p.actualMass.toFixed(1)} | **${yieldPct.toFixed(1)}%** |\n`;
    }

    md += `\n`;
    return md;
  }

  async function handleAttachTable() {
    if (!onSaveAttachment) return;
    setSaving(true);
    try {
      const data: StoichiometryData = { title, reagents, products };
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const file = new File([blob], `stoichiometry-${Date.now()}.json`, {
        type: "application/json",
      });
      await onSaveAttachment(file);
      setNotice(t("Stoichiometry table attached to entry as JSON."));
    } catch {
      setNotice(t("Failed to attach stoichiometry table."));
    } finally {
      setSaving(false);
    }
  }

  function handleInsertIntoEntry() {
    if (!onInsertMarkdown) return;
    const md = generateMarkdownTable();
    onInsertMarkdown(md);
    setNotice(t("Formatted stoichiometry table inserted into entry text."));
  }

  return (
    <div className="stoichiometry-calculator">
      <div className="stoichiometry-header">
        <input
          type="text"
          className="stoichiometry-title-input"
          value={title}
          disabled={disabled}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t("Reaction Title / Description")}
        />
        {activeStructure && activeStructure.atoms.length > 0 && (
          <div className="stoichiometry-import-tools">
            <button
              type="button"
              className="button button-outline button-small"
              onClick={importMoleculeToReactant}
              disabled={disabled}
            >
              {t("Import molecule to reactant")}
            </button>
            <button
              type="button"
              className="button button-outline button-small"
              onClick={importMoleculeToProduct}
              disabled={disabled}
            >
              {t("Import molecule to product")}
            </button>
          </div>
        )}
      </div>

      {notice && (
        <div className="notice notice-info" style={{ margin: "6px 0", fontSize: "11px" }}>
          {notice}
          <button
            type="button"
            className="button button-outline button-small"
            style={{ marginLeft: "8px", padding: "1px 6px" }}
            onClick={() => setNotice("")}
          >
            x
          </button>
        </div>
      )}

      {/* REAGENTS SECTION */}
      <div className="stoichiometry-section">
        <div className="stoichiometry-section-header">
          <strong>{t("Reactants & Reagents")}</strong>
          <small>{t("Designate one limiting reagent (1.00 eq); other amounts scale reactively.")}</small>
        </div>
        <div className="table-responsive">
          <table className="stoichiometry-table">
            <thead>
              <tr>
                <th title={t("Limiting Reagent")}>{t("Limit")}</th>
                <th>{t("Role")}</th>
                <th>{t("Name")}</th>
                <th>{t("Formula")}</th>
                <th>{t("MW (g/mol)")}</th>
                <th>{t("Equiv")}</th>
                <th>{t("Moles (mmol)")}</th>
                <th>{t("Mass (mg)")}</th>
                <th>{t("Density (g/mL)")}</th>
                <th>{t("Vol (mL)")}</th>
                <th>{t("Purity (%)")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reagents.map((row) => (
                <tr key={row.id} className={row.isLimiting ? "is-limiting-row" : ""}>
                  <td style={{ textAlign: "center" }}>
                    <input
                      type="radio"
                      name="limiting_reagent"
                      checked={row.isLimiting}
                      disabled={disabled}
                      onChange={() => toggleLimiting(row.id)}
                      title={t("Toggle limiting reagent")}
                    />
                  </td>
                  <td>
                    <select
                      value={row.role}
                      disabled={disabled}
                      onChange={(e) =>
                        updateReagent(row.id, {
                          role: e.target.value as ReagentRow["role"],
                        })
                      }
                    >
                      <option value="reactant">{t("Reactant")}</option>
                      <option value="reagent">{t("Reagent")}</option>
                      <option value="catalyst">{t("Catalyst")}</option>
                      <option value="solvent">{t("Solvent")}</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="text"
                      value={row.name}
                      disabled={disabled}
                      onChange={(e) => updateReagent(row.id, { name: e.target.value })}
                      placeholder={t("Compound")}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={row.formula}
                      disabled={disabled}
                      onChange={(e) => updateReagent(row.id, { formula: e.target.value })}
                      placeholder="e.g. C6H5Br"
                      style={{ width: "85px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={row.mw || ""}
                      disabled={disabled}
                      onChange={(e) =>
                        updateReagent(row.id, { mw: parseFloat(e.target.value) || 0 })
                      }
                      style={{ width: "70px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={row.equivalents || ""}
                      disabled={disabled || row.isLimiting}
                      onChange={(e) =>
                        updateReagent(row.id, {
                          equivalents: parseFloat(e.target.value) || 0,
                        })
                      }
                      style={{ width: "60px", fontWeight: row.isLimiting ? "bold" : "normal" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={Math.round(row.moles * 100) / 100 || ""}
                      disabled={disabled}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        if (row.isLimiting) {
                          handleLimitingMolesChange(val);
                        } else {
                          updateReagent(row.id, { moles: val });
                        }
                      }}
                      style={{ width: "70px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={Math.round(row.mass * 10) / 10 || ""}
                      disabled={disabled}
                      onChange={(e) =>
                        updateReagent(row.id, { mass: parseFloat(e.target.value) || 0 })
                      }
                      style={{ width: "75px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.001"
                      value={row.density || ""}
                      disabled={disabled}
                      onChange={(e) =>
                        updateReagent(row.id, {
                          density: parseFloat(e.target.value) || undefined,
                        })
                      }
                      placeholder="g/mL"
                      style={{ width: "65px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.01"
                      value={row.volume ? Math.round(row.volume * 100) / 100 : ""}
                      disabled={disabled || !row.density}
                      onChange={(e) =>
                        updateReagent(row.id, {
                          volume: parseFloat(e.target.value) || undefined,
                        })
                      }
                      placeholder="mL"
                      style={{ width: "65px" }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      max="100"
                      value={row.purity || 100}
                      disabled={disabled}
                      onChange={(e) =>
                        updateReagent(row.id, {
                          purity: parseFloat(e.target.value) || 100,
                        })
                      }
                      style={{ width: "50px" }}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="button button-outline button-small"
                      disabled={disabled || reagents.length <= 1}
                      onClick={() => removeReagent(row.id)}
                      title={t("Remove reagent")}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="button button-outline button-small"
          onClick={addReagent}
          disabled={disabled}
          style={{ marginTop: "6px" }}
        >
          + {t("Add reagent")}
        </button>
      </div>

      {/* PRODUCTS & YIELD SECTION */}
      <div className="stoichiometry-section" style={{ marginTop: "14px" }}>
        <div className="stoichiometry-section-header">
          <strong>{t("Products & Percentage Yield")}</strong>
          <small>{t("Theoretical yield is calculated against the limiting reagent.")}</small>
        </div>
        <div className="table-responsive">
          <table className="stoichiometry-table">
            <thead>
              <tr>
                <th>{t("Product Name")}</th>
                <th>{t("Formula")}</th>
                <th>{t("MW (g/mol)")}</th>
                <th>{t("Ratio")}</th>
                <th>{t("Theo. Moles (mmol)")}</th>
                <th>{t("Theo. Mass (mg)")}</th>
                <th>{t("Actual Mass (mg)")}</th>
                <th>{t("Yield (%)")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {products.map((row) => {
                const theoMoles = limitingMoles * (row.ratio || 1.0);
                const theoMass = theoMoles * (row.mw || 1.0);
                const actualMoles = row.mw > 0 ? row.actualMass / row.mw : 0;
                const yieldPct = theoMoles > 0 ? (actualMoles / theoMoles) * 100 : 0;

                const yieldBadgeClass =
                  yieldPct >= 80
                    ? "status-badge status-approved"
                    : yieldPct >= 40
                    ? "status-badge status-pending"
                    : "status-badge status-rejected";

                return (
                  <tr key={row.id}>
                    <td>
                      <input
                        type="text"
                        value={row.name}
                        disabled={disabled}
                        onChange={(e) => updateProduct(row.id, { name: e.target.value })}
                        placeholder={t("Target Product")}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={row.formula}
                        disabled={disabled}
                        onChange={(e) => updateProduct(row.id, { formula: e.target.value })}
                        placeholder="e.g. C12H10"
                        style={{ width: "90px" }}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        value={row.mw || ""}
                        disabled={disabled}
                        onChange={(e) =>
                          updateProduct(row.id, {
                            mw: parseFloat(e.target.value) || 0,
                          })
                        }
                        style={{ width: "75px" }}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.1"
                        value={row.ratio || 1.0}
                        disabled={disabled}
                        onChange={(e) =>
                          updateProduct(row.id, {
                            ratio: parseFloat(e.target.value) || 1.0,
                          })
                        }
                        style={{ width: "55px" }}
                      />
                    </td>
                    <td>
                      <span className="computed-val">{theoMoles.toFixed(2)}</span>
                    </td>
                    <td>
                      <span className="computed-val">{Math.round(theoMass * 10) / 10}</span>
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.1"
                        value={row.actualMass || ""}
                        disabled={disabled}
                        onChange={(e) =>
                          updateProduct(row.id, {
                            actualMass: parseFloat(e.target.value) || 0,
                          })
                        }
                        placeholder="Isolated mg"
                        style={{ width: "85px", fontWeight: "bold" }}
                      />
                    </td>
                    <td>
                      <span className={yieldBadgeClass}>
                        {yieldPct.toFixed(1)}%
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="button button-outline button-small"
                        disabled={disabled || products.length <= 1}
                        onClick={() => removeProduct(row.id)}
                        title={t("Remove product")}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="button button-outline button-small"
          onClick={addProduct}
          disabled={disabled}
          style={{ marginTop: "6px" }}
        >
          + {t("Add product")}
        </button>
      </div>

      {/* ACTION BUTTONS & INVENTORY CONSUMPTION */}
      <div className="stoichiometry-actions" style={{ marginTop: "12px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
        {onInsertMarkdown && (
          <button
            type="button"
            className="button button-primary button-small"
            onClick={handleInsertIntoEntry}
            disabled={disabled}
          >
            {t("Insert table into entry text")}
          </button>
        )}
        {onSaveAttachment && (
          <button
            type="button"
            className="button button-outline button-small"
            onClick={handleAttachTable}
            disabled={disabled || saving}
          >
            {saving ? t("Attaching...") : t("Attach JSON to entry")}
          </button>
        )}
        {onDeductStock && (
          <button
            type="button"
            className="button button-outline button-small"
            onClick={() => setShowDeductModal(true)}
            disabled={disabled || reagents.length === 0}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, borderColor: "#d8c8f7", color: "#3F1899" }}
          >
            📦 Deduct from inventory stock
          </button>
        )}
      </div>

      {deductSuccess && (
        <div style={{
          marginTop: 10,
          padding: "8px 12px",
          background: "#ecfdf5",
          border: "1px solid #a7f3d0",
          borderRadius: 6,
          color: "#065f46",
          fontSize: "0.85rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}>
          <span>{deductSuccess}</span>
          <button
            type="button"
            className="button-icon"
            onClick={() => setDeductSuccess(null)}
            style={{ fontSize: "0.8rem", padding: 0 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Stock Deduction Modal */}
      {showDeductModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: 600 }}>
            <header className="modal-header">
              <h3 style={{ margin: 0, color: "#3F1899", display: "flex", alignItems: "center", gap: 8 }}>
                📦 Deduct Reagent Consumption from Stock
              </h3>
              <button
                type="button"
                className="button-icon"
                onClick={() => setShowDeductModal(false)}
              >
                ✕
              </button>
            </header>

            <div className="modal-body" style={{ display: "grid", gap: 14 }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#493d68" }}>
                Verify the matched inventory items and calculated consumption for each reactant before updating laboratory stock records.
              </p>

              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ background: "#ece5fc", color: "#3F1899" }}>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Reactant</th>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Reaction Mass</th>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Matched Item</th>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Current Stock</th>
                    <th style={{ padding: "6px 8px", textAlign: "left" }}>Deduct Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {reagents.map((r) => {
                    const matchedId =
                      manualItemMappings[r.id] ??
                      inventoryItems.find(
                        (i) =>
                          i.name.toLowerCase() === r.name.toLowerCase() ||
                          (r.formula && i.catalog_number.toLowerCase() === r.formula.toLowerCase())
                      )?.id;

                    const matchedItem = inventoryItems.find((i) => i.id === matchedId);
                    const isGrams = matchedItem?.unit.toLowerCase() === "g" || matchedItem?.unit.toLowerCase() === "grams";
                    const deductAmount = matchedItem
                      ? isGrams
                        ? r.mass / 1000
                        : r.mass
                      : 0;

                    return (
                      <tr key={r.id} style={{ borderBottom: "1px solid #e8e0f7" }}>
                        <td style={{ padding: "6px 8px", fontWeight: 600 }}>{r.name}</td>
                        <td style={{ padding: "6px 8px" }}>{r.mass.toFixed(1)} mg</td>
                        <td style={{ padding: "6px 8px" }}>
                          <select
                            value={matchedId || ""}
                            onChange={(e) => {
                              const val = parseInt(e.target.value, 10);
                              setManualItemMappings((prev) => ({
                                ...prev,
                                [r.id]: val,
                              }));
                            }}
                            style={{ fontSize: "0.8rem", padding: "3px 6px", maxWidth: 160 }}
                          >
                            <option value="">-- Select Item --</option>
                            {inventoryItems.map((inv) => (
                              <option key={inv.id} value={inv.id}>
                                {inv.name} ({inv.quantity} {inv.unit})
                              </option>
                            ))}
                          </select>
                        </td>
                        <td style={{ padding: "6px 8px", color: "#6b5f88" }}>
                          {matchedItem ? `${matchedItem.quantity} ${matchedItem.unit}` : "-"}
                        </td>
                        <td style={{ padding: "6px 8px", fontWeight: 600, color: "#3F1899" }}>
                          {matchedItem ? `${deductAmount.toFixed(3)} ${matchedItem.unit}` : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <footer className="modal-footer" style={{ borderTop: "1px solid #e8e0f7", padding: "12px 16px", display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                className="button button-outline"
                onClick={() => setShowDeductModal(false)}
                disabled={deducting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button button-primary"
                disabled={deducting}
                onClick={async () => {
                  if (!onDeductStock) return;
                  setDeducting(true);
                  try {
                    const toDeduct: { itemId: number; itemName: string; amount: number; unit: string }[] = [];
                    reagents.forEach((r) => {
                      const matchedId =
                        manualItemMappings[r.id] ??
                        inventoryItems.find(
                          (i) =>
                            i.name.toLowerCase() === r.name.toLowerCase() ||
                            (r.formula && i.catalog_number.toLowerCase() === r.formula.toLowerCase())
                        )?.id;
                      const matchedItem = inventoryItems.find((i) => i.id === matchedId);
                      if (matchedItem) {
                        const isGrams = matchedItem.unit.toLowerCase() === "g" || matchedItem.unit.toLowerCase() === "grams";
                        const deductAmount = isGrams ? r.mass / 1000 : r.mass;
                        toDeduct.push({
                          itemId: matchedItem.id,
                          itemName: matchedItem.name,
                          amount: deductAmount,
                          unit: matchedItem.unit,
                        });
                      }
                    });

                    if (toDeduct.length === 0) {
                      alert("Please select at least one matched inventory item to deduct.");
                      setDeducting(false);
                      return;
                    }

                    await onDeductStock(toDeduct);
                    setDeductSuccess(`✓ Successfully deducted ${toDeduct.length} item(s) from inventory.`);
                    setShowDeductModal(false);
                  } catch (err) {
                    alert("Failed to deduct inventory: " + (err instanceof Error ? err.message : String(err)));
                  } finally {
                    setDeducting(false);
                  }
                }}
              >
                {deducting ? "Deducting..." : "Confirm Stock Deduction"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
