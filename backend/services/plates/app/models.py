from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from eln_common.database import Base


class Microplate(Base):
    __tablename__ = "microplates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    experiment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plate_format: Mapped[str] = mapped_column(String(32), default="96-well") # 96-well, 384-well, 24-well
    rows: Mapped[int] = mapped_column(Integer, default=8)
    cols: Mapped[int] = mapped_column(Integer, default=12)
    description: Mapped[str] = mapped_column(Text, default="")
    assay_type: Mapped[str] = mapped_column(String(100), default="ELISA Absorbance")
    wavelength: Mapped[str] = mapped_column(String(32), default="450 nm")
    measurement_unit: Mapped[str] = mapped_column(String(32), default="OD")
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    wells: Mapped[List["PlateWell"]] = relationship("PlateWell", back_populates="plate", cascade="all, delete-orphan")


class PlateWell(Base):
    __tablename__ = "plate_wells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate_id: Mapped[int] = mapped_column(Integer, ForeignKey("microplates.id", ondelete="CASCADE"), nullable=False, index=True)
    row_letter: Mapped[str] = mapped_column(String(4), nullable=False) # A, B, C...
    col_number: Mapped[int] = mapped_column(Integer, nullable=False) # 1, 2, 3...
    coordinate: Mapped[str] = mapped_column(String(8), nullable=False, index=True) # A1, H12
    role: Mapped[str] = mapped_column(String(32), default="sample") # sample, standard, control_pos, control_neg, blank, empty
    sample_name: Mapped[str] = mapped_column(String(120), default="")
    sample_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    replicate_group: Mapped[str] = mapped_column(String(32), default="")
    standard_concentration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    concentration_unit: Mapped[str] = mapped_column(String(32), default="ng/mL")
    dilution_factor: Mapped[float] = mapped_column(Float, default=1.0)
    raw_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    corrected_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calculated_concentration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    plate: Mapped["Microplate"] = relationship("Microplate", back_populates="wells")

