"""
SQLAlchemy models for Bio-PerformX database.
All measurements stored in metric units (cm, kg).
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import uuid


def generate_uuid():
    """Generate a UUID string for session IDs."""
    return str(uuid.uuid4())


class Session(Base):
    """
    Represents a report generation session with patient information.
    Each session has a unique ID used for file organization and data retrieval.
    """
    __tablename__ = "sessions"
    
    # Primary key
    session_id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Patient demographics
    patient_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)  # 'male' or 'female'
    
    # Physical measurements (always stored in metric)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)
    body_fat_pct = Column(Float, nullable=True)  # Optional, can be calculated
    
    # Activity and goals
    activity_level = Column(String(50), nullable=False)  # e.g., 'sedentary', 'light', 'moderate', 'active', 'very_active'
    weekly_weight_loss_lbs = Column(Float, nullable=False, default=0.0)
    
    # Report configuration
    report_type = Column(String(20), nullable=False, default='full')  # 'full' or 'minimal'
    respiratory_indication = Column(String(20), nullable=False, default='no')  # 'no', 'minor', 'severe'
    next_testing_month = Column(String(20), nullable=True)
    next_testing_year = Column(Integer, nullable=True)
    
    # RMR time window selection (in minutes from start of Pnoe data)
    rmr_time_start = Column(Float, nullable=True)  # Start time for RMR calculation
    rmr_time_end = Column(Float, nullable=True)    # End time for RMR calculation
    
    # Zone calculation mode
    zone_mode = Column(String(20), nullable=False, default='vt_based')  # 'vt_based' or 'manual'
    
    # File system path for generated files
    generation_folder_path = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    metrics = relationship("Metrics", back_populates="session", uselist=False, cascade="all, delete-orphan")
    uploaded_files = relationship("UploadedFile", back_populates="session", cascade="all, delete-orphan")
    static_charts = relationship("StaticChart", back_populates="session", cascade="all, delete-orphan")
    dynamic_charts = relationship("DynamicChart", back_populates="session", cascade="all, delete-orphan")


class Metrics(Base):
    """
    Stores all calculated metrics for a session.
    Each metric is its own column for easy querying and modification.
    """
    __tablename__ = "metrics"
    
    # Primary key
    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to session
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # ===== Spirometry Metrics =====
    fvc_best = Column(Float, nullable=True)
    fvc_predicted = Column(Float, nullable=True)
    fvc_percent = Column(Float, nullable=True)
    fev1_best = Column(Float, nullable=True)
    fev1_predicted = Column(Float, nullable=True)
    fev1_percent = Column(Float, nullable=True)
    fev1_fvc_best = Column(Float, nullable=True)
    fev1_fvc_predicted = Column(Float, nullable=True)
    fev1_fvc_percent = Column(Float, nullable=True)
    lung_capacity = Column(String(50), nullable=True)  # 'normal', 'mild', 'moderate', 'severe'
    
    # ===== VO2 and Cardiovascular Metrics =====
    vo2_max = Column(Float, nullable=True)           # Absolute VO2 max (L/min)
    vo2_max_per_kg = Column(Float, nullable=True)    # Relative VO2 max (mL/kg/min)
    vo2_max_category = Column(String(50), nullable=True)  # Fitness category
    peak_hr = Column(Integer, nullable=True)          # Peak heart rate (bpm)
    peak_vt = Column(Float, nullable=True)            # Peak tidal volume (L)
    peak_vt_hr = Column(Integer, nullable=True)       # HR at peak VT
    
    # ===== VT1/VT2 Thresholds =====
    vt1_hr = Column(Integer, nullable=True)           # Heart rate at VT1
    vt1_vo2 = Column(Float, nullable=True)            # VO2 at VT1
    vt1_speed = Column(Float, nullable=True)          # Speed at VT1
    vt2_hr = Column(Integer, nullable=True)           # Heart rate at VT2
    vt2_vo2 = Column(Float, nullable=True)            # VO2 at VT2
    vt2_speed = Column(Float, nullable=True)          # Speed at VT2
    
    # ===== Heart Rate Zones (can be VT-derived or manual) =====
    zone1_start = Column(Integer, nullable=True)
    zone1_end = Column(Integer, nullable=True)
    zone2_start = Column(Integer, nullable=True)
    zone2_end = Column(Integer, nullable=True)
    zone3_start = Column(Integer, nullable=True)
    zone3_end = Column(Integer, nullable=True)
    zone4_start = Column(Integer, nullable=True)
    zone4_end = Column(Integer, nullable=True)
    zone5_start = Column(Integer, nullable=True)
    zone5_end = Column(Integer, nullable=True)
    
    # ===== Fat Metabolism Metrics =====
    fat_max_value = Column(Float, nullable=True)      # Max fat oxidation (g/min)
    fat_max_hr = Column(Integer, nullable=True)       # HR at fat max
    fat_max_vo2 = Column(Float, nullable=True)        # VO2 at fat max
    fat_max_speed = Column(Float, nullable=True)      # Speed at fat max
    crossover_hr = Column(Integer, nullable=True)     # HR at CHO/FAT crossover (same as VT1)
    crossover_speed = Column(Float, nullable=True)    # Speed at crossover
    
    # ===== Metabolic Rate Metrics =====
    rmr_kcal = Column(Float, nullable=True)           # Resting metabolic rate (kcal/day)
    rmr_vo2 = Column(Float, nullable=True)            # VO2 at rest
    rest_fat_percentage = Column(Float, nullable=True)  # Fat % contribution at rest
    rest_carb_percentage = Column(Float, nullable=True) # Carb % contribution at rest
    tdee = Column(Float, nullable=True)               # Total daily energy expenditure
    
    # ===== Nutrition Metrics =====
    calorie_deficit = Column(Float, nullable=True)    # Daily calorie deficit
    target_calories = Column(Float, nullable=True)    # Target daily calories
    
    # Protein (EDITABLE - other macros derived from this)
    protein_g = Column(Float, nullable=True)
    
    # Carbs and Fat (calculated, maintaining ratio when protein changes)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fibre_g = Column(Float, nullable=True)
    
    # Original ratio storage (for recalculation when protein changes)
    original_carbs_ratio = Column(Float, nullable=True)  # carbs / (carbs + fat) ratio
    original_fat_ratio = Column(Float, nullable=True)    # fat / (carbs + fat) ratio
    
    # Weekday macros (deficit days)
    weekday_protein_g = Column(Float, nullable=True)
    weekday_carbs_g = Column(Float, nullable=True)
    weekday_fat_g = Column(Float, nullable=True)
    weekday_fibre_g = Column(Float, nullable=True)
    weekday_calories = Column(Float, nullable=True)
    
    # Weekend macros (non-deficit days)
    weekend_protein_g = Column(Float, nullable=True)
    weekend_carbs_g = Column(Float, nullable=True)
    weekend_fat_g = Column(Float, nullable=True)
    weekend_fibre_g = Column(Float, nullable=True)
    weekend_calories = Column(Float, nullable=True)
    
    # ===== VO2 Efficiency Metrics =====
    vo2_pulse_drop_bpm = Column(Integer, nullable=True)     # HR where VO2 pulse efficiency drops
    vo2_pulse_drops = Column(Boolean, nullable=True)         # Whether there's a drop
    vo2_breath_drop_bpm = Column(Integer, nullable=True)    # HR where VO2 breath efficiency drops
    vo2_breath_drops = Column(Boolean, nullable=True)        # Whether there's a drop
    
    # ===== Recovery Metrics =====
    cardiac_recovery_pct = Column(Float, nullable=True)     # Cardiac recovery %
    metabolic_recovery_pct = Column(Float, nullable=True)   # CO2 recovery %
    breath_recovery_pct = Column(Float, nullable=True)      # Breathing frequency recovery %
    
    # ===== Resting Heart Rate =====
    resting_hr = Column(Integer, nullable=True)
    resting_hr_category = Column(String(50), nullable=True)
    
    # ===== Zone Analysis Metrics (per zone) =====
    # Stored as JSON strings for flexibility
    zone_analysis_json = Column(Text, nullable=True)  # Full zone analysis data
    
    # ===== Oxygenation Metrics (from Train.Red analysis) =====
    oxygenation_metrics_json = Column(Text, nullable=True)  # SmO2 metrics as JSON
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    session = relationship("Session", back_populates="metrics")


class UploadedFile(Base):
    """
    Tracks uploaded files for each session.
    """
    __tablename__ = "uploaded_files"
    
    file_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    
    file_type = Column(String(50), nullable=False)  # 'spirometry_pdf', 'pnoe_csv', 'oxygenation_csv', 'seca_xlsx', 'spirometry_csv'
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path relative to session folder
    
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    session = relationship("Session", back_populates="uploaded_files")


class StaticChart(Base):
    """
    Tracks static (immutable) charts generated from raw data.
    These charts only change if the underlying data file changes.
    """
    __tablename__ = "static_charts"
    
    chart_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    
    chart_type = Column(String(50), nullable=False)  # 'spirometry', 'vt', 'relative_vo2', 'fuel_utilization', 'vo2_pulse', 'vo2_breath', 'fat_carbs', 'recovery', 'smo2'
    file_path = Column(String(500), nullable=False)  # Path relative to session folder
    
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    session = relationship("Session", back_populates="static_charts")


class DynamicChart(Base):
    """
    Tracks dynamic charts that depend on editable metrics.
    These charts are regenerated when metrics change.
    """
    __tablename__ = "dynamic_charts"
    
    chart_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    
    chart_type = Column(String(50), nullable=False)  # 'body_composition', 'body_fat_percentage', 'rmr', 'fuel_source', 'vo2_max_table', 'hr_zones_table', 'rhr_table'
    file_path = Column(String(500), nullable=False)  # Path relative to session folder
    
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    session = relationship("Session", back_populates="dynamic_charts")
