"""
FastAPI application for medical report generation.

This API provides endpoints for uploading patient data, calculating metrics,
previewing reports, editing metrics, and generating PDF reports.

Refactored to use:
- SQLAlchemy database for session persistence
- Separated static/dynamic chart generation
- Metrics calculator for all calculations
- Page context formatter for report generation
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request as StarletteRequest

# Database imports
from app.db.database import get_db, init_db, get_session_dir, GENERATED_DIR
from app.db.models import Session, Metrics, UploadedFile, StaticChart, DynamicChart

# Service imports
from app.services.metrics_calculator import MetricsCalculator
from app.services.static_chart_generator import StaticChartGenerator
from app.services.dynamic_chart_table_generator import DynamicChartTableGenerator
from app.services.spirometry_table_extractor import extract_spirometry_table_from_pdf
from app.services.unified_report_generator import UnifiedReportGenerator

app = FastAPI(
    title="Medical Report Generation API",
    description="API for generating medical performance reports with analysis and graphs",
    version="3.0.0",
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-change-in-production"),
)


# Add security headers middleware to allow external scripts
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https:; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https:; img-src 'self' data: https:;"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Mount static files (if static directory exists)
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
jinja_env = Environment(loader=FileSystemLoader("app/templates"))


class ReportResponse(BaseModel):
    message: str
    report_path: str
    session_id: str


def render_template(template_name: str, context: dict) -> HTMLResponse:
    """Helper function to render Jinja2 templates"""
    template = jinja_env.get_template(template_name)
    html_content = template.render(**context)
    return HTMLResponse(content=html_content, media_type="text/html")


def convert_weight_to_kg(weight_value: float, weight_unit: str) -> float:
    """Convert weight to kg based on unit."""
    if weight_unit.lower() == "lbs":
        return weight_value / 2.20462
    return weight_value


def convert_height_to_cm(height_value: float, height_unit: str) -> float:
    """Convert height to cm based on unit."""
    if height_unit.lower() in ["in", "inches"]:
        return height_value * 2.54
    elif height_unit.lower() in ["ft", "feet"]:
        return height_value * 30.48
    return height_value

def _build_vo2_max_table_data(age: int, gender: str, vo2_max_value: float) -> dict:
    """
    Build VO2 max table data based on age and gender.
    
    Returns dict with 'columns' (list of column headers) and 'data' (list of row data).
    """
    # VO2 max categories and ranges vary by age and gender
    # Using standard fitness categories
    columns = ["Age/Gender", "Very Poor", "Poor", "Fair", "Good", "Excellent", "Superior"]
    
    # Get age group label
    if age < 30:
        age_group = "20-29"
    elif age < 40:
        age_group = "30-39"
    elif age < 50:
        age_group = "40-49"
    elif age < 60:
        age_group = "50-59"
    else:
        age_group = "60+"
    
    gender_label = "M" if gender.lower() == "male" else "F"
    age_gender = f"{age_group} ({gender_label})"
    
    # Reference values for VO2 max by age/gender (ml/kg/min)
    if gender.lower() == "male":
        if age < 30:
            ranges = ["<24", "24-30", "31-37", "38-48", "49-55", ">55"]
        elif age < 40:
            ranges = ["<23", "23-29", "30-36", "37-44", "45-52", ">52"]
        elif age < 50:
            ranges = ["<21", "21-27", "28-34", "35-41", "42-49", ">49"]
        elif age < 60:
            ranges = ["<19", "19-25", "26-32", "33-39", "40-47", ">47"]
        else:
            ranges = ["<17", "17-23", "24-30", "31-37", "38-44", ">44"]
    else:  # female
        if age < 30:
            ranges = ["<21", "21-27", "28-34", "35-41", "42-49", ">49"]
        elif age < 40:
            ranges = ["<20", "20-26", "27-33", "34-40", "41-47", ">47"]
        elif age < 50:
            ranges = ["<18", "18-24", "25-31", "32-38", "39-45", ">45"]
        elif age < 60:
            ranges = ["<16", "16-22", "23-29", "30-36", "37-43", ">43"]
        else:
            ranges = ["<14", "14-20", "21-27", "28-34", "35-41", ">41"]
    
    data = [[age_gender] + ranges]
    
    return {"columns": columns, "data": data}


def _build_hr_zones_table_data(metrics: dict) -> dict:
    """
    Build heart rate zones table data from calculated metrics.
    
    Returns dict with 'columns' (list of column headers) and 'data' (list of row data).
    """
    columns = ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"]
    
    def fmt_range(start, end):
        if start is None or end is None:
            return "-"
        return f"{int(start)}-{int(end)}"
    
    # Build data rows
    data = [
        # Training Focus
        ["Recovery", "Fat Burn", "Aerobic", "Threshold", "Max Effort"],
        # Intensity
        ["50-60% Max HR", "60-70% Max HR", "70-80% Max HR", "80-90% Max HR", "90-100% Max HR"],
        # HR BPM ranges
        [
            fmt_range(metrics.get("zone1_start"), metrics.get("zone1_end")),
            fmt_range(metrics.get("zone2_start"), metrics.get("zone2_end")),
            fmt_range(metrics.get("zone3_start"), metrics.get("zone3_end")),
            fmt_range(metrics.get("zone4_start"), metrics.get("zone4_end")),
            fmt_range(metrics.get("zone5_start"), metrics.get("zone5_end")),
        ],
        # Duration
        ["30-60 min", "45-90 min", "20-40 min", "10-20 min", "5-10 min"],
        # Frequency
        ["Daily", "3-4x/week", "2-3x/week", "1-2x/week", "1x/week"],
        # Feel
        ["Very Light", "Light", "Moderate", "Hard", "Very Hard"],
        # Talk Test
        ["Easy conversation", "Can talk", "Short phrases", "Few words", "Can't talk"],
        # Breathing
        ["Normal", "Slightly elevated", "Elevated", "Heavy", "Maximal"],
    ]
    
    return {"columns": columns, "data": data}


def _build_rhr_table_data(age: int, gender: str, resting_hr: float) -> dict:
    """
    Build Resting Heart Rate table data based on age and gender.
    
    Returns dict with 'columns', 'data', and 'category'.
    """
    columns = ["Age/Gender", "Poor", "Below Avg", "Average", "Above Avg", "Good", "Excellent", "Athlete"]
    
    # Get age group label
    if age < 26:
        age_group = "18-25"
    elif age < 36:
        age_group = "26-35"
    elif age < 46:
        age_group = "36-45"
    elif age < 56:
        age_group = "46-55"
    elif age < 66:
        age_group = "56-65"
    else:
        age_group = "65+"
    
    gender_label = "M" if gender.lower() == "male" else "F"
    age_gender = f"{age_group} ({gender_label})"
    
    # Reference values for RHR by age/gender (bpm)
    if gender.lower() == "male":
        if age < 26:
            ranges = ["85+", "76-84", "71-75", "70-73", "62-68", "56-61", "49-55"]
            thresholds = [85, 76, 71, 70, 62, 56, 49]
        elif age < 36:
            ranges = ["83+", "75-82", "71-74", "65-70", "62-64", "55-61", "49-54"]
            thresholds = [83, 75, 71, 65, 62, 55, 49]
        elif age < 46:
            ranges = ["84+", "76-83", "71-75", "66-70", "62-65", "56-61", "50-55"]
            thresholds = [84, 76, 71, 66, 62, 56, 50]
        elif age < 56:
            ranges = ["85+", "77-84", "72-76", "67-71", "63-66", "57-62", "51-56"]
            thresholds = [85, 77, 72, 67, 63, 57, 51]
        elif age < 66:
            ranges = ["85+", "76-84", "72-75", "68-71", "63-67", "57-62", "51-56"]
            thresholds = [85, 76, 72, 68, 63, 57, 51]
        else:
            ranges = ["84+", "76-83", "71-75", "67-70", "62-66", "56-61", "50-55"]
            thresholds = [84, 76, 71, 67, 62, 56, 50]
    else:  # female
        if age < 26:
            ranges = ["86+", "79-85", "74-78", "70-73", "66-69", "61-65", "54-60"]
            thresholds = [86, 79, 74, 70, 66, 61, 54]
        elif age < 36:
            ranges = ["84+", "77-83", "73-76", "68-72", "64-67", "60-63", "54-59"]
            thresholds = [84, 77, 73, 68, 64, 60, 54]
        elif age < 46:
            ranges = ["85+", "78-84", "73-77", "69-72", "65-68", "60-64", "54-59"]
            thresholds = [85, 78, 73, 69, 65, 60, 54]
        elif age < 56:
            ranges = ["85+", "78-84", "74-77", "69-73", "65-68", "60-64", "54-59"]
            thresholds = [85, 78, 74, 69, 65, 60, 54]
        elif age < 66:
            ranges = ["85+", "78-84", "74-77", "69-73", "65-68", "60-64", "54-59"]
            thresholds = [85, 78, 74, 69, 65, 60, 54]
        else:
            ranges = ["85+", "78-84", "73-77", "68-72", "64-67", "59-63", "54-58"]
            thresholds = [85, 78, 73, 68, 64, 59, 54]
    
    # Determine category based on resting HR
    category = "Average"  # default
    if resting_hr:
        rhr = int(resting_hr)
        if rhr >= thresholds[0]:
            category = "Poor"
        elif rhr >= thresholds[1]:
            category = "Below Avg"
        elif rhr >= thresholds[2]:
            category = "Average"
        elif rhr >= thresholds[3]:
            category = "Above Avg"
        elif rhr >= thresholds[4]:
            category = "Good"
        elif rhr >= thresholds[5]:
            category = "Excellent"
        else:
            category = "Athlete"
    
    data = [[age_gender] + ranges]
    
    return {"columns": columns, "data": data, "category": category}


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - Upload form page"""
    return render_template(
        "upload.html", {"request": request, "session": request.session}
    )


