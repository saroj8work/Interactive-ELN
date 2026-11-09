with open("frontend/src/api.ts", "a", encoding="utf-8") as f:
    f.write('''

// ==========================================
// Phase 1: Microplate & Assay Analysis API
// ==========================================

export interface PlateWell {
  id: number;
  coordinate: string;
  row_letter: string;
  col_number: number;
  role: "sample" | "standard" | "control_pos" | "control_neg" | "blank" | "empty";
  sample_name: string;
  sample_id: number | null;
  replicate_group: string;
  standard_concentration: number | null;
  concentration_unit: string;
  dilution_factor: number;
  raw_value: number | null;
  corrected_value: number | null;
  calculated_concentration: number | null;
}

export interface Microplate {
  id: number;
  organization_id: number;
  project_id: number | null;
  experiment_id: number | null;
  name: string;
  plate_format: "96-well" | "384-well" | "24-well";
  rows: number;
  cols: number;
  description: string;
  assay_type: string;
  wavelength: string;
  measurement_unit: string;
  created_at: string;
  updated_at: string;
  wells: PlateWell[];
}

export interface HeatmapMatrix {
  plate_id: number;
  name: string;
  rows: number;
  cols: number;
  measurement_unit: string;
  matrix: { coordinate: string; raw_value: number | null; normalized: number; role: string }[][];
  min_value: number | null;
  max_value: number | null;
}

export const platesApi = {
  list: (projectId?: number | null, experimentId?: number | null) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<Microplate[]>(`/api/plates${qs}`);
  },
  get: (plateId: number) => authRequest<Microplate>(`/api/plates/${plateId}`),
  create: (data: {
    name: string;
    plate_format?: string;
    project_id?: number | null;
    experiment_id?: number | null;
    description?: string;
    assay_type?: string;
    wavelength?: string;
    measurement_unit?: string;
  }) => authRequest<Microplate>("/api/plates", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  updateWells: (plateId: number, wells: Partial<PlateWell>[]) =>
    authRequest<Microplate>(`/api/plates/${plateId}/wells`, {
      method: "PUT",
      body: JSON.stringify({ wells }),
    }),
  calculate: (plateId: number) =>
    authRequest<Record<string, any>>(`/api/plates/${plateId}/calculate`, {
      method: "POST",
    }),
  getHeatmap: (plateId: number) =>
    authRequest<HeatmapMatrix>(`/api/plates/${plateId}/heatmap`),
  uploadCsv: (plateId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authRequest<{ plate_id: number; updated_wells: number; status: string }>(
      `/api/plates/${plateId}/readings/csv`,
      {
        method: "POST",
        body: fd,
      }
    );
  },
};
''')

print("Added platesApi to frontend/src/api.ts")

