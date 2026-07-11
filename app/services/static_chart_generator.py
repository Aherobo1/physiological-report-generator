"""
Static Chart Generator Service

Generates charts that depend only on raw data and don't change based on user edits.
These charts are generated once on file upload and stored for reuse.

Static Charts:
- Page 7: Spirometry chart (from spirometry PDF), VT/Respiratory chart (from Pnoe CSV)
- Page 9: Relative VO2 chart (from Pnoe CSV)
- Page 10: Fuel utilization chart (from Pnoe CSV)
- Page 12: VO2 pulse chart, VO2 breath chart (from Pnoe CSV)
- Page 13: Fat and carbs chart, Recovery chart (from Pnoe CSV)
- Page 14: SmO2/TSI chart (from oxygenation CSV)
"""

import base64
import io
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyBboxPatch


class StaticChartGenerator:
    """Generate static (immutable) charts from raw data files."""

    # Define a color palette for phase backgrounds
    PHASE_COLORS = [
        "lightblue",
        "purple",
        "lightgreen",
        "blue",
        "orange",
        "pink",
        "yellow",
        "cyan",
        "magenta",
        "lime",
    ]

    def __init__(self, charts_dir: str | Path):
        """
        Initialize the static chart generator.

        Args:
            charts_dir: Directory to save generated charts (typically session's static_charts folder)
        """
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    def _add_phase_backgrounds(self, ax, phase_times: list, max_time: float) -> None:
        """
        Add colored background regions for phases dynamically.

        Args:
            ax: Matplotlib axis to add backgrounds to
            phase_times: List of phase start times
            max_time: Maximum time value for the last phase
        """
        if len(phase_times) < 2:
            return

        for i in range(len(phase_times)):
            start = phase_times[i] if i > 0 else 0
            end = phase_times[i + 1] if i + 1 < len(phase_times) else max_time
            color = self.PHASE_COLORS[i % len(self.PHASE_COLORS)]
            ax.axvspan(start, end, alpha=0.2, color=color)

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

    # ==================== PAGE 7: Spirometry & Respiratory Charts ====================

    def generate_spirometry_chart(self, spirometry_df: pd.DataFrame) -> str:
        """
        Generate spirometry chart with Z-scores.

        Args:
            spirometry_df: Spirometry DataFrame with FVC, FEV1, FEV1/FVC% parameters

        Returns:
            Path to saved chart
        """
        # Coerce numeric columns
        for col in ['Best', 'LLN', 'Pred.', '%Pred.', 'ZScore']:
            if col in spirometry_df.columns:
                spirometry_df[col] = pd.to_numeric(spirometry_df[col], errors='coerce')

        # Select rows of interest and prepare display values
        rows_map = {
            'Lung Volume': 'FVC',
            'Lung Power': 'FEV1',
            'Power/Volume': 'FEV1/FVC%'
        }

        records = []
        for label, param in rows_map.items():
            row = spirometry_df.loc[spirometry_df['Parameters'].str.strip() == param]
            if row.empty:
                continue
            row = row.iloc[0]
            records.append({
                'label': label,
                'param': param,
                'best': row['Best'],
                'pct': row['%Pred.'],
                'z': row['ZScore']
            })

        # Figure setup
        fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(11.5, 3.6), sharex=True,
                                gridspec_kw={'hspace': 0.65})

        x_min, x_max = -5, 3
        # Segment colors: red -> orange -> yellow -> green
        segments = [
            (-5, -4, '#f4a7a7'),   # red-ish
            (-4, -3, '#f7c49a'),   # orange-ish
            (-3, -1.7, '#f6e3a3'),   # yellow-ish
            (-1.7,  3, '#c9f0cc'),   # green-ish
        ]

        ticks = np.arange(x_min, x_max + 1, 1)
        labels = [str(i) for i in ticks]

        # Plot each row
        for ax, rec in zip(axes, records):
            # Background segments
            for a, b, color in segments:
                ax.barh(0, width=b-a, left=a, height=0.6, color=color, edgecolor='none')

            # LLN (-1) and Predicted (0) markers
            ax.axvline(0, color='black', lw=1)

            # Z-score pointer (downward triangle) at top of each panel
            if pd.notna(rec['z']):
                trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
                ax.plot(float(rec['z']), 1.2, marker='v', markersize=12, color='dimgray',
                        transform=trans, clip_on=False)

            # Labels, ticks, and styling
            ax.set_title(rec['label'], loc='left', fontsize=11, fontweight='bold', pad=2)
            ax.set_xlim(x_min, x_max)
            ax.set_yticks([])
            ax.set_xticks(ticks)
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_xlabel('')

        # Top annotations
        axes[0].text(-1.7, 0.45, 'LLN', ha='center', va='bottom', fontsize=9)
        axes[0].text(0, 0.45, 'Predicted', ha='center', va='bottom', fontsize=9)

        # Right-side summary boxes
        fig.subplots_adjust(right=0.78)
        box_ax = fig.add_axes([0.805, 0.06, 0.18, 0.90])  # [left, bottom, width, height]
        box_ax.axis('off')

        # Helper to draw a pill-shaped text box
        def pill(ax, xy, text):
            x, y = xy
            # Draw rounded rectangle background
            bbox = FancyBboxPatch((x-0.48, y-0.09), 0.96, 0.18,
                                boxstyle='round,pad=0.02,rounding_size=0.08',
                                ec='#dddddd', fc='#f3f3f3', linewidth=1.0)
            ax.add_patch(bbox)
            ax.text(x, y+0.025, text, ha='center', va='center', fontsize=11, fontweight='bold')
            ax.text(x, y-0.055, 'of predicted', ha='center', va='center', fontsize=9, color='#555555')

        box_ax.set_xlim(0, 1)
        box_ax.set_ylim(0, 1)

        # Prepare display strings and positions (top to bottom)
        right_items = []
        for rec in records:
            name = 'FVC' if rec['param'] == 'FVC' else ('FEV1' if rec['param'] == 'FEV1' else 'FEV1/FVC')
            unit = 'L' if rec['param'] in ('FVC', 'FEV1') else '%'
            value_fmt = f"{rec['best']:.2f}{unit}"
            pct_fmt = f"{rec['pct']:.1f}%"
            right_items.append((name, value_fmt, pct_fmt))

        # Sort to match image order on the right (FVC, FEV1, FEV1/FVC)
        order = ['FVC', 'FEV1', 'FEV1/FVC']
        right_items_sorted = [next(item for item in right_items if item[0] == k) for k in order]

        ys = [0.82, 0.48, 0.15]
        for (name, value_fmt, pct_fmt), y in zip(right_items_sorted, ys):
            main_line = f"{name}\n{value_fmt} → {pct_fmt}"
            pill(box_ax, (0.5, y), main_line)

        return self._save_chart("spirometry_chart.png")

    def generate_respiratory_chart(self, df: pd.DataFrame) -> str:
        """
        Generate respiratory/VT chart (VT and Speed over time).

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        first_unique_phase = df.drop_duplicates(subset="PHASE")
        phase_times = first_unique_phase["T(sec)"].tolist()

        plt.figure(figsize=(18, 5))
        ax1 = plt.subplot()

        sns.lineplot(data=df, x="T(sec)", y="VT(l)_smoothed", label="VT (L)")
        ax1.set_xlabel("Time (sec)")
        ax1.set_ylabel("VT (L)")
        ax1.grid(True, alpha=0.1)
        ax1.set_ylim(0, min(8, df["VT(l)_smoothed"].max()))

        ax2 = ax1.twinx()
        ax1.set_xticks(np.arange(0, df["T(sec)"].max() + 200, 200))
        sns.lineplot(
            data=df, x="T(sec)", y="Speed", color="green", ax=ax2,
            drawstyle="steps-post", linewidth=2, label="Speed",
        )
        ax2.set_ylabel("Speed")
        ax2.set_ylim(0, min(30, df["Speed"].max()) + 1)

        ax1.get_legend().remove()
        ax2.get_legend().remove()
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        self._add_phase_backgrounds(ax1, phase_times, df["T(sec)"].max())

        return self._save_chart("respiratory_chart.png")

    # ==================== PAGE 9: Relative VO2 Chart ====================

    def generate_relative_vo2_chart(
        self, df: pd.DataFrame, weight_kg: float, client_name: str = ""
    ) -> str:
        """
        Generate Relative VO2 at Each Stage vs VO2max chart.

        Args:
            df: Processed Pnoe DataFrame with VO2, HR, and Watts columns
            weight_kg: Client weight in kg
            client_name: Client name for chart title

        Returns:
            Path to saved chart
        """
        vo2_max = df["VO2(ml/min)"].rolling(window=2, center=True).mean().max() / weight_kg

        df_stages = df[df["Watts"] > 0].copy()
        stage_data = (
            df_stages.groupby("Watts")
            .agg({"VO2(ml/min)": "mean", "HR(bpm)": "mean"})
            .reset_index()
        )

        stage_data["Relative VO2"] = stage_data["VO2(ml/min)"] / weight_kg
        stage_data["% of VO2max"] = (stage_data["Relative VO2"] / vo2_max) * 100

        fig, ax1 = plt.subplots(figsize=(10, 6))

        bars = ax1.bar(
            stage_data["Watts"].astype(str),
            stage_data["% of VO2max"],
            color="#43a2ca", alpha=0.8, width=0.5,
        )

        ax2 = ax1.twinx()
        ax2.plot(
            stage_data["Watts"].astype(str),
            stage_data["HR(bpm)"],
            color="#e74c3c", marker="o", linewidth=2, markersize=6,
        )

        ax1.set_xlabel("Stage (Watts)", fontsize=12)
        ax1.set_ylabel("% of VO2max", fontsize=12)
        ax2.set_ylabel("Heart Rate (bpm)", fontsize=12, color="#e74c3c")
        ax2.tick_params(axis="y", labelcolor="#e74c3c")

        ax1.set_ylim(0, 120)
        ax2.set_ylim(80, 170)

        for i, bar in enumerate(bars):
            height = bar.get_height()
            watts = stage_data.loc[i, "Watts"]
            ax1.text(
                bar.get_x() + bar.get_width() / 2.0, height + 1,
                f"{watts:.0f} W\n{height:.1f}%",
                ha="center", va="bottom", fontsize=8, color="#2b7bba",
            )

        title = "Relative VO2 at Each Stage vs VO2max\nBike Ramp Test"
        if client_name:
            title += f" ({client_name})"
        plt.title(title, fontsize=14)
        ax1.grid(True, axis="y", linestyle="--", alpha=0.3)
        ax1.spines["top"].set_visible(False)
        ax2.spines["top"].set_visible(False)

        plt.tight_layout()

        return self._save_chart("relative_vo2_chart.png")

    # ==================== PAGE 10: Fuel Utilization Chart ====================

    def generate_fuel_utilization_chart(self, df: pd.DataFrame) -> str:
        """
        Generate fuel utilization chart (CHO vs FAT by stage).

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        speed_groups = df.groupby("Speed").mean(numeric_only=True).round(1)
        speed_groups = speed_groups.iloc[1:-1]

        filtered_data = speed_groups[
            (speed_groups.index >= 3.5) & (speed_groups.index <= 7.5)
        ]

        plt.figure(figsize=(15, 8))
        plt.style.use("default")

        stage_labels = [f"Stage {i}" for i in range(1, len(filtered_data) + 1)]
        x_positions = np.arange(len(filtered_data))

        fat_ee = filtered_data["EE(kcal/min)"] * filtered_data["FAT(%)"] / 100
        carbs_ee = filtered_data["EE(kcal/min)"] * filtered_data["CARBS(%)"] / 100

        ax1 = plt.gca()

        ax1.bar(x_positions, fat_ee, color="#1f77b4", alpha=0.8, width=0.6, label="Fat")
        ax1.bar(x_positions, carbs_ee, bottom=fat_ee, color="#ff7f0e", alpha=0.8, width=0.6, label="Carbs")

        ax1.set_xlabel("", fontsize=12)
        ax1.set_ylabel("Fuel (kcal/min)", fontsize=12)
        ax1.set_ylim(0, 20)

        for i, (fat_val, carb_val, total_val) in enumerate(
            zip(fat_ee, carbs_ee, filtered_data["EE(kcal/min)"])
        ):
            if fat_val > 0.3:
                ax1.text(i, fat_val / 2, f"{fat_val:.1f}", ha="center", va="center",
                         fontsize=9, fontweight="bold", color="white")
            if carb_val > 0.3:
                ax1.text(i, fat_val + carb_val / 2, f"{carb_val:.1f}", ha="center", va="center",
                         fontsize=9, fontweight="bold", color="white")
            ax1.text(i, total_val + 0.5, f"{total_val:.1f} kcal", ha="center", va="bottom",
                     fontsize=10, fontweight="bold", color="black")

        for i, speed in enumerate(filtered_data.index):
            ax1.text(i, -1.5, f"{speed:.1f} mph", ha="center", va="top", fontsize=9)
            ax1.text(i, -2.8, f"{speed * 1.609:.1f} min/km", ha="center", va="top", fontsize=8, color="gray")

        ax2 = ax1.twinx()
        ax2.plot(x_positions, filtered_data["HR(bpm)"], marker="o", linewidth=3,
                 markersize=8, color="red", label="Heart Rate")

        ax2.set_ylabel("Heart Rate (bpm)", fontsize=12, color="red")
        ax2.tick_params(axis="y", labelcolor="red")
        ax2.set_ylim(0, 220)

        for i, hr in enumerate(filtered_data["HR(bpm)"]):
            ax2.text(i, hr + 10, f"{int(hr)}bpm", ha="center", va="bottom",
                     fontsize=10, fontweight="bold", color="red")

        ax1.set_xticks(x_positions)
        ax1.set_xticklabels(stage_labels, fontsize=11)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
                   frameon=True, fancybox=True, shadow=True)

        ax1.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
        ax1.set_axisbelow(True)

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.1, top=0.9)

        return self._save_chart("fuel_utilization_chart.png")

    # ==================== PAGE 12: VO2 Pulse & VO2 Breath Charts ====================

    def generate_vo2_pulse_chart(self, df: pd.DataFrame) -> str:
        """
        Generate VO2 Pulse chart with HR and Speed.

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        first_unique_phase = df.drop_duplicates(subset="PHASE")
        phase_times = first_unique_phase["T(sec)"].tolist()

        plt.figure(figsize=(18, 5))
        ax1 = plt.subplot()

        sns.lineplot(data=df, x="T(sec)", y="VO2 Pulse_smoothed",
                     label="VO2 Pulse (mL/beat)", color="blue")
        ax1.set_xlabel("Time (sec)")
        ax1.set_ylabel("VO2 Pulse (mL/beat)")
        ax1.set_ylim(0, df["VO2 Pulse_smoothed"].max())
        ax1.grid(True, alpha=0.1)

        ax2 = ax1.twinx()
        sns.lineplot(data=df, x="T(sec)", y="HR(bpm)_smoothed",
                     color="red", ax=ax2, linewidth=2, label="Heart Rate (bpm)")
        ax2.set_ylabel("Heart Rate (bpm)", color="red")
        ax2.tick_params(axis="y", labelcolor="red")
        ax2.set_ylim(0, df["HR(bpm)_smoothed"].max() + 1)

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        sns.lineplot(data=df, x="T(sec)", y="Speed", color="green", ax=ax3,
                     drawstyle="steps-post", linewidth=2, label="Speed")
        ax3.set_ylabel("Speed", color="green")
        ax3.tick_params(axis="y", labelcolor="green")
        ax3.set_ylim(0, df["Speed"].max() + 1)

        ax1.set_xticks(np.arange(0, df["T(sec)"].max() + 200, 200))

        for ax in [ax1, ax2, ax3]:
            if ax.get_legend():
                ax.get_legend().remove()

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines3, labels3 = ax3.get_legend_handles_labels()
        ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3, loc="upper left")

        self._add_phase_backgrounds(ax1, phase_times, df["T(sec)"].max())

        return self._save_chart("vo2_pulse_chart.png")

    def generate_vo2_breath_chart(self, df: pd.DataFrame) -> str:
        """
        Generate VO2 per Breath chart.

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        first_unique_phase = df.drop_duplicates(subset="PHASE")
        phase_times = first_unique_phase["T(sec)"].tolist()

        plt.figure(figsize=(18, 5))
        ax1 = plt.subplot()

        sns.lineplot(data=df, x="T(sec)", y="VO2 Breath_smoothed",
                     label="VO2 per Breath (mL/breath)")
        ax1.set_xlabel("Time (sec)")
        ax1.set_ylabel("VO2 per Breath (mL/breath)")
        ax1.set_ylim(0, df["VO2 Breath_smoothed"].max() + 1)
        ax1.grid(True, alpha=0.1)

        ax2 = ax1.twinx()
        ax1.set_xticks(np.arange(0, df["T(sec)"].max() + 200, 200))
        sns.lineplot(data=df, x="T(sec)", y="Speed", color="green", ax=ax2,
                     drawstyle="steps-post", linewidth=2, label="Speed")
        ax2.set_ylim(0, df["Speed"].max() + 1)
        ax2.set_ylabel("Speed")

        ax1.get_legend().remove()
        ax2.get_legend().remove()
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        self._add_phase_backgrounds(ax1, phase_times, df["T(sec)"].max())

        return self._save_chart("vo2_breath_chart.png")

    # ==================== PAGE 13: Fat Metabolism & Recovery Charts ====================

    def generate_fat_metabolism_chart(self, df: pd.DataFrame) -> str:
        """
        Generate fat metabolism chart (CHO vs FAT over time).

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        first_unique_phase = df.drop_duplicates(subset="PHASE")
        phase_times = first_unique_phase["T(sec)"].tolist()

        plt.figure(figsize=(18, 5))
        ax1 = plt.subplot()

        sns.lineplot(data=df, x="T(sec)", y="CHO_smoothed", label="CHO (kcal/min)")
        ax1.set_xlabel("Time (sec)")
        ax1.set_ylabel("CHO (g/min)")
        ax1.grid(True, alpha=0.1)

        ax2 = ax1.twinx()
        ax1.set_xticks(np.arange(0, df["T(sec)"].max() + 200, 200))
        sns.lineplot(data=df, x="T(sec)", y="FAT_smoothed", color="green", ax=ax2,
                     label="FAT (kcal/min)")
        ax2.set_ylabel("FAT (kcal/min)")
        ax2.set_ylim(0, 15)

        ax1.get_legend().remove()
        ax2.get_legend().remove()
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

        self._add_phase_backgrounds(ax1, phase_times, df["T(sec)"].max())

        return self._save_chart("fat_metabolism_chart.png")

    def generate_recovery_chart(self, df: pd.DataFrame) -> str:
        """
        Generate recovery chart (VCO2, HR, and BF).

        Args:
            df: Processed Pnoe DataFrame with smoothed columns

        Returns:
            Path to saved chart
        """
        first_unique_phase = df.drop_duplicates(subset="PHASE")
        phase_times = first_unique_phase["T(sec)"].tolist()

        plt.figure(figsize=(18, 5))
        ax1 = plt.subplot()

        sns.lineplot(data=df, x="T(sec)", y="VCO2(ml/min)_smoothed",
                     label="VCO2 (ml/min)", color="blue")
        ax1.set_xlabel("Time (sec)")
        ax1.set_ylabel("VO2 Pulse (mL/beat)")
        ax1.set_ylim(0, df["VCO2(ml/min)"].max())
        ax1.grid(True, alpha=0.1)

        ax2 = ax1.twinx()
        sns.lineplot(data=df, x="T(sec)", y="HR(bpm)_smoothed",
                     color="red", ax=ax2, linewidth=2, label="Heart Rate (bpm)")
        ax2.set_ylabel("Heart Rate (bpm)", color="red")
        ax2.set_ylim(df["HR(bpm)_smoothed"].min(), df["HR(bpm)_smoothed"].max() + 1)
        ax2.tick_params(axis="y", labelcolor="red")

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        sns.lineplot(data=df, x="T(sec)", y="BF(bpm)_smoothed",
                     color="green", ax=ax3, linewidth=2, label="BF (bpm)")
        ax3.set_ylabel("BF (bpm)", color="green")
        ax3.tick_params(axis="y", labelcolor="green")
        ax3.set_ylim(0, df["BF(bpm)_smoothed"].max() + 1)
        ax1.set_xticks(np.arange(0, df["T(sec)"].max() + 200, 200))

        for ax in [ax1, ax2, ax3]:
            if ax.get_legend():
                ax.get_legend().remove()

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines3, labels3 = ax3.get_legend_handles_labels()
        ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3, loc="upper left")

        self._add_phase_backgrounds(ax1, phase_times, df["T(sec)"].max())

        return self._save_chart("recovery_chart.png")

    # ==================== PAGE 14: Muscle Oxygenation (SmO2) Charts ====================

    def generate_tsi_chart(self, oxygenation_df: pd.DataFrame) -> str:
        """
        Generate TSI (Tissue Saturation Index) chart with trend lines per stage.

        Args:
            oxygenation_df: DataFrame with Time, TSI, and TSI-second columns

        Returns:
            Path to saved chart
        """
        from numpy.polynomial.polynomial import Polynomial

        plt.figure(figsize=(12, 5.5))

        plt.plot(oxygenation_df["Time"], oxygenation_df["TSI"],
                 label="TSI (Left Leg)", color="steelblue", linewidth=2)
        plt.plot(oxygenation_df["Time"], oxygenation_df["TSI-second"],
                 label="TSI2 (Right Leg)", color="orange", linewidth=2)

        max_time = oxygenation_df["Time"].max()
        intervals = [
            (0, 250), (250, 500), (500, 750), (750, 1000),
            (1000, 1250), (1250, 1500), (1500, max_time),
        ]

        for start_time, end_time in intervals:
            mask_interval = (oxygenation_df["Time"] >= start_time) & \
                           (oxygenation_df["Time"] <= end_time)

            mask_left = mask_interval & ~oxygenation_df["TSI"].isna()
            if mask_left.sum() > 1:
                x_left = oxygenation_df.loc[mask_left, "Time"]
                y_left = oxygenation_df.loc[mask_left, "TSI"]
                coefs_left = Polynomial.fit(x_left, y_left, 1).convert().coef
                trend_left = coefs_left[0] + coefs_left[1] * x_left
                plt.plot(x_left, trend_left, color="black", linestyle="--", linewidth=2, alpha=0.8)

            mask_right = mask_interval & ~oxygenation_df["TSI-second"].isna()
            if mask_right.sum() > 1:
                x_right = oxygenation_df.loc[mask_right, "Time"]
                y_right = oxygenation_df.loc[mask_right, "TSI-second"]
                coefs_right = Polynomial.fit(x_right, y_right, 1).convert().coef
                trend_right = coefs_right[0] + coefs_right[1] * x_right
                plt.plot(x_right, trend_right, color="black", linestyle="--", linewidth=2, alpha=0.8)

        plt.xlabel("Time (s)")
        plt.ylabel("TSI (%)")
        plt.title("TSI (Left) and TSI2 (Right) with Black Slope Lines per Stage")
        plt.legend(fontsize=10, loc="upper right")
        plt.grid(alpha=0.25)
        plt.tight_layout()

        return self._save_chart("tsi_chart.png", dpi=160)

    def generate_muscle_oxygenation_chart(
        self, oxygenation_df: pd.DataFrame
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate comprehensive muscle oxygenation (SmO2) chart with both legs and heart rate.

        Args:
            oxygenation_df: DataFrame with muscle oxygenation data (Train.Red CSV format)

        Returns:
            Tuple of (chart_path, metrics_dict)
        """
        df_oxy = oxygenation_df.copy()

        df_oxy["Timestamp (seconds passed)"] = pd.to_numeric(
            df_oxy["Timestamp (seconds passed)"], errors="coerce"
        )
        df_oxy["Left_SmO2"] = pd.to_numeric(df_oxy["SmO2"], errors="coerce")
        df_oxy["Right_SmO2"] = pd.to_numeric(df_oxy["SmO2.1"], errors="coerce")
        df_oxy["Heart_Rate"] = pd.to_numeric(df_oxy["Heart Rate (BPM)"], errors="coerce")
        df_oxy["Lap"] = pd.to_numeric(df_oxy["Lap/Event"], errors="coerce")

        df_oxy = df_oxy.dropna(subset=["Timestamp (seconds passed)"])
        df_oxy = df_oxy.sort_values("Timestamp (seconds passed)").reset_index(drop=True)

        time_diffs = df_oxy["Timestamp (seconds passed)"].diff().dropna()
        avg_sampling_interval = time_diffs.median()
        sampling_freq = 1 / avg_sampling_interval if avg_sampling_interval > 0 else 10
        window_samples = int(10 * sampling_freq)

        df_oxy["Left_SmO2_smooth"] = df_oxy["Left_SmO2"].rolling(
            window=window_samples, center=True, min_periods=5
        ).mean()
        df_oxy["Right_SmO2_smooth"] = df_oxy["Right_SmO2"].rolling(
            window=window_samples, center=True, min_periods=5
        ).mean()
        df_oxy["Heart_Rate_smooth"] = df_oxy["Heart_Rate"].rolling(
            window=window_samples, center=True, min_periods=5
        ).mean()

        lap_changes = df_oxy[df_oxy["Lap"].diff() != 0].copy()
        lap_starts = {}
        for idx, row in lap_changes.iterrows():
            lap_num = int(row["Lap"])
            lap_starts[lap_num] = row["Timestamp (seconds passed)"]

        warm_up_end = lap_starts.get(1, df_oxy["Timestamp (seconds passed)"].max())
        recovery_start = lap_starts.get(7, df_oxy["Timestamp (seconds passed)"].max())

        warm_up_last_30_start = warm_up_end - 30
        warm_up_mask = (df_oxy["Timestamp (seconds passed)"] >= warm_up_last_30_start) & \
                       (df_oxy["Timestamp (seconds passed)"] <= warm_up_end)

        recovery_end = df_oxy["Timestamp (seconds passed)"].max()
        recovery_last_30_start = recovery_end - 30
        recovery_mask = (df_oxy["Timestamp (seconds passed)"] >= recovery_last_30_start) & \
                        (df_oxy["Timestamp (seconds passed)"] <= recovery_end)

        left_warmup_avg = df_oxy.loc[warm_up_mask, "Left_SmO2_smooth"].mean()
        left_recovery_avg = df_oxy.loc[recovery_mask, "Left_SmO2_smooth"].mean()
        left_recovery_pct = round((left_recovery_avg / left_warmup_avg) * 100)

        right_warmup_avg = df_oxy.loc[warm_up_mask, "Right_SmO2_smooth"].mean()
        right_recovery_avg = df_oxy.loc[recovery_mask, "Right_SmO2_smooth"].mean()
        right_recovery_pct = round((right_recovery_avg / right_warmup_avg) * 100)

        active_mask = (df_oxy["Timestamp (seconds passed)"] >= warm_up_end) & \
                      (df_oxy["Timestamp (seconds passed)"] <= recovery_start)
        active_data = df_oxy[active_mask]

        left_min = active_data["Left_SmO2_smooth"].min()
        left_min_lap = int(active_data.loc[active_data["Left_SmO2_smooth"].idxmin(), "Lap"])
        right_min = active_data["Right_SmO2_smooth"].min()
        right_min_lap = int(active_data.loc[active_data["Right_SmO2_smooth"].idxmin(), "Lap"])

        left_drop = left_warmup_avg - left_min
        right_drop = right_warmup_avg - right_min

        hr_warmup = df_oxy[df_oxy["Timestamp (seconds passed)"] <= warm_up_end]["Heart_Rate_smooth"].mean()
        hr_max = active_data["Heart_Rate_smooth"].max()

        fig, ax1 = plt.subplots(figsize=(18, 8))

        time = df_oxy["Timestamp (seconds passed)"]
        ax1.plot(time, df_oxy["Left_SmO2_smooth"],
                 label=f"Left SmO₂ (Rec {left_recovery_pct}% of warm-up)",
                 color="#2E86AB", linewidth=2)
        ax1.plot(time, df_oxy["Right_SmO2_smooth"],
                 label=f"Right SmO₂ (Rec {right_recovery_pct}% of warm-up)",
                 color="#A23B72", linewidth=2)

        ax1.set_xlabel("Time (seconds)", fontsize=12, fontweight="bold")
        ax1.set_ylabel("SmO₂ (%)", fontsize=12, fontweight="bold")
        ax1.tick_params(axis="y", labelcolor="black")
        ax1.grid(True, alpha=0.3, linestyle="--")

        ax2 = ax1.twinx()
        ax2.plot(time, df_oxy["Heart_Rate_smooth"], label="Heart Rate",
                 color="red", linewidth=1.5, linestyle="--", alpha=0.7)
        ax2.set_ylabel("Heart Rate (BPM)", fontsize=12, fontweight="bold", color="red")
        ax2.tick_params(axis="y", labelcolor="red")

        ax1.axvspan(0, warm_up_end, alpha=0.15, color="blue", label="Warm-up")

        active_laps = [1, 2, 3, 4, 5, 6]
        colors_active = ["yellow", "orange"] * 3
        for i, lap in enumerate(active_laps):
            start = lap_starts.get(lap, 0)
            end = lap_starts.get(lap + 1, recovery_start) if lap < 6 else recovery_start
            ax1.axvspan(start, end, alpha=0.1, color=colors_active[i])

        ax1.axvspan(recovery_start, recovery_end, alpha=0.2, color="gray", label="Recovery")
        ax1.axvline(x=recovery_start, color="black", linestyle="-", linewidth=2, alpha=0.7)

        for lap in range(1, 7):
            start = lap_starts.get(lap, 0)
            end = lap_starts.get(lap + 1, recovery_start) if lap < 6 else recovery_start
            mid = (start + end) / 2
            ax1.text(mid, ax1.get_ylim()[1] * 0.97, f"Lap {lap}",
                     ha="center", va="top", fontsize=10, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))

        plt.title("Train.Red SmO₂ Ramp - Muscle Oxygenation Analysis",
                  fontsize=16, fontweight="bold", pad=20)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10, framealpha=0.9)

        plt.tight_layout()

        metrics = {
            "left_baseline_smo2": f"{left_warmup_avg:.1f}%",
            "right_baseline_smo2": f"{right_warmup_avg:.1f}%",
            "left_minimum_smo2": f"{left_min:.1f}%",
            "right_minimum_smo2": f"{right_min:.1f}%",
            "left_minimum_lap": f"Lap {left_min_lap}",
            "right_minimum_lap": f"Lap {right_min_lap}",
            "left_oxygen_drop": f"{left_drop:.1f}%",
            "right_oxygen_drop": f"{right_drop:.1f}%",
            "left_drop_percentage": f"{(left_drop / left_warmup_avg * 100):.0f}% decrease",
            "right_drop_percentage": f"{(right_drop / right_warmup_avg * 100):.0f}% decrease",
            "left_recovery_percentage": f"{left_recovery_pct}%",
            "right_recovery_percentage": f"{right_recovery_pct}%",
            "hr_warmup": f"{hr_warmup:.0f}",
            "hr_max": f"{hr_max:.0f}",
            "test_duration": f"~{(recovery_start - warm_up_end) / 60:.0f} minutes active test",
            "recovery_assessment": "Excellent recovery capacity"
            if (left_recovery_pct + right_recovery_pct) / 2 >= 100
            else "Good recovery capacity",
        }

        chart_path = self._save_chart("muscle_oxygenation_chart.png")
        return chart_path, metrics

    # ==================== Batch Generation ====================

    def generate_all_pnoe_charts(
        self, df: pd.DataFrame, weight_kg: float, client_name: str = ""
    ) -> Dict[str, str]:
        """
        Generate all static charts from Pnoe data.

        Args:
            df: Processed Pnoe DataFrame with smoothed columns
            weight_kg: Client weight in kg
            client_name: Client name for chart titles

        Returns:
            Dictionary mapping chart type to file path
        """
        charts = {}
        
        charts["respiratory"] = self.generate_respiratory_chart(df)
        charts["relative_vo2"] = self.generate_relative_vo2_chart(df, weight_kg, client_name)
        charts["fuel_utilization"] = self.generate_fuel_utilization_chart(df)
        charts["vo2_pulse"] = self.generate_vo2_pulse_chart(df)
        charts["vo2_breath"] = self.generate_vo2_breath_chart(df)
        charts["fat_metabolism"] = self.generate_fat_metabolism_chart(df)
        charts["recovery"] = self.generate_recovery_chart(df)
        
        return charts

    def generate_all_oxygenation_charts(
        self, oxygenation_df: pd.DataFrame
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Generate all oxygenation-related charts.

        Args:
            oxygenation_df: DataFrame with muscle oxygenation data

        Returns:
            Tuple of (charts dict, oxygenation metrics dict)
        """
        charts = {}
        
        # Check if it's TSI format or Train.Red format
        if "TSI" in oxygenation_df.columns:
            charts["tsi"] = self.generate_tsi_chart(oxygenation_df)
            metrics = {}
        else:
            chart_path, metrics = self.generate_muscle_oxygenation_chart(oxygenation_df)
            charts["muscle_oxygenation"] = chart_path
        
        return charts, metrics