@app.post("/upload")
async def upload_files(
    request: Request,
    db: DBSession = Depends(get_db),
    # Patient info
    first_name: str = Form(...),
    last_name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    # Weight with unit
    weight_value: float = Form(...),
    weight_unit: str = Form(default="lbs"),
    # Height with unit
    height_value: float = Form(...),
    height_unit: str = Form(default="in"),
    # Body composition
    fat_percentage: float = Form(...),
    # Settings
    activity_level: str = Form(default="sedentary"),
    weekly_weight_loss_lbs: float = Form(default=1.0),
    focus: str = Form(default="Endurance"),
    next_testing_date: str = Form(...),
    report_type: str = Form(default="full"),
    respiratory_indication: str = Form(default="No"),
    zone_mode: str = Form(default="vt_based"),
    # Files
    spirometry_pdf: UploadFile = File(...),
    pnoe_csv: UploadFile = File(...),
    oxygenation_csv: UploadFile = File(None),
):
    """Handle file upload, calculate metrics, generate static charts, and store in database."""
    
    # Validate file types
    if not spirometry_pdf.filename.endswith(".pdf"):
        return render_template(
            "upload.html",
            {"request": request, "session": request.session, "error": "Spirometry file must be a PDF"},
        )

    if not pnoe_csv.filename.endswith(".csv"):
        return render_template(
            "upload.html",
            {"request": request, "session": request.session, "error": "Pnoe file must be a CSV"},
        )

    if oxygenation_csv and oxygenation_csv.filename and not oxygenation_csv.filename.endswith(".csv"):
        return render_template(
            "upload.html",
            {"request": request, "session": request.session, "error": "Oxygenation file must be a CSV"},
        )

    try:
        # Generate session UUID
        session_id = str(uuid.uuid4())
        
        # Create session directory structure
        session_dir = get_session_dir(session_id)
        uploads_dir = session_dir / "uploads"
        static_charts_dir = session_dir / "static_charts"
        dynamic_charts_dir = session_dir / "dynamic_charts"

        # Convert measurements to standard units (cm, kg)
        weight_kg = convert_weight_to_kg(weight_value, weight_unit)
        height_cm = convert_height_to_cm(height_value, height_unit)

        # Save uploaded files
        spirometry_path = uploads_dir / f"spirometry_{spirometry_pdf.filename}"
        pnoe_path = uploads_dir / f"pnoe_{pnoe_csv.filename}"
        oxygenation_path = None

        with open(spirometry_path, "wb") as f:
            shutil.copyfileobj(spirometry_pdf.file, f)

        with open(pnoe_path, "wb") as f:
            shutil.copyfileobj(pnoe_csv.file, f)

        if oxygenation_csv and oxygenation_csv.filename:
            oxygenation_path = uploads_dir / f"oxygenation_{oxygenation_csv.filename}"
            with open(oxygenation_path, "wb") as f:
                shutil.copyfileobj(oxygenation_csv.file, f)

        # Extract spirometry table from PDF
        spirometry_csv_path = extract_spirometry_table_from_pdf(
            str(spirometry_path), output_dir=str(uploads_dir)
        )

        # Parse next testing date into month and year
        next_testing_month = None
        next_testing_year = None
        if next_testing_date:
            try:
                # Try to parse various date formats
                from datetime import datetime
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %Y", "%b %Y"]:
                    try:
                        parsed_date = datetime.strptime(next_testing_date, fmt)
                        next_testing_month = parsed_date.strftime("%B")
                        next_testing_year = parsed_date.year
                        break
                    except ValueError:
                        continue
                # If parsing failed, try to extract from string directly
                if not next_testing_month:
                    parts = next_testing_date.split()
                    if len(parts) >= 2:
                        next_testing_month = parts[0]
                        try:
                            next_testing_year = int(parts[-1])
                        except ValueError:
                            next_testing_year = None
            except Exception:
                pass

        # ========================================
        # Create Session record in database
        # ========================================
        patient_name = f"{first_name} {last_name}"
        db_session = Session(
            session_id=session_id,
            patient_name=patient_name,
            age=age,
            gender=gender,
            height_cm=height_cm,
            weight_kg=weight_kg,
            body_fat_pct=fat_percentage,
            activity_level=activity_level,
            weekly_weight_loss_lbs=weekly_weight_loss_lbs,
            report_type=report_type,
            respiratory_indication=respiratory_indication,
            zone_mode=zone_mode,
            next_testing_month=next_testing_month,
            next_testing_year=next_testing_year,
            generation_folder_path=str(session_dir),
        )
        db.add(db_session)

        # ========================================
        # Record uploaded files in database
        # ========================================
        for file_type, file_path in [
            ("spirometry_pdf", spirometry_path),
            ("pnoe_csv", pnoe_path),
            ("spirometry_csv", spirometry_csv_path),
        ]:
            db.add(UploadedFile(
                session_id=session_id,
                file_type=file_type,
                file_path=str(file_path),
                original_filename=file_path.name if isinstance(file_path, Path) else Path(file_path).name,
            ))

        if oxygenation_path:
            db.add(UploadedFile(
                session_id=session_id,
                file_type="oxygenation_csv",
                file_path=str(oxygenation_path),
                original_filename=oxygenation_path.name,
            ))

        # ========================================
        # Calculate metrics using MetricsCalculator
        # ========================================
        calculator = MetricsCalculator()
        calculator.load_pnoe_data(str(pnoe_path))
        calculator.load_spirometry_data(spirometry_csv_path)
        
        if oxygenation_path:
            calculator.load_oxygenation_data(str(oxygenation_path))

        all_metrics = calculator.calculate_all_metrics(
            weight_kg=weight_kg,
            height_cm=height_cm,
            age=age,
            gender=gender,
            fat_percentage=fat_percentage,
            activity_level=activity_level,
            weekly_weight_loss_lbs=weekly_weight_loss_lbs,
            zone_mode=zone_mode,
        )

        # ========================================
        # Create Metrics record in database
        # ========================================
        db_metrics = Metrics(
            session_id=session_id,
            # Spirometry
            fvc_best=all_metrics.get("fvc_best"),
            fvc_predicted=all_metrics.get("fvc_predicted"),
            fvc_percent=all_metrics.get("fvc_percent"),
            fev1_best=all_metrics.get("fev1_best"),
            fev1_predicted=all_metrics.get("fev1_predicted"),
            fev1_percent=all_metrics.get("fev1_percent"),
            fev1_fvc_best=all_metrics.get("fev1_fvc_best"),
            fev1_fvc_predicted=all_metrics.get("fev1_fvc_predicted"),
            fev1_fvc_percent=all_metrics.get("fev1_fvc_percent"),
            lung_capacity=all_metrics.get("lung_capacity"),
            # VO2
            vo2_max=all_metrics.get("vo2_max"),
            vo2_max_per_kg=all_metrics.get("vo2_max_per_kg"),
            vo2_max_category=all_metrics.get("vo2_max_category"),
            peak_hr=all_metrics.get("peak_hr"),
            peak_vt=all_metrics.get("peak_vt"),
            peak_vt_hr=all_metrics.get("peak_vt_hr"),
            # Fat metabolism
            fat_max_value=all_metrics.get("fat_max_value"),
            fat_max_hr=all_metrics.get("fat_max_hr"),
            fat_max_vo2=all_metrics.get("fat_max_vo2"),
            fat_max_speed=all_metrics.get("fat_max_speed"),
            # Thresholds
            vt1_hr=all_metrics.get("vt1_hr"),
            vt1_vo2=all_metrics.get("vt1_vo2"),
            vt1_speed=all_metrics.get("vt1_speed"),
            vt2_hr=all_metrics.get("vt2_hr"),
            vt2_vo2=all_metrics.get("vt2_vo2"),
            vt2_speed=all_metrics.get("vt2_speed"),
            crossover_hr=all_metrics.get("crossover_hr"),
            crossover_speed=all_metrics.get("crossover_speed"),
            # Heart rate zones
            zone1_start=all_metrics.get("zone1_start"),
            zone1_end=all_metrics.get("zone1_end"),
            zone2_start=all_metrics.get("zone2_start"),
            zone2_end=all_metrics.get("zone2_end"),
            zone3_start=all_metrics.get("zone3_start"),
            zone3_end=all_metrics.get("zone3_end"),
            zone4_start=all_metrics.get("zone4_start"),
            zone4_end=all_metrics.get("zone4_end"),
            zone5_start=all_metrics.get("zone5_start"),
            zone5_end=all_metrics.get("zone5_end"),
            # VO2 drop points
            vo2_pulse_drops=all_metrics.get("vo2_pulse_drops"),
            vo2_pulse_drop_bpm=all_metrics.get("vo2_pulse_drop_bpm"),
            vo2_breath_drops=all_metrics.get("vo2_breath_drops"),
            vo2_breath_drop_bpm=all_metrics.get("vo2_breath_drop_bpm"),
            # Recovery
            cardiac_recovery_pct=all_metrics.get("cardiac_recovery_pct"),
            metabolic_recovery_pct=all_metrics.get("metabolic_recovery_pct"),
            breath_recovery_pct=all_metrics.get("breath_recovery_pct"),
            resting_hr=all_metrics.get("resting_hr"),
            resting_hr_category=all_metrics.get("resting_hr_category"),
            # RMR and TDEE
            rmr_kcal=all_metrics.get("rmr_kcal"),
            rmr_vo2=all_metrics.get("rmr_vo2"),
            rest_fat_percentage=all_metrics.get("rest_fat_percentage"),
            rest_carb_percentage=all_metrics.get("rest_carb_percentage"),
            tdee=all_metrics.get("tdee"),
            calorie_deficit=all_metrics.get("calorie_deficit"),
            target_calories=all_metrics.get("target_calories"),
            # Macros (with original ratios for recalculation)
            protein_g=all_metrics.get("protein_g"),
            carbs_g=all_metrics.get("carbs_g"),
            fat_g=all_metrics.get("fat_g"),
            fibre_g=all_metrics.get("fibre_g"),
            original_carbs_ratio=all_metrics.get("original_carbs_ratio"),
            original_fat_ratio=all_metrics.get("original_fat_ratio"),
            # Weekday/Weekend macros
            weekday_calories=all_metrics.get("weekday_calories"),
            weekday_protein_g=all_metrics.get("weekday_protein_g"),
            weekday_carbs_g=all_metrics.get("weekday_carbs_g"),
            weekday_fat_g=all_metrics.get("weekday_fat_g"),
            weekday_fibre_g=all_metrics.get("weekday_fibre_g"),
            weekend_calories=all_metrics.get("weekend_calories"),
            weekend_protein_g=all_metrics.get("weekend_protein_g"),
            weekend_carbs_g=all_metrics.get("weekend_carbs_g"),
            weekend_fat_g=all_metrics.get("weekend_fat_g"),
            weekend_fibre_g=all_metrics.get("weekend_fibre_g"),
            # Zone analysis (stored as JSON)
            zone_analysis_json=json.dumps(all_metrics.get("zone_analysis")) if all_metrics.get("zone_analysis") else None,
        )
        db.add(db_metrics)

        # ========================================
        # Generate static charts (one-time)
        # ========================================
        static_gen = StaticChartGenerator(str(static_charts_dir))
        
        # Generate charts from available data
        try:
            # Spirometry chart (if spirometry PDF was uploaded)
            if spirometry_path:
                spirometry_chart = static_gen.generate_spirometry_chart(calculator.spirometry_df)
                db.add(StaticChart(
                    session_id=session_id,
                    chart_type="spirometry",
                    file_path=spirometry_chart,
                ))
        except Exception as e:
            print(f"Error generating spirometry chart: {e}")

        # Pnoe charts
        try:
            pnoe_charts = static_gen.generate_all_pnoe_charts(
                df=calculator.pnoe_df,
                weight_kg=weight_kg,
                client_name=patient_name,
            )
            for chart_type, chart_path in pnoe_charts.items():
                db.add(StaticChart(
                    session_id=session_id,
                    chart_type=chart_type,
                    file_path=chart_path,
                ))
        except Exception as e:
            print(f"Error generating Pnoe charts: {e}")

        # Oxygenation chart (if CSV was uploaded)
        if oxygenation_path and calculator.oxygenation_df is not None:
            try:
                oxy_charts, oxy_metrics = static_gen.generate_all_oxygenation_charts(
                    calculator.oxygenation_df
                )
                for chart_type, chart_path in oxy_charts.items():
                    db.add(StaticChart(
                        session_id=session_id,
                        chart_type=chart_type,
                        file_path=chart_path,
                    ))
                
                # Store oxygenation metrics in the metrics table
                if oxy_metrics:
                    db_metrics.oxygenation_metrics_json = json.dumps(oxy_metrics)
                    
            except Exception as e:
                print(f"Error generating oxygenation charts: {e}")

        # ========================================
        # Generate dynamic charts (regenerate on edit)
        # ========================================
        dynamic_gen = DynamicChartTableGenerator(str(dynamic_charts_dir))
        
        # Generate individual dynamic charts
        try:
            # Body composition - calculate fat and lean mass in lbs
            weight_lbs = weight_kg * 2.20462
            fat_mass_lbs = weight_lbs * (fat_percentage / 100)
            lean_mass_lbs = weight_lbs * (1 - fat_percentage / 100)
            chart_path = dynamic_gen.generate_body_composition_chart(fat_mass_lbs, lean_mass_lbs)
            db.add(DynamicChart(session_id=session_id, chart_type="body_composition", file_path=chart_path))
            
            # Body fat percentage
            chart_path = dynamic_gen.generate_body_fat_percent_chart(fat_percentage, age, gender)
            db.add(DynamicChart(session_id=session_id, chart_type="body_fat_percentage", file_path=chart_path))
            
            # Metabolism
            chart_path = dynamic_gen.generate_metabolism_chart(
                rmr_kcal=all_metrics.get("rmr_kcal"),
                weight_kg=weight_kg,
                height_cm=height_cm,
                age_years=age,
                sex=gender,
            )
            db.add(DynamicChart(session_id=session_id, chart_type="metabolism", file_path=chart_path))
            
            # Fuel source
            chart_path = dynamic_gen.generate_fuel_source_chart(fat_percentage=all_metrics.get("rest_fat_percentage", 0))
            db.add(DynamicChart(session_id=session_id, chart_type="fuel_source", file_path=chart_path))
            
            # VO2 Max table
            vo2_max_value = all_metrics.get("vo2_max_per_kg", 0)
            vo2_max_category = all_metrics.get("vo2_max_category", "Good")
            vo2_table_data = _build_vo2_max_table_data(age, gender, vo2_max_value)
            chart_path = dynamic_gen.generate_vo2_max_table(
                data=vo2_table_data["data"],
                columns=vo2_table_data["columns"],
                vo2_max_value=vo2_max_value,
                category=vo2_max_category,
            )
            db.add(DynamicChart(session_id=session_id, chart_type="vo2_max_table", file_path=chart_path))
            
            # Heart Rate Zones table - use DataFrame-based calculation
            chart_path = dynamic_gen.generate_heart_rate_zones_table(
                df=calculator.pnoe_df,
                zone_1_start=all_metrics.get("zone1_start", 100),
                zone_2_start=all_metrics.get("zone2_start", 115),
                zone_3_start=all_metrics.get("zone3_start", 130),
                zone_4_start=all_metrics.get("zone4_start", 150),
                zone_5_start=all_metrics.get("zone5_start", 165),
                zone_5_end=all_metrics.get("zone5_end", 180),
            )
            db.add(DynamicChart(session_id=session_id, chart_type="heart_rate_zones_table", file_path=chart_path))
            
            # Resting Heart Rate table
            resting_hr = all_metrics.get("resting_hr", 70)
            rhr_table_data = _build_rhr_table_data(age, gender, resting_hr)
            chart_path = dynamic_gen.generate_resting_heart_rate_table(
                data=rhr_table_data["data"],
                columns=rhr_table_data["columns"],
                rhr_value=resting_hr,
                category=rhr_table_data["category"],
            )
            db.add(DynamicChart(session_id=session_id, chart_type="rhr_table", file_path=chart_path))
            
        except Exception as e:
            print(f"Error generating dynamic charts: {e}")
            import traceback
            traceback.print_exc()

        # ========================================
        # Copy static reference images
        # ========================================
        try:
            # Body fat percentage master chart
            master_chart_src = Path("app/static_charts/body_fat_percentage_master_chart.png")
            if master_chart_src.exists():
                master_chart_dst = static_charts_dir / "body_fat_percentage_master_chart.png"
                shutil.copy(master_chart_src, master_chart_dst)
                db.add(StaticChart(
                    session_id=session_id,
                    chart_type="body_fat_percentage_master",
                    file_path=str(master_chart_dst),
                ))
            
            # Fuelling analysis flowchart
            flowchart_src = Path("app/static_charts/estimated_carb_storage.png")
            if flowchart_src.exists():
                flowchart_dst = static_charts_dir / "estimated_carb_storage.png"
                shutil.copy(flowchart_src, flowchart_dst)
                db.add(StaticChart(
                    session_id=session_id,
                    chart_type="fuelling_flowchart",
                    file_path=str(flowchart_dst),
                ))
        except Exception as e:
            print(f"Error copying static charts: {e}")

        # Commit all changes to database
        db.commit()

        # Store session_id in browser session for navigation
        request.session["session_id"] = session_id

        return RedirectResponse(url="/preview", status_code=303)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {error_details}")
        db.rollback()
        return render_template(
            "upload.html",
            {"request": request, "session": request.session, "error": f"Error processing upload: {str(e)}"},
        )
    finally:
        spirometry_pdf.file.close()
        pnoe_csv.file.close()
        if oxygenation_csv and oxygenation_csv.filename:
            oxygenation_csv.file.close()


