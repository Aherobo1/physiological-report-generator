"""
Unified Report Generator Service

This service handles the complete report generation flow in a single, cohesive module.
It eliminates intermediate transformations and ensures consistent naming between
chart generation and template rendering.

Flow:
1. Load all data files (Pnoe CSV, Spirometry PDF/CSV, Oxygenation CSV)
2. Calculate all metrics
3. Generate all charts with consistent naming
4. Build page contexts with matching variable names
5. Render HTML and generate PDF
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session as DBSession

from app.db.models import Session, Metrics, StaticChart, DynamicChart
from app.services.metrics_calculator import MetricsCalculator
from app.services.static_chart_generator import StaticChartGenerator
from app.services.dynamic_chart_table_generator import DynamicChartTableGenerator


class UnifiedReportGenerator:
    """
    Unified service for generating medical performance reports.
    
    This class handles the entire report generation flow:
    - Data loading and processing
    - Metric calculations
    - Chart generation
    - Context building
    - HTML rendering
    - PDF generation
    """

    def __init__(
        self,
        db: DBSession,
        session_id: str,
        template_dir: str = "app/report_gen",
    ):
        """
        Initialize the unified report generator.

        Args:
            db: SQLAlchemy database session
            session_id: The session UUID
            template_dir: Directory containing Jinja2 templates
        """
        self.db = db
        self.session_id = session_id
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
        # Cached data
        self._session: Optional[Session] = None
        self._metrics: Optional[Metrics] = None
        self._charts: Dict[str, str] = {}  # chart_key -> base64 string

    # ==================== Data Loading ====================

    def load_session_data(self) -> None:
        """Load session and metrics from database."""
        self._session = self.db.query(Session).filter(
            Session.session_id == self.session_id
        ).first()
        if not self._session:
            raise ValueError(f"Session not found: {self.session_id}")

        self._metrics = self.db.query(Metrics).filter(
            Metrics.session_id == self.session_id
        ).first()
        if not self._metrics:
            raise ValueError(f"Metrics not found for session: {self.session_id}")

    def load_charts_from_db(self) -> None:
        """Load all charts from database and convert to base64."""
        # Load static charts
        static_charts = self.db.query(StaticChart).filter(
            StaticChart.session_id == self.session_id
        ).all()
        
        for chart in static_charts:
            if chart.file_path and Path(chart.file_path).exists():
                self._charts[chart.chart_type] = self._file_to_base64(chart.file_path)

        # Load dynamic charts
        dynamic_charts = self.db.query(DynamicChart).filter(
            DynamicChart.session_id == self.session_id
        ).all()
        
        for chart in dynamic_charts:
            if chart.file_path and Path(chart.file_path).exists():
                self._charts[chart.chart_type] = self._file_to_base64(chart.file_path)

    def _file_to_base64(self, file_path: str) -> str:
        """Convert a file to base64 string."""
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @property
    def session_data(self) -> Session:
        """Get session data, loading if necessary."""
        if not self._session:
            self.load_session_data()
        return self._session

    @property
    def metrics(self) -> Metrics:
        """Get metrics data, loading if necessary."""
        if not self._metrics:
            self.load_session_data()
        return self._metrics

    def get_chart(self, chart_key: str) -> str:
        """Get chart base64 string by key, returning empty string if not found."""
        return self._charts.get(chart_key, "")

    # ==================== Helper Methods ====================

    def _format_pace(self, speed_mph: float) -> str:
        """Convert speed (mph) to pace (min:sec/mile)."""
        if speed_mph <= 0:
            return "-"
        pace_min = 60 / speed_mph
        minutes = int(pace_min)
        seconds = int((pace_min % 1) * 60)
        return f"{minutes}:{seconds:02d}"

    def _format_height_imperial(self, height_cm: float) -> str:
        """Convert height from cm to ft'in\" format."""
        if not height_cm or height_cm <= 0:
            return "-"
        total_inches = height_cm / 2.54
        feet = int(total_inches // 12)
        inches = int(total_inches % 12)
        return f"{feet}'{inches}\""

    def _determine_hr_zone(self, hr: int) -> str:
        """Determine which HR zone a heart rate falls into."""
        if hr is None:
            return "-"
        
        m = self.metrics
        try:
            if m.zone1_start and m.zone1_end and m.zone1_start <= hr <= m.zone1_end:
                return "Zone 1"
            elif m.zone2_start and m.zone2_end and m.zone2_start <= hr <= m.zone2_end:
                return "Zone 2"
            elif m.zone3_start and m.zone3_end and m.zone3_start <= hr <= m.zone3_end:
                return "Zone 3"
            elif m.zone4_start and m.zone4_end and m.zone4_start <= hr <= m.zone4_end:
                return "Zone 4"
            elif m.zone5_start and m.zone5_end and m.zone5_start <= hr <= m.zone5_end:
                return "Zone 5"
        except TypeError:
            return "-"
        return "-"

    def _safe_format(self, value, fmt: str = "{}", default: str = "-") -> str:
        """Safely format a value, returning default if None."""
        if value is None:
            return default
        try:
            return fmt.format(value)
        except (ValueError, TypeError):
            return default

    def _safe_int(self, value, default: str = "-") -> str:
        """Safely format a value as integer."""
        if value is None:
            return default
        try:
            return str(int(value))
        except (ValueError, TypeError):
            return default

    def _safe_float(self, value, decimals: int = 1, default: str = "-") -> str:
        """Safely format a value as float with specified decimals."""
        if value is None:
            return default
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return default

    # ==================== Page Context Generators ====================
    # Each method generates the exact context dict expected by the template

    def generate_page_1_context(self) -> Dict[str, Any]:
        """Page 1 - Cover page."""
        name_parts = (self.session_data.patient_name or "").split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        return {
            "name": first_name,
            "surname": last_name,
            "date": self.session_data.created_at.strftime("%B %d, %Y") if self.session_data.created_at else datetime.now().strftime("%B %d, %Y"),
        }

    def generate_page_2_context(self) -> Dict[str, Any]:
        """Page 2 - Table of contents (no dynamic data needed)."""
        return {}

    def generate_page_3_context(self) -> Dict[str, Any]:
        """Page 3 - Overview (no dynamic data needed for current template)."""
        return {}

    def generate_page_4_context(self) -> Dict[str, Any]:
        """Page 4 - Body composition."""
        weight_kg = self.session_data.weight_kg or 0
        weight_lbs = weight_kg * 2.20462
        body_fat_pct = self.session_data.body_fat_pct or 0
        
        fat_mass_lbs = weight_lbs * body_fat_pct / 100 if body_fat_pct else 0
        lean_mass_lbs = weight_lbs * (1 - body_fat_pct / 100) if body_fat_pct else weight_lbs
        
        return {
            # Template expects these exact names
            "body_composition_chart": self.get_chart("body_composition"),
            "body_fat_chart": self.get_chart("body_fat_percentage"),
            "fat_percentage": f"{body_fat_pct:.1f}" if body_fat_pct else "0",
        }

    def generate_page_5_context(self) -> Dict[str, Any]:
        """Page 5 - Resting Metabolic Rate Assessment."""
        m = self.metrics
        
        # Calculate NEAT (TDEE - RMR)
        neat = 0
        if m.tdee and m.rmr_kcal:
            neat = int(m.tdee - m.rmr_kcal)
        
        return {
            "metabolism_chart": self.get_chart("metabolism"),
            "fuel_source_chart": self.get_chart("fuel_source"),
            "resting_calories": self._safe_int(m.rmr_kcal),
            "neat_calories": self._safe_int(neat) if neat > 0 else "-",
            "weight_loss_calories": self._safe_int(m.calorie_deficit),
            "weight_loss_rate": f"{self.session_data.weekly_weight_loss_lbs:.1f}" if self.session_data.weekly_weight_loss_lbs else "1.0",
            "total_calories": self._safe_int(m.target_calories),
        }

    def generate_page_6_context(self) -> Dict[str, Any]:
        """Page 6 - Weekly Meal Plan Breakdown."""
        m = self.metrics
        
        return {
            # Deficit (daily uniform)
            "deficit_calories": self._safe_int(m.target_calories),
            "deficit_protein": f"{self._safe_int(m.protein_g)}g Protein",
            "deficit_carbs": f"{self._safe_int(m.carbs_g)}g Carbs",
            "deficit_fat": f"{self._safe_int(m.fat_g)}g Fat",
            "deficit_fiber": f"{self._safe_int(m.fibre_g)}g Fibre",
            # Refeed weekday
            "refeed_weekday_calories": self._safe_int(m.weekday_calories),
            "refeed_weekday_protein": f"{self._safe_int(m.weekday_protein_g)}g Protein",
            "refeed_weekday_carbs": f"{self._safe_int(m.weekday_carbs_g)}g Carbs",
            "refeed_weekday_fat": f"{self._safe_int(m.weekday_fat_g)}g Fat",
            "refeed_weekday_fiber": f"{self._safe_int(m.weekday_fibre_g)}g Fibre",
            # Refeed weekend
            "refeed_weekend_calories": self._safe_int(m.weekend_calories),
            "refeed_weekend_protein": f"{self._safe_int(m.weekend_protein_g)}g Protein",
            "refeed_weekend_carbs": f"{self._safe_int(m.weekend_carbs_g)}g Carbs",
            "refeed_weekend_fat": f"{self._safe_int(m.weekend_fat_g)}g Fat",
            "refeed_weekend_fiber": f"{self._safe_int(m.weekend_fibre_g)}g Fibre",
        }

    def generate_page_7_context(self) -> Dict[str, Any]:
        """Page 7 - Lung Analysis (Spirometry & Respiratory)."""
        m = self.metrics
        
        # Determine peak VT zone
        peak_vt_zone = "-"
        if m.peak_vt_hr:
            peak_vt_zone = self._determine_hr_zone(m.peak_vt_hr)
        
        # Calculate FEV1 percentage
        fev1_pct = "-"
        if m.peak_vt and m.fev1_best and m.fev1_best > 0:
            fev1_pct = f"{(m.peak_vt / m.fev1_best) * 100:.0f}"
        
        return {
            "lung_analysis_chart": self.get_chart("spirometry"),
            "respiratory_analysis_chart": self.get_chart("respiratory"),
            "indication": self.session_data.respiratory_indication or "No",
            "peak_vt": self._safe_float(m.peak_vt, 2),
            "peak_vt_bpm": self._safe_int(m.peak_vt_hr),
            "peak_vt_zone": peak_vt_zone,
            "fev1_percentage": fev1_pct,
        }

    def generate_page_8_context(self) -> Dict[str, Any]:
        """Page 8 - Cardio Metrics (VO2 Max & Heart Rate Zones)."""
        return {
            "vo2_max_table": self.get_chart("vo2_max_table"),
            "hr_zones_table": self.get_chart("heart_rate_zones_table"),
        }

    def generate_page_9_context(self) -> Dict[str, Any]:
        """Page 9 - Relative VO2."""
        return {
            "relative_vo2_chart": self.get_chart("relative_vo2"),
            "client_name": self.session_data.patient_name or "",
            "assessment_date": self.session_data.created_at.strftime("%B %d, %Y") if self.session_data.created_at else "",
        }

    def generate_page_10_context(self) -> Dict[str, Any]:
        """Page 10 - Fuel Utilization."""
        return {
            "fuel_utilization_chart": self.get_chart("fuel_utilization"),
            "client_name": self.session_data.patient_name or "",
            "assessment_date": self.session_data.created_at.strftime("%B %d, %Y") if self.session_data.created_at else "",
        }

    def generate_page_11_context(self) -> Dict[str, Any]:
        """Page 11 - Fuelling Analysis."""
        return {
            "fuelling_analysis_flowchart": self.get_chart("fuelling_flowchart"),
        }

    def generate_page_12_context(self) -> Dict[str, Any]:
        """Page 12 - VO2 Pulse & VO2 Breath."""
        m = self.metrics
        
        # VO2 Pulse drop zone
        vo2_pulse_drop_zone = None
        if m.vo2_pulse_drops and m.vo2_pulse_drop_bpm:
            vo2_pulse_drop_zone = self._determine_hr_zone(m.vo2_pulse_drop_bpm)
        
        # VO2 Breath drop zone
        vo2_breath_drop_zone = None
        if m.vo2_breath_drops and m.vo2_breath_drop_bpm:
            vo2_breath_drop_zone = self._determine_hr_zone(m.vo2_breath_drop_bpm)
        
        return {
            "vo2_pulse_chart": self.get_chart("vo2_pulse"),
            "vo2_breath_chart": self.get_chart("vo2_breath"),
            "vo2_pulse_drop_bpm": f"{m.vo2_pulse_drop_bpm} bpm" if m.vo2_pulse_drops and m.vo2_pulse_drop_bpm else None,
            "vo2_pulse_drop_zone": vo2_pulse_drop_zone,
            "vo2_breath_drop_bpm": f"{m.vo2_breath_drop_bpm} bpm" if m.vo2_breath_drops and m.vo2_breath_drop_bpm else None,
            "vo2_breath_drop_zone": vo2_breath_drop_zone,
        }

    def generate_page_13_context(self) -> Dict[str, Any]:
        """Page 13 - Fat Metabolism & Recovery."""
        m = self.metrics
        
        # Fat max as percentage of max HR
        max_hr = m.peak_hr or 180
        fat_max_hr_pct = "-"
        if m.fat_max_hr and max_hr:
            fat_max_hr_pct = f"{int((m.fat_max_hr / max_hr) * 100)}% of Max Heart Rate"
        
        crossover_hr_pct = "-"
        if m.crossover_hr and max_hr:
            crossover_hr_pct = f"{int((m.crossover_hr / max_hr) * 100)}% of Max Heart Rate"
        
        return {
            "fat_metabolism_chart": self.get_chart("fat_metabolism"),
            "recovery_chart": self.get_chart("recovery"),
            "rhr_table": self.get_chart("rhr_table"),
            # Fat Max
            "fat_max_optimal": "*Optimal 10-12Kcals/minute",
            "fat_max_value": f"{self._safe_float(m.fat_max_value, 1)}Kcals/min" if m.fat_max_value else "-",
            "fat_max_heart_rate": fat_max_hr_pct,
            "fat_max_bpm": f"{self._safe_int(m.fat_max_hr)} bpm",
            # Crossover
            "crossover_bpm": f"{self._safe_int(m.crossover_hr)}bpm",
            "crossover_heart_rate": crossover_hr_pct,
            # Recovery percentages
            "cardiac_recovery_time": "(1 minute)",
            "cardiac_recovery_percentage": f"{self._safe_int(m.cardiac_recovery_pct)}%",
            "metabolic_recovery_time": "(2 minutes)",
            "metabolic_recovery_percentage": f"{self._safe_int(m.metabolic_recovery_pct)}%",
            "breath_recovery_time": "(1.5 minutes)",
            "breath_recovery_percentage": f"{self._safe_int(m.breath_recovery_pct)}%",
        }

    def generate_page_14_context(self) -> Dict[str, Any]:
        """Page 14 - Local Muscle Activity (Muscle Oxygenation)."""
        m = self.metrics
        
        # Parse oxygenation metrics from JSON if available
        oxy = {}
        if m.oxygenation_metrics_json:
            import json
            try:
                oxy = json.loads(m.oxygenation_metrics_json)
            except json.JSONDecodeError:
                pass
        
        return {
            "muscle_oxygenation_chart": self.get_chart("muscle_oxygenation") or self.get_chart("tsi"),
            # Left leg
            "left_baseline_smo2": oxy.get("left_baseline_smo2", "-"),
            "left_minimum_smo2": oxy.get("left_minimum_smo2", "-"),
            "left_minimum_lap": oxy.get("left_minimum_lap", "-"),
            "left_oxygen_drop": oxy.get("left_oxygen_drop", "-"),
            "left_drop_percentage": oxy.get("left_drop_percentage", "-"),
            "left_recovery_percentage": oxy.get("left_recovery_percentage", "-"),
            # Right leg
            "right_baseline_smo2": oxy.get("right_baseline_smo2", "-"),
            "right_minimum_smo2": oxy.get("right_minimum_smo2", "-"),
            "right_minimum_lap": oxy.get("right_minimum_lap", "-"),
            "right_oxygen_drop": oxy.get("right_oxygen_drop", "-"),
            "right_drop_percentage": oxy.get("right_drop_percentage", "-"),
            "right_recovery_percentage": oxy.get("right_recovery_percentage", "-"),
            # Additional metrics
            "hr_warmup": oxy.get("hr_warmup", "-"),
            "hr_max": oxy.get("hr_max", "-"),
            "test_duration": oxy.get("test_duration", "-"),
            "recovery_assessment": oxy.get("recovery_assessment", "-"),
        }

    def generate_page_15_context(self) -> Dict[str, Any]:
        """Page 15 - Training Recommendations."""
        m = self.metrics
        
        # Format zone ranges
        def fmt_range(start, end):
            if start is None or end is None:
                return "____"
            return f"{start}-{end}"
        
        return {
            # Zone 2
            "zone2_frequency": "3-4x/week",
            "zone2_duration": "40+ minutes",
            "zone2_hr_range": fmt_range(m.zone2_start, m.zone2_end),
            "zone2_speed": f"{self._safe_float(m.vt1_speed, 1)}" if m.vt1_speed else "___",
            "zone2_incline": "2% Incline",
            # Zone 3
            "zone3_frequency": "1-2x/week",
            "zone3_duration": "10-20 minutes",
            "zone3_hr_range": fmt_range(m.zone3_start, m.zone3_end),
            "zone3_speed": f"{self._safe_float(m.vt2_speed, 1)}" if m.vt2_speed else "___",
            "zone3_incline": "2% Incline",
            "zone3_target_hr": self._safe_int(m.zone3_end),
            "zone3_recovery_speed": f"{self._safe_float(m.fat_max_speed, 1)}" if m.fat_max_speed else "____",
            "zone3_recovery_incline": "2% Incline",
            # Zone 1
            "zone1_hr_range": fmt_range(m.zone1_start, m.zone1_end),
            "zone1_duration": "4-8 minutes",
            "zone3_repeats": "2-3 times",
        }

    def generate_page_16_context(self) -> Dict[str, Any]:
        """Page 16 - Training Recommendations continued (if needed)."""
        return self.generate_page_15_context()

    def generate_page_17_context(self) -> Dict[str, Any]:
        """Page 17 - Next Steps (static content)."""
        return {}

    def generate_page_18_context(self) -> Dict[str, Any]:
        """Page 18 - Glossary (static content)."""
        return {}

    def generate_page_19_context(self) -> Dict[str, Any]:
        """Page 19 - Glossary continued (static content)."""
        return {}

    def generate_page_20_context(self) -> Dict[str, Any]:
        """Page 20 - Glossary with body fat master chart."""
        return {
            "body_fat_percentage_chart": self.get_chart("body_fat_percentage_master"),
        }

    def generate_page_21_context(self) -> Dict[str, Any]:
        """Page 21 - Glossary with RHR tables (static content)."""
        return {}

    # ==================== Master Context Generator ====================

    def generate_all_contexts(self, report_type: str = "full") -> Dict[str, Dict[str, Any]]:
        """
        Generate all page contexts for the report.

        Args:
            report_type: 'full' or 'minimal'

        Returns:
            Dictionary mapping page keys to their contexts
        """
        # Ensure data is loaded
        self.load_session_data()
        self.load_charts_from_db()
        
        contexts = {}
        
        # Page generator mapping
        page_generators = {
            1: self.generate_page_1_context,
            2: self.generate_page_2_context,
            3: self.generate_page_3_context,
            4: self.generate_page_4_context,
            5: self.generate_page_5_context,
            6: self.generate_page_6_context,
            7: self.generate_page_7_context,
            8: self.generate_page_8_context,
            9: self.generate_page_9_context,
            10: self.generate_page_10_context,
            11: self.generate_page_11_context,
            12: self.generate_page_12_context,
            13: self.generate_page_13_context,
            14: self.generate_page_14_context,
            15: self.generate_page_15_context,
            16: self.generate_page_16_context,
            17: self.generate_page_17_context,
            18: self.generate_page_18_context,
            19: self.generate_page_19_context,
            20: self.generate_page_20_context,
            21: self.generate_page_21_context,
        }
        
        # Determine which pages to generate
        if report_type == "minimal":
            pages_to_generate = [1, 2, 4, 5, 6, 17, 18, 20, 21]
        else:
            pages_to_generate = list(range(1, 22))
        
        # Generate contexts
        for page_num in pages_to_generate:
            if page_num in page_generators:
                try:
                    contexts[f"page_{page_num}"] = page_generators[page_num]()
                except Exception as e:
                    print(f"Error generating context for page {page_num}: {e}")
                    contexts[f"page_{page_num}"] = {}
        
        # For minimal reports, create combined page 20_21
        if report_type == "minimal":
            contexts["page_20_21_minimal"] = {
                "body_fat_percentage_chart": self.get_chart("body_fat_percentage_master"),
            }
        
        return contexts

    # ==================== HTML Generation ====================

    def generate_html(self, report_type: str = "full") -> str:
        """
        Generate complete HTML document for the report.

        Args:
            report_type: 'full' or 'minimal'

        Returns:
            Complete HTML document as string
        """
        contexts = self.generate_all_contexts(report_type)
        
        html_pages = []
        
        # Header context
        header_context = {
            "patient_name": self.session_data.patient_name or "",
            "age": self.session_data.age or "",
            "height": f"{self.session_data.height_cm:.0f} cm" if self.session_data.height_cm else "",
            "weight": f"{self.session_data.weight_kg:.1f} kg" if self.session_data.weight_kg else "",
            "focus": "Endurance",
        }
        
        # Define page mappings
        if report_type == "minimal":
            page_mapping = [
                (1, "page_1.html", 1),
                (2, "page_2_minimal.html", 2),
                (4, "page_4.html", 3),
                (5, "page_5_minimal.html", 4),
                (6, "page_6.html", 5),
                (17, "page_17.html", 6),
                (18, "page_18_minimal.html", 7),
                (20, "page_20_21_minimal.html", 8),
            ]
        else:
            page_mapping = [(i, f"page_{i}.html", i) for i in range(1, 22)]
        
        num_pages = len(page_mapping)
        
        # Footer contexts
        footer_context = [
            {
                "contact_email": "info@ishplabs.com",
                "website": "www.ishplabs.com",
                "social": "@ishplabs",
                "page_number": i + 1,
            }
            for i in range(num_pages)
        ]
        
        # Render header and footers
        header_html = self.env.get_template("header.html").render(header_context)
        footer_html_list = [
            self.env.get_template("footer.html").render(ctx)
            for ctx in footer_context
        ]
        
        # Render pages
        for idx, (original_page_num, template_name, report_page_num) in enumerate(page_mapping):
            # Get context
            if template_name == "page_20_21_minimal.html":
                page_key = "page_20_21_minimal"
            else:
                page_key = f"page_{original_page_num}"
            
            context = contexts.get(page_key, {})
            
            try:
                template = self.env.get_template(template_name).render(context)
            except Exception as e:
                print(f"Error rendering template {template_name}: {e}")
                template = f"<div class='page bg-white p-8'><h1>Error rendering page {original_page_num}</h1><p>{str(e)}</p></div>"
            
            # Pages 1 and 2 don't have headers/footers in full report
            # In minimal report, only page 1 doesn't have header/footer
            if report_page_num > 2:
                full_html = f"""
                <div class="page flex flex-col justify-between">
                    <div>
                        {header_html}
                    </div>
                    <main class="flex-grow p-4">
                        {template}
                    </main>
                    <div class="border-t text-center text-sm text-gray-600">
                        {footer_html_list[idx]}
                    </div>
                </div>
                """
            elif report_page_num == 2:
                full_html = f"""
                <div class="page flex flex-col justify-between">
                    <main class="flex-grow p-4">
                        {template}
                    </main>
                    <div class="border-t text-center text-sm text-gray-600">
                        {footer_html_list[idx]}
                    </div>
                </div>
                """
            else:
                full_html = f"""
                <div class="page">
                    {template}
                </div>
                """
            
            html_pages.append(full_html)
        
        # Combine pages with page breaks
        final_html = "<div class='page-break'></div>".join(html_pages)
        
        # Wrap in complete HTML document
        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <link href="https://cdn.jsdelivr.net/npm/tailwindcss/dist/tailwind.min.css" rel="stylesheet">
          <style>
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
            }}
            .page-break {{ page-break-after: always; }}
            .page {{
              height: 100vh;
              min-height: 100vh;
              display: flex;
              flex-direction: column;
            }}
            .page main {{
              flex: 1;
              overflow: hidden;
            }}
            * {{
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }}
            img {{
              max-height: 300px;
            }}
            .chart-large {{
              max-height: 500px !important;
            }}
            .table-image {{
              max-height: none !important;
              width: auto !important;
              max-width: 100% !important;
              height: auto !important;
              object-fit: contain;
            }}
          </style>
        </head>
        <body class="m-0 p-0">
          {final_html}
        </body>
        </html>
        """
        
        return html_doc

    # ==================== PDF Generation ====================

    async def html_to_pdf(self, html_content: str, pdf_path: str) -> None:
        """
        Convert HTML content to PDF file.

        Args:
            html_content: HTML content as string
            pdf_path: Path where PDF should be saved
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")
            await page.pdf(
                path=pdf_path,
                format="Letter",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()

    async def generate_pdf(
        self,
        output_path: str,
        report_type: str = "full",
    ) -> str:
        """
        Generate complete PDF report.

        Args:
            output_path: Path where PDF should be saved
            report_type: 'full' or 'minimal'

        Returns:
            Path to generated PDF
        """
        # Generate HTML
        html_content = self.generate_html(report_type)
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate PDF
        await self.html_to_pdf(html_content, output_path)
        
        return output_path


# ==================== Chart Type Mapping ====================
# This documents the expected chart keys used by templates

CHART_KEY_MAPPING = {
    # Page 4 - Body Composition
    "body_composition": "body_composition_chart.png",  # from DynamicChartTableGenerator
    "body_fat_percentage": "body_fat_percent_chart.png",  # from DynamicChartTableGenerator
    
    # Page 5 - Metabolism
    "metabolism": "metabolism_chart.png",  # from DynamicChartTableGenerator
    "fuel_source": "fuel_source_chart.png",  # from DynamicChartTableGenerator
    
    # Page 7 - Lung Analysis
    "spirometry": "spirometry_chart.png",  # from StaticChartGenerator
    "respiratory": "respiratory_chart.png",  # from StaticChartGenerator
    
    # Page 8 - Cardio Metrics
    "vo2_max_table": "vo2_max_table.png",  # from DynamicChartTableGenerator
    "heart_rate_zones_table": "heart_rate_zones_table.png",  # from DynamicChartTableGenerator
    
    # Page 9 - Relative VO2
    "relative_vo2": "relative_vo2_chart.png",  # from StaticChartGenerator
    
    # Page 10 - Fuel Utilization
    "fuel_utilization": "fuel_utilization_chart.png",  # from StaticChartGenerator
    
    # Page 11 - Fuelling Analysis
    "fuelling_flowchart": "estimated_carb_storage.png",  # static file
    
    # Page 12 - VO2 Pulse/Breath
    "vo2_pulse": "vo2_pulse_chart.png",  # from StaticChartGenerator
    "vo2_breath": "vo2_breath_chart.png",  # from StaticChartGenerator
    
    # Page 13 - Fat Metabolism & Recovery
    "fat_metabolism": "fat_metabolism_chart.png",  # from StaticChartGenerator
    "recovery": "recovery_chart.png",  # from StaticChartGenerator
    
    # Page 14 - Muscle Oxygenation
    "muscle_oxygenation": "muscle_oxygenation_chart.png",  # from StaticChartGenerator
    "tsi": "tsi_chart.png",  # from StaticChartGenerator
    
    # Page 20 - Body Fat Master Chart
    "body_fat_percentage_master": "body_fat_percentage_master_chart.png",  # static file
    
    # Page 21 - RHR Table
    "rhr_table": "rhr_table.png",  # from DynamicChartTableGenerator
}
