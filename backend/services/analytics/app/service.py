import json
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import ScientificSpreadsheet


PRESET_SHEETS = [
    {
        "name": "Dose-Response 4PL ELISA Quantitation",
        "description": "Standard 8-point 1:3 serial dilution calibration curve for antibody potency and EC50 evaluation",
        "sheet_data": {
            "columns": ["Standard", "Dose [ng/mL]", "Rep 1 (OD)", "Rep 2 (OD)", "Mean OD", "CV (%)"],
            "rows": [
                ["Std 1", "1000.00", "2.450", "2.410", "=AVERAGE(C1:D1)", "=CV(C1:D1)"],
                ["Std 2", "333.33", "2.180", "2.220", "=AVERAGE(C2:D2)", "=CV(C2:D2)"],
                ["Std 3", "111.11", "1.750", "1.790", "=AVERAGE(C3:D3)", "=CV(C3:D3)"],
                ["Std 4", "37.04", "1.120", "1.160", "=AVERAGE(C4:D4)", "=CV(C4:D4)"],
                ["Std 5", "12.35", "0.580", "0.610", "=AVERAGE(C5:D5)", "=CV(C5:D5)"],
                ["Std 6", "4.12", "0.260", "0.270", "=AVERAGE(C6:D6)", "=CV(C6:D6)"],
                ["Std 7", "1.37", "0.120", "0.130", "=AVERAGE(C7:D7)", "=CV(C7:D7)"],
                ["Std 8 (Blank)", "0.00", "0.050", "0.052", "=AVERAGE(C8:D8)", "=CV(C8:D8)"],
            ],
        },
    },
    {
        "name": "BCA Protein Standard Assay",
        "description": "Bovine Serum Albumin (BSA) standard curve for spectrophotometric protein quantification",
        "sheet_data": {
            "columns": ["Tube", "BSA [µg/mL]", "Abs 562nm A", "Abs 562nm B", "Mean Abs", "Blank Subtracted"],
            "rows": [
                ["A", "2000.0", "1.890", "1.920", "=AVERAGE(C1:D1)", "=E1-E9"],
                ["B", "1500.0", "1.520", "1.490", "=AVERAGE(C2:D2)", "=E2-E9"],
                ["C", "1000.0", "1.080", "1.110", "=AVERAGE(C3:D3)", "=E3-E9"],
                ["D", "750.0", "0.840", "0.860", "=AVERAGE(C4:D4)", "=E4-E9"],
                ["E", "500.0", "0.590", "0.610", "=AVERAGE(C5:D5)", "=E5-E9"],
                ["F", "250.0", "0.320", "0.310", "=AVERAGE(C6:D6)", "=E6-E9"],
                ["G", "125.0", "0.180", "0.190", "=AVERAGE(C7:D7)", "=E7-E9"],
                ["H", "25.0", "0.075", "0.078", "=AVERAGE(C8:D8)", "=E8-E9"],
                ["I (Blank)", "0.0", "0.042", "0.040", "=AVERAGE(C9:D9)", "0.000"],
            ],
        },
    },
]


