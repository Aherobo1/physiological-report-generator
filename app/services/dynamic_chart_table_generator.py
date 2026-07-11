"""
Dynamic Chart and Table Generator Service

Generates charts and tables that depend on editable metrics.
These are regenerated when the user changes values in the edit form.

Dynamic Charts (Page 4):
- Body composition chart (depends on fat%, weight)
- Body fat percentage chart (depends on fat%, age, gender)

Dynamic Charts (Page 5):
- RMR/Metabolism chart (depends on RMR, weight, height, age, gender)
- Fuel source chart (depends on rest fat percentage)

Dynamic Tables (Page 8):
- VO2 max table (depends on VO2 max value, age, gender)
- Heart rate zones table (depends on zone boundaries)

Dynamic Tables (Page 13):
- RHR table (depends on resting HR, age, gender)
"""

import base64
import io
from pathlib import Path
from typing import Dict, List, Optional, Any

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, RegularPolygon


class DynamicChartTableGenerator:
    """Generate dynamic charts and tables that depend on editable metrics."""

    def __init__(self, charts_dir: str | Path):
        """
        Initialize the dynamic chart generator.

        Args:
            charts_dir: Directory to save generated charts (typically session's dynamic_charts folder)
        """
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    def _save_chart(self, filename: str, dpi: int = 300) -> str:
        """
        Save current matplotlib figure to file and return the path.

        Args:
            filename: Name of the file to save
            dpi: Resolution of the saved image

        Returns:
            Absolute path to the saved chart
        """
        chart_path = self.charts_dir / filename
        plt.savefig(chart_path, dpi=dpi, bbox_inches="tight")
        plt.close()
        return str(chart_path)

    def _chart_to_base64(self, chart_path: str | Path) -> str:
        """
        Convert a saved chart to base64 string.

        Args:
            chart_path: Path to the chart image

        Returns:
            Base64 encoded string
        """
        with open(chart_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # ==================== PAGE 4: Body Composition Charts ====================

    def generate_body_composition_chart(
        self, fat_mass_lbs: float, lean_mass_lbs: float
    ) -> str:
        """
        Generate body composition donut chart.

        Args:
            fat_mass_lbs: Fat mass in pounds
            lean_mass_lbs: Lean mass in pounds

        Returns:
            Path to saved chart
        """
        total_weight = fat_mass_lbs + lean_mass_lbs
        fat_percentage = (fat_mass_lbs / total_weight) * 100
        lean_percentage = (lean_mass_lbs / total_weight) * 100

        sizes = [fat_percentage, lean_percentage]
        colors = ["#fde3ac", "#ff9966"]

        plt.figure(figsize=(8, 8))

        plt.pie(
            sizes,
            autopct="",
            startangle=90,
            wedgeprops=dict(width=0.5, edgecolor="w"),
            colors=colors,
            labels=["", ""],
        )

        plt.text(
            -1, 1,
            f"Fat Mass ({fat_mass_lbs:.1f}lbs)\n{fat_percentage:.1f}%",
            fontsize=14, fontweight="bold", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

        plt.text(
            1, -1,
            f"Lean Mass ({lean_mass_lbs:.1f}lbs)\n{lean_percentage:.1f}%",
            fontsize=14, fontweight="bold", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

        plt.axis("equal")

        return self._save_chart("body_composition_chart.png", dpi=600)

    def generate_body_fat_percent_chart(
        self, fat_percentage: float, age: int, gender: str
    ) -> str:
        """
        Generate body fat percentage chart with age/gender-specific ranges.

        Args:
            fat_percentage: Body fat percentage
            age: Patient age
            gender: Patient gender ('male' or 'female')

        Returns:
            Path to saved chart
        """
        # Determine age group
        if 20 <= age <= 39:
            age_group = "20-39"
        elif 40 <= age <= 59:
            age_group = "40-59"
        elif 60 <= age <= 79:
            age_group = "60-79"
        else:
            age_group = "20-39"

        gender_abbrev = "M" if gender.lower() == "male" else "F"
        demographic = f"{age_group}\n({gender_abbrev})"

        # Define segments based on gender and age group
        if gender.lower() == "female":
            if age_group == "20-39":
                segments = [
                    ("#F8A8A8", 0, 15),
                    ("#FFEECC", 15, 5),
                    ("#D0F0C0", 20, 15),
                    ("#FFEECC", 35, 5),
                    ("#F8A8A8", 40, 10),
                ]
            else:
                segments = [
                    ("#F8A8A8", 0, 20),
                    ("#FFEECC", 20, 5),
                    ("#D0F0C0", 25, 10),
                    ("#FFEECC", 35, 5),
                    ("#F8A8A8", 40, 10),
                ]
        else:  # male
            if age_group == "20-39":
                segments = [
                    ("#F8A8A8", 0, 5),
                    ("#FFEECC", 5, 5),
                    ("#D0F0C0", 10, 10),
                    ("#FFEECC", 20, 5),
                    ("#F8A8A8", 25, 25),
                ]
            elif age_group == "40-59":
                segments = [
                    ("#F8A8A8", 0, 5),
                    ("#FFEECC", 5, 5),
                    ("#D0F0C0", 10, 10),
                    ("#FFEECC", 20, 10),
                    ("#F8A8A8", 30, 20),
                ]
            else:  # 60-79
                segments = [
                    ("#F8A8A8", 0, 5),
                    ("#FFEECC", 5, 5),
                    ("#D0F0C0", 10, 15),
                    ("#FFEECC", 25, 5),
                    ("#F8A8A8", 30, 20),
                ]

        fig, ax = plt.subplots(figsize=(10, 2))

        for color, start, length in segments:
            ax.barh(
                y=0, width=length, left=start, height=1,
                color=color, edgecolor="black", linewidth=0.5,
            )

        ax.plot(
            fat_percentage, 1.05, marker="v", color="black",
            markersize=10, clip_on=False, transform=ax.get_xaxis_transform(),
        )

        ax.set_xlim(0, 50)
        ax.set_xticks(range(0, 51, 5))
        ax.set_yticks([])
        ax.text(
            -0.05, 0, demographic, transform=ax.get_yaxis_transform(),
            va="center", ha="right", fontsize=12,
        )

        ticks = range(0, 51, 5)
        ax.set_xticks(ticks)
        labels = [f"{t}%" for t in ticks]
        ax.set_xticklabels(labels)

        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(True)

        for x in range(0, 51, 5):
            ax.plot(
                [x, x], [-0.05, -0.01], color="black",
                transform=ax.get_xaxis_transform(), clip_on=False,
            )

        plt.tight_layout()

        return self._save_chart("body_fat_percent_chart.png")

    # ==================== PAGE 5: Metabolism Charts ====================

    def generate_metabolism_chart(
        self,
        rmr_kcal: float,
        weight_kg: float = None,
        height_cm: float = None,
        age_years: int = None,
        sex: str = None,
    ) -> str:
        """
        Generate metabolism chart (Slow vs Fast Metabolism).
        Uses ratio-based scale (0.3 to 1.9) comparing measured RMR to Mifflin-St Jeor prediction.

        Args:
            rmr_kcal: Resting metabolic rate in kcal/day (measured RMR)
            weight_kg: Weight in kg
            height_cm: Height in cm
            age_years: Age in years
            sex: Sex ("male" or "female")

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(11.5, 2.5))

        # Calculate ratio if we have all required parameters
        ratio = None
        if all([weight_kg, height_cm, age_years, sex]):
            if sex.lower() == "male":
                mifflin_rmr = 10 * weight_kg + 6.25 * height_cm - 5 * age_years + 5
            elif sex.lower() == "female":
                mifflin_rmr = 10 * weight_kg + 6.25 * height_cm - 5 * age_years - 161
            else:
                mifflin_rmr = None

            if mifflin_rmr and mifflin_rmr > 0:
                ratio = rmr_kcal / mifflin_rmr

        # Bar setup
        scale_edges = [0.3, 0.7, 0.9, 1.1, 1.3, 1.5, 1.9]
        scale_labels = ["Very Slow", "Slow", "Average", "Fast", "Very Fast"]
        tick_edges = scale_edges[1:-1]

        x_start = scale_edges[0]
        x_end = scale_edges[-1]
        bar_height = 0.36
        y_bar = 0.48

        color_before = "#B2FFC8"
        color_after = "#ECEDF2"
        gray_color = "#606060"

        if ratio is not None:
            highlight_end = min(max(ratio, x_start), x_end)
        else:
            min_rmr = 1000
            max_rmr = 3000
            normalized = (rmr_kcal - min_rmr) / (max_rmr - min_rmr)
            highlight_end = x_start + normalized * (x_end - x_start)
            highlight_end = min(max(highlight_end, x_start), x_end)

        ax.add_patch(
            Rectangle(
                (x_start, y_bar), x_end - x_start, bar_height,
                ec="none", fc=color_after, lw=0,
            )
        )

        if highlight_end > x_start:
            ax.add_patch(
                Rectangle(
                    (x_start, y_bar), highlight_end - x_start, bar_height,
                    ec="none", fc=color_before, lw=0,
                )
            )

        ax.text(
            x_start + 0.07, y_bar + bar_height / 2,
            f"{int(round(rmr_kcal))}kCals",
            ha="left", va="center", color=gray_color, fontsize=12, weight="bold",
            bbox=dict(boxstyle="round,pad=0.14", ec="none", fc="#B2FFC8", alpha=1.0),
        )

        ax.plot(
            [highlight_end], [y_bar + bar_height + 0.08],
            marker="v", markersize=14, color=gray_color, clip_on=False,
        )

        tick_width = 4.1
        tick_bottom = y_bar - 0.07
        tick_top = y_bar
        for edge in tick_edges:
            ax.plot(
                [edge, edge], [tick_bottom, tick_top],
                color=gray_color, lw=tick_width, solid_capstyle="butt",
                clip_on=False, zorder=2,
            )

        label_y = tick_bottom - 0.08
        for label, tick in zip(scale_labels, tick_edges):
            ax.text(
                tick, label_y, label,
                ha="center", va="top", fontsize=11, weight="bold", color=gray_color,
            )

        ax.text(
            x_start, y_bar + bar_height + 0.5,
            "Slow vs Fast Metabolism",
            ha="left", va="bottom", fontsize=14, weight="bold",
        )

        ax.set_xlim(x_start, x_end)
        ax.set_ylim(0, 1)
        ax.axis("off")

        plt.tight_layout()

        return self._save_chart("metabolism_chart.png")

    def generate_fuel_source_chart(self, fat_percentage: float) -> str:
        """
        Generate fuel source chart (Fats vs Carbs at rest).

        Args:
            fat_percentage: Fat percentage at rest

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(11.5, 2.5))

        carb_percentage = 100 - fat_percentage
        optimal_point = 75

        fats_bar = FancyBboxPatch(
            (0, 0.36), fat_percentage, 0.28,
            boxstyle="round,pad=0,rounding_size=0.1", ec="none", fc="#FEEAAB",
        )
        ax.add_patch(fats_bar)

        carbs_bar = FancyBboxPatch(
            (fat_percentage, 0.36), carb_percentage, 0.28,
            boxstyle="round,pad=0,rounding_size=0.1", ec="none", fc="#A7F5FF",
        )
        ax.add_patch(carbs_bar)

        label_fontprops = dict(fontsize=12, weight="bold", color="#333333")

        ax.text(
            fat_percentage / 2, 0.5,
            f"Fats\n{fat_percentage:.0f}%",
            ha="center", va="center", **label_fontprops,
        )
        ax.text(
            fat_percentage + carb_percentage / 2, 0.5,
            f"Carbs\n{100 - fat_percentage:.0f}%",
            ha="center", va="center", **label_fontprops,
        )

        ax.text(
            optimal_point, 0.9, "Optimal",
            ha="center", va="center", fontsize=12, weight="bold", color="#606060",
        )

        ax.plot([optimal_point, optimal_point], [0.65, 0.8], color="#606060", lw=3)
        ax.plot(fat_percentage, 0.7, "v", markersize=15, color="#606060", clip_on=False)

        positions = [0, 25, 50, 75, 100]
        tick_color = "#606060"
        for pos in positions:
            if pos == 0:
                ax.text(pos + 0.5, 0.15, str(pos), ha="center", va="center",
                        fontsize=12, color="#333333", weight="bold")
                ax.plot([pos, pos], [0.25, 0.37], color=tick_color, lw=14, solid_capstyle="butt")
            elif pos == 100:
                ax.text(pos - 0.5, 0.15, str(pos), ha="center", va="center",
                        fontsize=12, color="#333333", weight="bold")
                ax.plot([pos, pos], [0.25, 0.37], color=tick_color, lw=14, solid_capstyle="butt")
            else:
                ax.text(pos, 0.15, str(pos), ha="center", va="center",
                        fontsize=12, color="#333333", weight="bold")
                ax.plot([pos, pos], [0.25, 0.37], color=tick_color, lw=8, solid_capstyle="butt")

        ax.set_title("Fuel Source", fontsize=14, weight="bold", loc="left", pad=22)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 1)
        ax.axis("off")

        plt.tight_layout()

        return self._save_chart("fuel_source_chart.png")

    # ==================== PAGE 8: VO2 Max & Heart Rate Zones Tables ====================

    def generate_vo2_max_table(
        self,
        data: List[List],
        columns: List[str],
        vo2_max_value: float = None,
        category: str = None,
    ) -> str:
        """
        Generate VO2 Max table as an image with category highlighting.

        Args:
            data: List of rows (each row is a list of values)
            columns: List of column headers
            vo2_max_value: Patient's VO2 max value
            category: Category that the patient falls into (e.g., 'Good', 'Excellent')

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(14, 2.2))
        ax.axis("off")

        table = ax.table(
            cellText=data,
            colLabels=columns,
            cellLoc="center",
            loc="center",
            bbox=[0, 0, 1, 1],
        )

        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 1.8)

        # Header row styling
        for i in range(len(columns)):
            cell = table[(0, i)]
            cell.set_facecolor("#7dd3fc")
            cell.set_text_props(weight="bold", color="black", fontsize=12)
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(1)

        # Find category column
        category_index = None
        if category and category in columns:
            category_index = columns.index(category)

        # Data row styling
        for i in range(len(data[0])):
            cell = table[(1, i)]
            if i == 0:
                cell.set_facecolor("#a5f3fc")
                cell.set_text_props(weight="semibold", color="black", fontsize=11)
            else:
                cell.set_facecolor("#f3f4f6")
                cell.set_text_props(color="black", fontsize=10)
                if category_index is not None and i == category_index:
                    cell.set_text_props(weight="bold", color="black", fontsize=11)
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(1)

        # Add arrow indicator
        if category_index is not None:
            cell_width = 1.0 / len(columns)
            arrow_x = (category_index + 0.5) * cell_width

            arrow = FancyArrowPatch(
                (arrow_x, -0.15), (arrow_x, -0.05),
                arrowstyle="->", mutation_scale=20, linewidth=2,
                color="black", transform=ax.transAxes,
            )
            ax.add_patch(arrow)

            triangle = RegularPolygon(
                (arrow_x, -0.05), 3, radius=0.02, orientation=np.pi / 2,
                color="black", transform=ax.transAxes,
            )
            ax.add_patch(triangle)

        # Title
        if vo2_max_value is not None:
            percentile_map = {
                "Very Poor": "1st-10th percentile",
                "Poor": "10th-20th percentile",
                "Fair": "20th-40th percentile",
                "Good": "40th-60th percentile",
                "Excellent": "60th-80th percentile",
                "Superior": "100th percentile",
            }
            percentile = percentile_map.get(category, "N/A")
            title = f"VO2 Max - {vo2_max_value:.1f} ({percentile})"
            ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

        return self._save_chart("vo2_max_table.png")

    def generate_heart_rate_zones_table(
        self,
        df: pd.DataFrame,
        zone_1_start: float,
        zone_2_start: float,
        zone_3_start: float,
        zone_4_start: float,
        zone_5_start: float,
        zone_5_end: float,
        hr_col: str = "HR(bpm)_smoothed",
        speed_col: str = "Speed",
        ee_col: str = "EE(kcal/min)",
        cho_col: str = "CHO",
        bf_col: str = "BF(bpm)_smoothed",
        incline: str = "2% Incline",
    ) -> str:
        """
        Generate Heart Rate Zones table as an image with dynamic metrics.

        Args:
            df: DataFrame containing workout data with required columns
            zone_1_start: Start of Zone 1 heart rate
            zone_2_start: Start of Zone 2 heart rate (end of Zone 1)
            zone_3_start: Start of Zone 3 heart rate (end of Zone 2)
            zone_4_start: Start of Zone 4 heart rate (end of Zone 3)
            zone_5_start: Start of Zone 5 heart rate (end of Zone 4)
            zone_5_end: End of Zone 5 heart rate
            hr_col: Column name for heart rate
            speed_col: Column name for speed (mph)
            ee_col: Column name for energy expenditure (kcal/min)
            cho_col: Column name for carbohydrate burn (kcal)
            bf_col: Column name for breathing frequency
            incline: Incline description text

        Returns:
            Path to saved chart
        """
        # Create zones list from parameters
        zones_list = [
            ("Zone 1", zone_1_start, zone_2_start),
            ("Zone 2", zone_2_start, zone_3_start),
            ("Zone 3", zone_3_start, zone_4_start),
            ("Zone 4", zone_4_start, zone_5_start),
            ("Zone 5", zone_5_start, zone_5_end),
        ]

        # Fixed row descriptions
        descriptions = [
            "Improves health and\nrecovery capacity",
            "Improves endurance\nand fat burning",
            "Improves Aerobic\nfitness",
            "Improves maximum\nperformance capacity",
            "Develops maximum\nperformance and speed",
        ]

        hr_percentages = [
            "55-65% of Max Heart Rate",
            "65-75% of Max Heart Rate",
            "80-85% of Max Heart Rate",
            "85-88% of Max Heart Rate",
            "90%+ of Max Heart Rate",
        ]

        ideal_breath_ranges = [
            "Ideal Range: 15-20 breaths",
            "Ideal Range: 20-25 breaths",
            "Ideal Range: 25-30 breaths",
            "Ideal Range: 30-35 breaths",
            "Ideal Range: 40+ breaths",
        ]

        def speed_to_pace(s_mph: float) -> tuple:
            """Convert speed in mph to pace in min/km."""
            if s_mph <= 0:
                return 0, 0
            s_kmh = s_mph * 1.60934
            p_min = 60 / s_kmh
            p_m = int(p_min)
            p_s = int((p_min % 1) * 60)
            return p_m, p_s

        # Calculate metrics for each zone
        zone_metrics = {
            "HR BPM": [],
            "Speed": [],
            "Pace": [],
            "Calories": [],
            "Carb Utilization": [],
            "Breathing": [],
        }

        for i, (name, start, end) in enumerate(zones_list):
            # Filter dataframe for the current zone
            mask = (df[hr_col] >= start) & (df[hr_col] <= end)
            zone_df = df[mask]

            # HR BPM Range
            zone_metrics["HR BPM"].append(f"{int(start)}-{int(end)} bpm")

            if not zone_df.empty:
                # Speed (Range) - filter out very low speeds
                if speed_col in zone_df.columns:
                    speed_series = zone_df[zone_df[speed_col] > 0.1][speed_col]
                else:
                    speed_series = pd.Series()

                if not speed_series.empty:
                    min_speed = speed_series.min()
                    max_speed = speed_series.max()

                    if abs(min_speed - max_speed) < 0.1:
                        zone_metrics["Speed"].append(f"{min_speed:.1f} mph\n{incline}")
                    else:
                        zone_metrics["Speed"].append(f"{min_speed:.1f}-{max_speed:.1f} mph\n{incline}")

                    # Pace (Range)
                    min_pace_m, min_pace_s = speed_to_pace(max_speed)
                    max_pace_m, max_pace_s = speed_to_pace(min_speed)

                    if min_pace_m == max_pace_m and min_pace_s == max_pace_s:
                        pace_str = f"{min_pace_m}:{min_pace_s:02d} min/km Pace"
                    else:
                        pace_str = f"{max_pace_m}:{max_pace_s:02d}-{min_pace_m}:{min_pace_s:02d}\nmin/km Pace"
                    zone_metrics["Pace"].append(pace_str)
                else:
                    zone_metrics["Speed"].append(f"-\n{incline}")
                    zone_metrics["Pace"].append("-")

                # Calories (EE)
                if ee_col in zone_df.columns:
                    avg_cals = zone_df[ee_col].mean()
                    zone_metrics["Calories"].append(f"Avg:\n{avg_cals:.1f} kcals/minute")
                else:
                    zone_metrics["Calories"].append("-")

                # Carb Utilization (g/min)
                if cho_col in zone_df.columns:
                    avg_carbs_g = zone_df[cho_col].mean() / 4  # Convert kcal to grams
                    zone_metrics["Carb Utilization"].append(f"Avg: {avg_carbs_g:.1f}g/min\nCarb Utilization")
                else:
                    zone_metrics["Carb Utilization"].append("-")

                # Breathing (BF)
                if bf_col in zone_df.columns:
                    avg_breaths = zone_df[bf_col].mean()
                    ideal_range = ideal_breath_ranges[i]
                    zone_metrics["Breathing"].append(f"Avg: {int(avg_breaths)} breaths\n{ideal_range}")
                else:
                    zone_metrics["Breathing"].append(f"-\n{ideal_breath_ranges[i]}")

            else:
                zone_metrics["Speed"].append(f"-\n{incline}")
                zone_metrics["Pace"].append("-")
                zone_metrics["Calories"].append("-")
                zone_metrics["Carb Utilization"].append("-")
                zone_metrics["Breathing"].append(f"-\n{ideal_breath_ranges[i]}")

        # Prepare data for the table
        table_data = []
        table_data.append(descriptions)
        table_data.append(hr_percentages)
        table_data.append(zone_metrics["HR BPM"])
        table_data.append(zone_metrics["Speed"])
        table_data.append(zone_metrics["Pace"])
        table_data.append(zone_metrics["Calories"])
        table_data.append(zone_metrics["Carb Utilization"])
        table_data.append(zone_metrics["Breathing"])

        col_labels = [name for name, _, _ in zones_list]

        # Create the table plot
        fig, ax = plt.subplots(figsize=(13, 8))
        ax.axis("off")

        table = ax.table(
            cellText=table_data,
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 3.5)

        # Zone-specific colors
        colors = ["#fecaca", "#fecaca", "#fef08a", "#bbf7d0", "#bbf7d0"]

        # Header row styling
        for j, label in enumerate(col_labels):
            cell = table[(0, j)]
            cell.set_facecolor("#7dd3fc")
            cell.set_text_props(weight="bold")

            # HR BPM row (index 2 in data -> row 3 in table)
            cell = table[(3, j)]
            cell.set_facecolor(colors[j])
            cell.set_text_props(weight="bold")

            # Breathing row (index 7 in data -> row 8 in table)
            cell = table[(8, j)]
            cell.set_facecolor(colors[j])
            cell.set_text_props(weight="bold")

        plt.title("Personalized Heart Rate Zones", fontsize=16, fontweight="bold", pad=5)
        plt.tight_layout()

        return self._save_chart("heart_rate_zones_table.png")

    def generate_heart_rate_zones_table_simple(
        self,
        data: List[List],
        columns: List[str],
    ) -> str:
        """
        Generate Heart Rate Zones table as an image (simple version without DataFrame).

        Args:
            data: List of rows (each row is a list of values)
            columns: List of column headers (Zone 1-5)

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.axis("off")

        table = ax.table(
            cellText=data,
            colLabels=columns,
            loc="center",
            cellLoc="center",
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 3.5)

        # Header row styling
        for j, label in enumerate(columns):
            cell = table[(0, j)]
            cell.set_facecolor("#7dd3fc")
            cell.set_text_props(weight="bold")

        # Zone-specific colors
        colors = ["#fecaca", "#fecaca", "#fef08a", "#bbf7d0", "#bbf7d0"]

        # HR BPM row (index 2 in data -> row 3 in table)
        for j in range(len(columns)):
            cell = table[(3, j)]
            cell.set_facecolor(colors[j])
            cell.set_text_props(weight="bold")

        # Breathing row (index 7 in data -> row 8 in table)
        for j in range(len(columns)):
            cell = table[(8, j)]
            cell.set_facecolor(colors[j])
            cell.set_text_props(weight="bold")

        plt.title("Personalized Heart Rate Zones", fontsize=16, fontweight="bold", pad=5)
        plt.tight_layout()

        return self._save_chart("heart_rate_zones_table.png")

    # ==================== PAGE 13: RHR Table ====================

    def generate_resting_heart_rate_table(
        self,
        data: List[List],
        columns: List[str],
        rhr_value: float = None,
        category: str = None,
    ) -> str:
        """
        Generate Resting Heart Rate table as an image with category highlighting.

        Args:
            data: List of rows (each row is a list of values)
            columns: List of column headers
            rhr_value: Patient's resting heart rate value in bpm
            category: Category that the patient falls into

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(16, 2.2))
        ax.axis("off")

        table = ax.table(
            cellText=data,
            colLabels=columns,
            cellLoc="center",
            loc="center",
            bbox=[0, 0, 1, 1],
        )

        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 1.8)

        # Header row styling
        for i in range(len(columns)):
            cell = table[(0, i)]
            cell.set_facecolor("#7dd3fc")
            cell.set_text_props(weight="bold", color="black", fontsize=12)
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(1)

        # Find category column
        category_index = None
        if category and category in columns:
            category_index = columns.index(category)

        # Data row styling
        for i in range(len(data[0])):
            cell = table[(1, i)]
            if i == 0:
                cell.set_facecolor("#a5f3fc")
                cell.set_text_props(weight="semibold", color="black", fontsize=11)
            else:
                if category_index is not None and i == category_index:
                    cell.set_facecolor("#d1fae5")
                    cell.set_text_props(weight="bold", color="black", fontsize=11)
                else:
                    cell.set_facecolor("#f3f4f6")
                    cell.set_text_props(color="black", fontsize=10)
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(1)

        # Add arrow indicator
        if category_index is not None:
            cell_width = 1.0 / len(columns)
            arrow_x = (category_index + 0.5) * cell_width

            arrow = FancyArrowPatch(
                (arrow_x, -0.15), (arrow_x, -0.05),
                arrowstyle="->", mutation_scale=20, linewidth=2,
                color="black", transform=ax.transAxes,
            )
            ax.add_patch(arrow)

            triangle = RegularPolygon(
                (arrow_x, -0.05), 3, radius=0.02, orientation=np.pi / 2,
                color="black", transform=ax.transAxes,
            )
            ax.add_patch(triangle)

        # Title
        if rhr_value is not None:
            title = f"Resting Heart Rate - {rhr_value:.0f}bpm"
            ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

        return self._save_chart("rhr_table.png")

    # ==================== Utility Methods ====================

    def delete_all_charts(self) -> None:
        """Delete all dynamic charts in the directory (for regeneration)."""
        for chart_file in self.charts_dir.glob("*.png"):
            chart_file.unlink()

    def get_chart_path(self, chart_type: str) -> Optional[str]:
        """
        Get the path to a specific chart if it exists.

        Args:
            chart_type: Type of chart (e.g., 'body_composition', 'metabolism')

        Returns:
            Path to chart file or None if not found
        """
        filename_map = {
            "body_composition": "body_composition_chart.png",
            "body_fat_percentage": "body_fat_percent_chart.png",
            "metabolism": "metabolism_chart.png",
            "fuel_source": "fuel_source_chart.png",
            "vo2_max_table": "vo2_max_table.png",
            "heart_rate_zones_table": "heart_rate_zones_table.png",
            "rhr_table": "rhr_table.png",
        }
        
        filename = filename_map.get(chart_type)
        if filename:
            chart_path = self.charts_dir / filename
            if chart_path.exists():
                return str(chart_path)
        return None