@app.get("/preview", response_class=HTMLResponse)
async def preview(request: Request, db: DBSession = Depends(get_db)):
    """Preview generated report"""
    session_id = request.session.get("session_id")
    if not session_id:
        return RedirectResponse(url="/", status_code=303)

    # Verify session exists in database
    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        return RedirectResponse(url="/", status_code=303)

    # Get metrics for display
    metrics = db.query(Metrics).filter(Metrics.session_id == session_id).first()

    return render_template(
        "preview.html",
        {
            "request": request,
            "session": request.session,
            "db_session": db_session,
            "metrics": metrics,
        },
    )


@app.get("/edit", response_class=HTMLResponse)
async def edit_form(request: Request, db: DBSession = Depends(get_db)):
    """Display edit metrics form"""
    session_id = request.session.get("session_id")
    if not session_id:
        return RedirectResponse(url="/", status_code=303)

    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        return RedirectResponse(url="/", status_code=303)

    metrics = db.query(Metrics).filter(Metrics.session_id == session_id).first()

    return render_template(
        "edit.html",
        {
            "request": request,
            "session": request.session,
            "db_session": db_session,
            "metrics": metrics,
        },
    )


@app.post("/edit")
async def edit_metrics(request: Request, db: DBSession = Depends(get_db)):
    """
    Handle metric edits.
    
    Handles all editable fields:
    - Patient demographics: age, weight, fat_percentage
    - RMR settings: rmr_time_start, rmr_time_end, activity_level, weekly_weight_loss
    - Protein (carbs and fat are recalculated maintaining the original ratio)
    - Zone settings: zone_mode, manual zones
    - VO2 Max and Resting HR
    - VO2 Pulse/Breath efficiency drops
    - Recovery metrics
    - Fat max and crossover values
    """
    session_id = request.session.get("session_id")
    if not session_id:
        return RedirectResponse(url="/", status_code=303)

    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        return RedirectResponse(url="/", status_code=303)

    metrics = db.query(Metrics).filter(Metrics.session_id == session_id).first()
    if not metrics:
        return RedirectResponse(url="/", status_code=303)

    form_data = await request.form()

    def safe_float(value) -> Optional[float]:
        if not value or str(value).strip() == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_int(value) -> Optional[int]:
        if not value or str(value).strip() == "":
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    try:
        # ========================================
        # Update Patient Demographics
        # ========================================
        new_age = safe_int(form_data.get("age"))
        if new_age is not None:
            db_session.age = new_age
        
        new_weight_lbs = safe_float(form_data.get("weight_lbs"))
        if new_weight_lbs is not None:
            db_session.weight_kg = new_weight_lbs / 2.20462
        
        new_fat_pct = safe_float(form_data.get("fat_percentage"))
        if new_fat_pct is not None:
            db_session.body_fat_pct = new_fat_pct

        # ========================================
        # Update RMR and Metabolic Settings
        # ========================================
        new_rmr_start = safe_float(form_data.get("rmr_time_start"))
        if new_rmr_start is not None:
            db_session.rmr_time_start = new_rmr_start
        
        new_rmr_end = safe_float(form_data.get("rmr_time_end"))
        if new_rmr_end is not None:
            db_session.rmr_time_end = new_rmr_end
        
        new_activity_level = form_data.get("activity_level")
        if new_activity_level:
            db_session.activity_level = new_activity_level
        
        new_weekly_loss = safe_float(form_data.get("weekly_weight_loss_lbs"))
        if new_weekly_loss is not None:
            db_session.weekly_weight_loss_lbs = new_weekly_loss

        # ========================================
        # Recalculate RMR and dependent metrics when RMR settings change
        # ========================================
        pnoe_file = db.query(UploadedFile).filter(
            UploadedFile.session_id == session_id,
            UploadedFile.file_type == "pnoe_csv"
        ).first()
        
        if pnoe_file and Path(pnoe_file.file_path).exists():
            calculator = MetricsCalculator()
            calculator.load_pnoe_data(pnoe_file.file_path)
            
            # Convert minutes to seconds for the calculator
            rmr_start_sec = (db_session.rmr_time_start or 0) * 60
            rmr_end_sec = (db_session.rmr_time_end or 5) * 60
            
            # Recalculate RMR and fuel source
            rmr_fuel = calculator.calculate_rmr_and_fuel_source(rmr_start_sec, rmr_end_sec)
            if rmr_fuel:
                metrics.rmr_kcal = rmr_fuel.get("rmr_kcal", metrics.rmr_kcal)
                metrics.rest_fat_percentage = rmr_fuel.get("rest_fat_percentage", metrics.rest_fat_percentage)
                metrics.rest_carb_percentage = rmr_fuel.get("rest_carb_percentage", metrics.rest_carb_percentage)
                
                # Recalculate TDEE and targets with new RMR
                tdee_targets = calculator.calculate_tdee_and_targets(
                    metrics.rmr_kcal,
                    db_session.activity_level,
                    db_session.weekly_weight_loss_lbs,
                )
                metrics.tdee = tdee_targets.get("tdee", metrics.tdee)
                metrics.calorie_deficit = tdee_targets.get("calorie_deficit", metrics.calorie_deficit)
                metrics.target_calories = tdee_targets.get("target_calories", metrics.target_calories)
                
                # Recalculate nutrition/macros with new target calories
                nutrition = calculator.calculate_nutrition_metrics(
                    db_session.weight_kg,
                    db_session.body_fat_pct,
                    db_session.age,
                    metrics.target_calories,
                    metrics.calorie_deficit,
                )
                metrics.protein_g = nutrition.get("protein_g", metrics.protein_g)
                metrics.carbs_g = nutrition.get("carbs_g", metrics.carbs_g)
                metrics.fat_g = nutrition.get("fat_g", metrics.fat_g)
                metrics.fibre_g = nutrition.get("fibre_g", metrics.fibre_g)
                metrics.weekday_calories = nutrition.get("weekday_calories", metrics.weekday_calories)
                metrics.weekday_protein_g = nutrition.get("weekday_protein_g", metrics.weekday_protein_g)
                metrics.weekday_carbs_g = nutrition.get("weekday_carbs_g", metrics.weekday_carbs_g)
                metrics.weekday_fat_g = nutrition.get("weekday_fat_g", metrics.weekday_fat_g)
                metrics.weekday_fibre_g = nutrition.get("weekday_fibre_g", metrics.weekday_fibre_g)
                metrics.weekend_calories = nutrition.get("weekend_calories", metrics.weekend_calories)
                metrics.weekend_protein_g = nutrition.get("weekend_protein_g", metrics.weekend_protein_g)
                metrics.weekend_carbs_g = nutrition.get("weekend_carbs_g", metrics.weekend_carbs_g)
                metrics.weekend_fat_g = nutrition.get("weekend_fat_g", metrics.weekend_fat_g)
                metrics.weekend_fibre_g = nutrition.get("weekend_fibre_g", metrics.weekend_fibre_g)

        # ========================================
        # Update Protein (recalculate carbs/fat)
        # ========================================
        new_protein = safe_float(form_data.get("protein_g"))
        
        if new_protein is not None and new_protein != metrics.protein_g:
            calculator = MetricsCalculator()
            new_macros = calculator.recalculate_macros_from_protein(
                new_protein_g=new_protein,
                original_carbs_g=metrics.carbs_g,
                original_fat_g=metrics.fat_g,
                total_calories=metrics.target_calories,
            )
            
            metrics.protein_g = new_protein
            metrics.carbs_g = new_macros["carbs_g"]
            metrics.fat_g = new_macros["fat_g"]
            
            # Also update weekday/weekend macros
            if metrics.weekday_carbs_g and metrics.weekday_fat_g:
                weekday_macros = calculator.recalculate_macros_from_protein(
                    new_protein_g=new_protein,
                    original_carbs_g=metrics.weekday_carbs_g,
                    original_fat_g=metrics.weekday_fat_g,
                    total_calories=metrics.weekday_calories,
                )
                metrics.weekday_protein_g = new_protein
                metrics.weekday_carbs_g = weekday_macros["carbs_g"]
                metrics.weekday_fat_g = weekday_macros["fat_g"]
            
            if metrics.weekend_carbs_g and metrics.weekend_fat_g:
                weekend_macros = calculator.recalculate_macros_from_protein(
                    new_protein_g=new_protein,
                    original_carbs_g=metrics.weekend_carbs_g,
                    original_fat_g=metrics.weekend_fat_g,
                    total_calories=metrics.weekend_calories,
                )
                metrics.weekend_protein_g = new_protein
                metrics.weekend_carbs_g = weekend_macros["carbs_g"]
                metrics.weekend_fat_g = weekend_macros["fat_g"]

        # ========================================
        # Update Zone Settings
        # ========================================
        new_zone_mode = form_data.get("zone_mode")
        if new_zone_mode:
            db_session.zone_mode = new_zone_mode
        
        # If manual zone mode, update zone boundaries
        if new_zone_mode == "manual":
            zone1_start = safe_int(form_data.get("zone1_start"))
            zone2_start = safe_int(form_data.get("zone2_start"))
            zone3_start = safe_int(form_data.get("zone3_start"))
            zone4_start = safe_int(form_data.get("zone4_start"))
            zone5_start = safe_int(form_data.get("zone5_start"))
            zone5_end = safe_int(form_data.get("zone5_end"))
            
            if all([zone1_start, zone2_start, zone3_start, zone4_start, zone5_start, zone5_end]):
                metrics.zone1_start = zone1_start
                metrics.zone1_end = zone2_start - 1
                metrics.zone2_start = zone2_start
                metrics.zone2_end = zone3_start - 1
                metrics.zone3_start = zone3_start
                metrics.zone3_end = zone4_start - 1
                metrics.zone4_start = zone4_start
                metrics.zone4_end = zone5_start - 1
                metrics.zone5_start = zone5_start
                metrics.zone5_end = zone5_end

        # Update Fat Max and Crossover values
        new_fat_max = safe_float(form_data.get("fat_max_value"))
        if new_fat_max is not None:
            metrics.fat_max_value = new_fat_max
        
        new_crossover_hr = safe_int(form_data.get("crossover_hr"))
        if new_crossover_hr is not None:
            metrics.crossover_hr = new_crossover_hr

        # ========================================
        # Update VO2 Max and Resting HR
        # ========================================
        new_vo2_max = safe_float(form_data.get("vo2_max_per_kg"))
        if new_vo2_max is not None:
            metrics.vo2_max_per_kg = new_vo2_max
            # Recalculate absolute VO2 max
            if db_session.weight_kg:
                metrics.vo2_max = new_vo2_max * db_session.weight_kg / 1000
        
        new_resting_hr = safe_int(form_data.get("resting_hr"))
        if new_resting_hr is not None:
            metrics.resting_hr = new_resting_hr

        # ========================================
        # Update VO2 Pulse Drop
        # ========================================
        vo2_pulse_drops = form_data.get("vo2_pulse_drops") == "true"
        metrics.vo2_pulse_drops = vo2_pulse_drops
        if vo2_pulse_drops:
            new_vo2_pulse_drop = safe_int(form_data.get("vo2_pulse_drop_bpm"))
            if new_vo2_pulse_drop is not None:
                metrics.vo2_pulse_drop_bpm = new_vo2_pulse_drop
        else:
            metrics.vo2_pulse_drop_bpm = None

        # ========================================
        # Update VO2 Breath Drop
        # ========================================
        vo2_breath_drops = form_data.get("vo2_breath_drops") == "true"
        metrics.vo2_breath_drops = vo2_breath_drops
        if vo2_breath_drops:
            new_vo2_breath_drop = safe_int(form_data.get("vo2_breath_drop_bpm"))
            if new_vo2_breath_drop is not None:
                metrics.vo2_breath_drop_bpm = new_vo2_breath_drop
        else:
            metrics.vo2_breath_drop_bpm = None

        # ========================================
        # Update Recovery Metrics
        # ========================================
        new_cardiac_recovery = safe_float(form_data.get("cardiac_recovery_pct"))
        if new_cardiac_recovery is not None:
            metrics.cardiac_recovery_pct = new_cardiac_recovery
        
        new_metabolic_recovery = safe_float(form_data.get("metabolic_recovery_pct"))
        if new_metabolic_recovery is not None:
            metrics.metabolic_recovery_pct = new_metabolic_recovery
        
        new_breath_recovery = safe_float(form_data.get("breath_recovery_pct"))
        if new_breath_recovery is not None:
            metrics.breath_recovery_pct = new_breath_recovery

        # ========================================
        # Regenerate dynamic charts with new metrics
        # ========================================
        session_dir = get_session_dir(session_id)
        dynamic_charts_dir = session_dir / "dynamic_charts"
        
        # Delete existing dynamic charts from DB and filesystem
        existing_dynamic = db.query(DynamicChart).filter(
            DynamicChart.session_id == session_id
        ).all()
        for chart in existing_dynamic:
            if chart.file_path and Path(chart.file_path).exists():
                Path(chart.file_path).unlink()
            db.delete(chart)
        
        # Regenerate dynamic charts with new metrics
        dynamic_gen = DynamicChartTableGenerator(str(dynamic_charts_dir))
        
        try:
            # Body composition - calculate fat and lean mass in lbs
            weight_lbs = db_session.weight_kg * 2.20462
            fat_mass_lbs = weight_lbs * (db_session.body_fat_pct / 100)
            lean_mass_lbs = weight_lbs * (1 - db_session.body_fat_pct / 100)
            chart_path = dynamic_gen.generate_body_composition_chart(fat_mass_lbs, lean_mass_lbs)
            db.add(DynamicChart(session_id=session_id, chart_type="body_composition", file_path=chart_path))
            
            # Body fat percentage
            chart_path = dynamic_gen.generate_body_fat_percent_chart(db_session.body_fat_pct, db_session.age, db_session.gender)
            db.add(DynamicChart(session_id=session_id, chart_type="body_fat_percentage", file_path=chart_path))
            
            # Metabolism
            chart_path = dynamic_gen.generate_metabolism_chart(
                rmr_kcal=metrics.rmr_kcal,
                weight_kg=db_session.weight_kg,
                height_cm=db_session.height_cm,
                age_years=db_session.age,
                sex=db_session.gender,
            )
            db.add(DynamicChart(session_id=session_id, chart_type="metabolism", file_path=chart_path))
            
            # Fuel source
            chart_path = dynamic_gen.generate_fuel_source_chart(fat_percentage=metrics.rest_fat_percentage or 0)
            db.add(DynamicChart(session_id=session_id, chart_type="fuel_source", file_path=chart_path))
            
            # VO2 Max table
            vo2_max_value = metrics.vo2_max_per_kg or 0
            vo2_max_category = metrics.vo2_max_category or "Good"
            vo2_table_data = _build_vo2_max_table_data(db_session.age, db_session.gender, vo2_max_value)
            chart_path = dynamic_gen.generate_vo2_max_table(
                data=vo2_table_data["data"],
                columns=vo2_table_data["columns"],
                vo2_max_value=vo2_max_value,
                category=vo2_max_category,
            )
            db.add(DynamicChart(session_id=session_id, chart_type="vo2_max_table", file_path=chart_path))
            
            # Heart Rate Zones table - reload pnoe data and regenerate
            pnoe_file = db.query(UploadedFile).filter(
                UploadedFile.session_id == session_id,
                UploadedFile.file_type == "pnoe_csv"
            ).first()
            if pnoe_file and Path(pnoe_file.file_path).exists():
                calculator = MetricsCalculator()
                calculator.load_pnoe_data(pnoe_file.file_path)
                chart_path = dynamic_gen.generate_heart_rate_zones_table(
                    df=calculator.pnoe_df,
                    zone_1_start=metrics.zone1_start or 100,
                    zone_2_start=metrics.zone2_start or 115,
                    zone_3_start=metrics.zone3_start or 130,
                    zone_4_start=metrics.zone4_start or 150,
                    zone_5_start=metrics.zone5_start or 165,
                    zone_5_end=metrics.zone5_end or 180,
                )
                db.add(DynamicChart(session_id=session_id, chart_type="heart_rate_zones_table", file_path=chart_path))
            
            # Resting Heart Rate table
            resting_hr = metrics.resting_hr or 70
            rhr_table_data = _build_rhr_table_data(db_session.age, db_session.gender, resting_hr)
            chart_path = dynamic_gen.generate_resting_heart_rate_table(
                data=rhr_table_data["data"],
                columns=rhr_table_data["columns"],
                rhr_value=resting_hr,
                category=rhr_table_data["category"],
            )
            db.add(DynamicChart(session_id=session_id, chart_type="rhr_table", file_path=chart_path))
        except Exception as e:
            print(f"Error regenerating dynamic charts: {e}")
            import traceback
            traceback.print_exc()

        db.commit()
        return RedirectResponse(url="/preview", status_code=303)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {error_details}")
        db.rollback()
        return render_template(
            "edit.html",
            {
                "request": request,
                "session": request.session,
                "db_session": db_session,
                "metrics": metrics,
                "error": f"Error updating metrics: {str(e)}",
            },
        )