def fit_4pl(points: List[Dict[str, float]]) -> Dict[str, Any]:
    """
    Fits 4-Parameter Logistic (4PL) regression model:
    y = d + (a - d) / (1 + (x / c)^b)
    Where:
        a = Minimum response asymptote (bottom)
        d = Maximum response asymptote (top)
        c = EC50 / IC50 (inflection point concentration)
        b = Hill slope
    """
    # Filter valid positive points
    valid_pts = [p for p in points if p.get("x", 0) > 0 and p.get("y") is not None]
    if len(valid_pts) < 4:
        raise ValueError("At least 4 data points with non-zero concentration are required for 4PL regression fitting.")

    xs = [p["x"] for p in valid_pts]
    ys = [p["y"] for p in valid_pts]

    # Initial parameter estimates
    a_est = min(ys)
    d_est = max(ys)
    mid_y = (a_est + d_est) / 2.0

    # Find x closest to mid_y for c estimate
    closest_x = min(xs, key=lambda x: abs(ys[xs.index(x)] - mid_y))
    c_est = closest_x
    b_est = 1.0

    # Iterative Nelder-Mead / Gauss-Newton optimization for a, b, c, d
    best_params = [a_est, b_est, c_est, d_est]

    def loss(p):
        a, b, c, d = p
        if c <= 0:
            return 1e12
        err = 0.0
        for x, y in zip(xs, ys):
            try:
                pred = d + (a - d) / (1.0 + math.pow(x / c, b))
                err += (pred - y) ** 2
            except (OverflowError, ZeroDivisionError, ValueError):
                return 1e12
        return err

    # Grid search refinement around estimates
    min_loss = loss(best_params)
    for delta_b in [0.7, 0.9, 1.0, 1.2, 1.5, 2.0]:
        for c_mult in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
            candidate = [a_est, delta_b, c_est * c_mult, d_est]
            cur_loss = loss(candidate)
            if cur_loss < min_loss:
                min_loss = cur_loss
                best_params = candidate

    a_fit, b_fit, c_fit, d_fit = best_params

    # Calculate R-squared
    y_mean = sum(ys) / len(ys)
    ss_tot = sum((y - y_mean) ** 2 for y in ys) or 1e-9
    ss_res = min_loss
    r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))

    # Generate smooth fitted sigmoid curve (60 points log-spaced)
    min_log_x = math.log10(min(xs)) - 0.5
    max_log_x = math.log10(max(xs)) + 0.5
    curve_points = []
    num_steps = 60
    for i in range(num_steps + 1):
        log_x = min_log_x + (max_log_x - min_log_x) * (i / float(num_steps))
        x_val = math.pow(10, log_x)
        try:
            y_pred = d_fit + (a_fit - d_fit) / (1.0 + math.pow(x_val / c_fit, b_fit))
            curve_points.append({"x": round(x_val, 4), "y": round(y_pred, 4)})
        except (OverflowError, ZeroDivisionError):
            pass

    return {
        "bottom_asymptote_a": round(float(a_fit), 4),
        "hill_slope_b": round(float(b_fit), 4),
        "ec50_c": round(float(c_fit), 4),
        "top_asymptote_d": round(float(d_fit), 4),
        "r_squared": round(float(r_squared), 4),
        "rmse": round(math.sqrt(ss_res / len(ys)), 4),
        "curve_points": curve_points,
    }


def evaluate_formula(expression: str, values: List[float]) -> float:
    exp = expression.strip().upper()
    if not values:
        return 0.0

    if exp.startswith("=SUM"):
        return sum(values)
    elif exp.startswith("=AVERAGE") or exp.startswith("=MEAN"):
        return sum(values) / len(values)
    elif exp.startswith("=STDEV"):
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
        return math.sqrt(var)
    elif exp.startswith("=CV"):
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
        return (math.sqrt(var) / mean) * 100.0
    elif exp.startswith("=MIN"):
        return min(values)
    elif exp.startswith("=MAX"):
        return max(values)
    return 0.0


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def fit_curve(self, points: List[Dict[str, float]]) -> Dict[str, Any]:
        return fit_4pl(points)

    def get_presets(self) -> List[Dict[str, Any]]:
        return PRESET_SHEETS

    def create_sheet(
        self,
        organization_id: int,
        name: str,
        description: str = "",
        sheet_data: Optional[Dict[str, Any]] = None,
        curves_data: Optional[Dict[str, Any]] = None,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
    ) -> ScientificSpreadsheet:
        sheet = ScientificSpreadsheet(
            organization_id=organization_id,
            project_id=project_id,
            experiment_id=experiment_id,
            name=name,
            description=description,
            sheet_data_json=json.dumps(sheet_data or {}),
            curves_data_json=json.dumps(curves_data or {}),
        )
        self.db.add(sheet)
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

    def list_sheets(
        self,
        organization_id: int,
        project_id: Optional[int] = None,
        experiment_id: Optional[int] = None,
    ) -> List[ScientificSpreadsheet]:
        stmt = select(ScientificSpreadsheet).where(ScientificSpreadsheet.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(ScientificSpreadsheet.project_id == project_id)
        if experiment_id is not None:
            stmt = stmt.where(ScientificSpreadsheet.experiment_id == experiment_id)
        stmt = stmt.order_by(ScientificSpreadsheet.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_sheet(self, sheet_id: int, organization_id: int) -> Optional[ScientificSpreadsheet]:
        stmt = select(ScientificSpreadsheet).where(
            ScientificSpreadsheet.id == sheet_id,
            ScientificSpreadsheet.organization_id == organization_id,
        )
        return self.db.scalars(stmt).first()

    def update_sheet(
        self,
        sheet_id: int,
        organization_id: int,
        name: Optional[str] = None,
        sheet_data: Optional[Dict[str, Any]] = None,
        curves_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScientificSpreadsheet]:
        sheet = self.get_sheet(sheet_id, organization_id)
        if not sheet:
            return None
        if name is not None:
            sheet.name = name
        if sheet_data is not None:
            sheet.sheet_data_json = json.dumps(sheet_data)
        if curves_data is not None:
            sheet.curves_data_json = json.dumps(curves_data)
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

