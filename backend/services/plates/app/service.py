import csv
import io
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Microplate, PlateWell


def get_grid_dimensions(plate_format: str) -> tuple[int, int]:
    if plate_format == "384-well":
        return 16, 24
    elif plate_format == "24-well":
        return 4, 6
    return 8, 12 # Default 96-well


def row_letter_for_index(idx: int) -> str:
    # 0 -> A, 25 -> Z, 26 -> AA
    result = ""
    while idx >= 0:
        result = chr(65 + (idx % 26)) + result
        idx = (idx // 26) - 1
    return result


class PlateService:
    def __init__(self, db: Session):
        self.db = db

    def create_plate(
        self,
        organization_id: int,
        user_id: int,
        name: str,
        plate_format: str = "96-well",
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        description: str = "",
        assay_type: str = "ELISA Absorbance",
        wavelength: str = "450 nm",
        measurement_unit: str = "OD"
    ) -> Microplate:
        rows, cols = get_grid_dimensions(plate_format)
        plate = Microplate(
            organization_id=organization_id,
            project_id=project_id,
            experiment_id=experiment_id,
            name=name,
            plate_format=plate_format,
            rows=rows,
            cols=cols,
            description=description,
            assay_type=assay_type,
            wavelength=wavelength,
            measurement_unit=measurement_unit,
            created_by_user_id=user_id,
        )
        self.db.add(plate)
        self.db.flush()

        # Initialize empty wells grid
        wells: List[PlateWell] = []
        for r in range(rows):
            r_letter = row_letter_for_index(r)
            for c in range(1, cols + 1):
                coord = f"{r_letter}{c}"
                wells.append(PlateWell(
                    plate_id=plate.id,
                    row_letter=r_letter,
                    col_number=c,
                    coordinate=coord,
                    role="empty",
                ))
        self.db.add_all(wells)
        self.db.commit()
        self.db.refresh(plate)
        return plate

    def get_plate(self, plate_id: int, organization_id: int) -> Optional[Microplate]:
        return self.db.scalar(
            select(Microplate).where(
                Microplate.id == plate_id,
                Microplate.organization_id == organization_id
            )
        )

    def list_plates(
        self,
        organization_id: int,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Microplate]:
        stmt = select(Microplate).where(Microplate.organization_id == organization_id)
        if project_id:
            stmt = stmt.where(Microplate.project_id == project_id)
        if experiment_id:
            stmt = stmt.where(Microplate.experiment_id == experiment_id)
        stmt = stmt.order_by(Microplate.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def update_wells_batch(
        self,
        plate_id: int,
        organization_id: int,
        well_updates: List[Dict[str, Any]]
    ) -> Microplate:
        plate = self.get_plate(plate_id, organization_id)
        if not plate:
            raise ValueError("Plate not found.")

        well_map = {w.coordinate: w for w in plate.wells}
        for u in well_updates:
            coord = u.get("coordinate", "").upper().strip()
            if coord in well_map:
                w = well_map[coord]
                if "role" in u:
                    w.role = u["role"]
                if "sample_name" in u:
                    w.sample_name = u["sample_name"]
                if "sample_id" in u:
                    w.sample_id = u["sample_id"]
                if "replicate_group" in u:
                    w.replicate_group = u["replicate_group"]
                if "standard_concentration" in u:
                    w.standard_concentration = u["standard_concentration"]
                if "concentration_unit" in u:
                    w.concentration_unit = u["concentration_unit"]
                if "dilution_factor" in u:
                    w.dilution_factor = float(u["dilution_factor"])
                if "raw_value" in u:
                    w.raw_value = float(u["raw_value"]) if u["raw_value"] is not None else None

        plate.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(plate)
        return plate

    def import_plate_reader_csv(
        self,
        plate_id: int,
        organization_id: int,
        csv_content: str
    ) -> int:
        plate = self.get_plate(plate_id, organization_id)
        if not plate:
            raise ValueError("Plate not found.")

        well_map = {w.coordinate: w for w in plate.wells}
        updated_count = 0

        # Try parsing as 8x12 grid first or coordinate list
        lines = [line.strip() for line in csv_content.splitlines() if line.strip()]
        reader = csv.reader(lines)
        rows_data = list(reader)

        # Check if row-labeled grid (e.g. Row A, B, C... in first column)
        is_matrix = any(r and r[0].strip().upper() in ("A", "B", "C", "D") for r in rows_data)

        if is_matrix:
            for row in rows_data:
                if not row:
                    continue
                first_cell = row[0].strip().upper()
                if len(first_cell) == 1 and first_cell.isalpha():
                    row_letter = first_cell
                    for col_idx, val in enumerate(row[1:], start=1):
                        coord = f"{row_letter}{col_idx}"
                        if coord in well_map:
                            try:
                                well_map[coord].raw_value = float(val.strip())
                                updated_count += 1
                            except (ValueError, TypeError):
                                pass
        else:
            # Pair format: "A1, 0.425" or header "Well, OD"
            for row in rows_data:
                if len(row) >= 2:
                    potential_coord = row[0].strip().upper()
                    if potential_coord in well_map:
                        try:
                            well_map[potential_coord].raw_value = float(row[1].strip())
                            updated_count += 1
                        except (ValueError, TypeError):
                            pass

        plate.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return updated_count

    def calculate_quantitation(
        self,
        plate_id: int,
        organization_id: int
    ) -> Dict[str, Any]:
        plate = self.get_plate(plate_id, organization_id)
        if not plate:
            raise ValueError("Plate not found.")

        # 1. Blank background calculation
        blanks = [w.raw_value for w in plate.wells if w.role == "blank" and w.raw_value is not None]
        blank_mean = sum(blanks) / len(blanks) if blanks else 0.0

        for w in plate.wells:
            if w.raw_value is not None:
                w.corrected_value = max(0.0, round(w.raw_value - blank_mean, 5))
            else:
                w.corrected_value = None

        # 2. Standard curve linear regression (y = mx + b)
        # where y = corrected_value, x = standard_concentration
        standards = [
            (w.standard_concentration, w.corrected_value)
            for w in plate.wells
            if w.role == "standard"
            and w.standard_concentration is not None
            and w.corrected_value is not None
        ]

        slope = 0.0
        intercept = 0.0
        r_squared = 0.0

        if len(standards) >= 2:
            n = len(standards)
            sum_x = sum(s[0] for s in standards)
            sum_y = sum(s[1] for s in standards)
            sum_xx = sum(s[0] ** 2 for s in standards)
            sum_yy = sum(s[1] ** 2 for s in standards)
            sum_xy = sum(s[0] * s[1] for s in standards)

            denom = (n * sum_xx - sum_x ** 2)
            if denom != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denom
                intercept = (sum_y - slope * sum_x) / n

                # Compute R-squared
                y_mean = sum_y / n
                ss_tot = sum((s[1] - y_mean) ** 2 for s in standards)
                ss_res = sum((s[1] - (slope * s[0] + intercept)) ** 2 for s in standards)
                r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

        # 3. Calculate Sample concentrations: x = (y - intercept) / slope * dilution_factor
        quantitated_count = 0
        for w in plate.wells:
            if w.role in ("sample", "control_pos", "control_neg") and w.corrected_value is not None and slope > 0:
                calc = ((w.corrected_value - intercept) / slope) * (w.dilution_factor or 1.0)
                w.calculated_concentration = round(max(0.0, calc), 3)
                quantitated_count += 1
            elif w.role == "standard":
                w.calculated_concentration = w.standard_concentration

        plate.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return {
            "blank_mean": round(blank_mean, 4),
            "curve": {
                "slope": round(slope, 5),
                "intercept": round(intercept, 5),
                "r_squared": round(r_squared, 4),
                "formula": f"OD = {slope:.4f} * Conc + {intercept:.4f}",
                "standard_points": len(standards),
            },
            "quantitated_wells": quantitated_count,
        }

    def get_heatmap_matrix(
        self,
        plate_id: int,
        organization_id: int
    ) -> Dict[str, Any]:
        plate = self.get_plate(plate_id, organization_id)
        if not plate:
            raise ValueError("Plate not found.")

        vals = [w.raw_value for w in plate.wells if w.raw_value is not None]
        min_val = min(vals) if vals else 0.0
        max_val = max(vals) if vals else 1.0
        val_range = (max_val - min_val) if (max_val - min_val) > 0 else 1.0

        grid = []
        for r in range(plate.rows):
            r_letter = row_letter_for_index(r)
            row_items = []
            for c in range(1, plate.cols + 1):
                coord = f"{r_letter}{c}"
                w = next((well for well in plate.wells if well.coordinate == coord), None)
                if w:
                    intensity = 0.0
                    if w.raw_value is not None:
                        intensity = round((w.raw_value - min_val) / val_range, 3)
                    row_items.append({
                        "id": w.id,
                        "coordinate": w.coordinate,
                        "role": w.role,
                        "sample_name": w.sample_name,
                        "raw_value": w.raw_value,
                        "corrected_value": w.corrected_value,
                        "calculated_concentration": w.calculated_concentration,
                        "concentration_unit": w.concentration_unit,
                        "intensity": intensity,
                    })
                else:
                    row_items.append(None)
            grid.append({
                "row_letter": r_letter,
                "wells": row_items,
            })

        return {
            "plate_id": plate.id,
            "plate_name": plate.name,
            "format": plate.plate_format,
            "wavelength": plate.wavelength,
            "min_reading": min_val,
            "max_reading": max_val,
            "grid": grid,
        }