@app.post("/generate-report")
async def generate_report(request: Request, db: DBSession = Depends(get_db)):
    """
    Generate PDF report and redirect to view it.
    
    Uses the UnifiedReportGenerator for a streamlined flow:
    - Load data from database
    - Generate contexts with consistent chart naming
    - Render HTML and convert to PDF
    """
    session_id = request.session.get("session_id")
    if not session_id:
        return RedirectResponse(url="/", status_code=303)

    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        return RedirectResponse(url="/", status_code=303)

    try:
        session_dir = get_session_dir(session_id)
        reports_dir = session_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Use the unified report generator
        report_generator = UnifiedReportGenerator(
            db=db,
            session_id=session_id,
            template_dir="app/report_gen",
        )

        # Generate PDF directly
        output_path = reports_dir / "report.pdf"
        await report_generator.generate_pdf(
            output_path=str(output_path),
            report_type=db_session.report_type or "full",
        )

        # Update session with generation folder path (for later retrieval)
        db_session.generation_folder_path = str(session_dir)
        db.commit()

        # Redirect to view the PDF
        return RedirectResponse(url=f"/view-report?session_id={session_id}", status_code=303)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR generating report: {error_details}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/view-report")
async def view_report(request: Request, session_id: Optional[str] = None, db: DBSession = Depends(get_db)):
    """
    View the generated PDF report in the browser.
    
    Returns the PDF file with inline content-disposition so browsers display it
    rather than downloading it.
    """
    # Use session_id from query param or from session
    if not session_id:
        session_id = request.session.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=404, detail="No session found")

    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get report path
    session_dir = get_session_dir(session_id)
    report_path = session_dir / "reports" / "report.pdf"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Please generate the report first.")

    # Return PDF with inline disposition for browser viewing
    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{db_session.patient_name}_report.pdf\""
        }
    )


