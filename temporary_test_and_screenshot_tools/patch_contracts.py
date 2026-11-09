import os

path = "backend/eln_common/contracts.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

if "class MicroplateRead" not in text:
    appendix = """

class PlateWellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coordinate: str
    row_letter: str
    col_number: int
    role: str
    sample_name: str
    sample_id: int | None
    replicate_group: str
    standard_concentration: float | None
    concentration_unit: str
    dilution_factor: float
    raw_value: float | None
    corrected_value: float | None
    calculated_concentration: float | None


class MicroplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int | None
    experiment_id: int | None
    name: str
    plate_format: str
    rows: int
    cols: int
    description: str
    assay_type: str
    wavelength: str
    measurement_unit: str
    created_at: datetime
    updated_at: datetime
    wells: list[PlateWellRead]
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(appendix)
    print("Added PlateWellRead and MicroplateRead to contracts.py")
else:
    print("Already present in contracts.py")