@app.get("/download-report")
async def download_report(request: Request, db: DBSession = Depends(get_db)):
    """Download the generated PDF report as a file."""
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=404, detail="No session found")

    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get report path
    session_dir = get_session_dir(session_id)
    report_path = session_dir / "reports" / "report.pdf"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found. Please generate the report first.")

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"{db_session.patient_name}_report.pdf",
    )


@app.get("/chart/{session_id}/{chart_type}/{filename}")
async def serve_chart(session_id: str, chart_type: str, filename: str, db: DBSession = Depends(get_db)):
    """
    Serve chart images from session directories.
    
    Args:
        session_id: The session UUID
        chart_type: Either 'static' or 'dynamic'
        filename: The chart filename (e.g., 'spirometry_chart.png')
    
    Returns:
        The chart image file
    """
    # Validate session exists
    db_session = db.query(Session).filter(Session.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get chart path
    session_dir = get_session_dir(session_id)
    
    if chart_type == "static":
        chart_path = session_dir / "static_charts" / filename
    elif chart_type == "dynamic":
        chart_path = session_dir / "dynamic_charts" / filename
    else:
        raise HTTPException(status_code=400, detail="Invalid chart type. Use 'static' or 'dynamic'")
    
    if not chart_path.exists():
        raise HTTPException(status_code=404, detail=f"Chart not found: {filename}")
    
    # Determine media type
    media_type = "image/png"
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif filename.endswith(".svg"):
        media_type = "image/svg+xml"
    
    return FileResponse(
        path=chart_path,
        media_type=media_type,
        headers={"Cache-Control": "max-age=3600"}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "report-generation-api", "version": "3.0.0"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
