"""
Metrics Calculator Service

Calculates all fundamental metrics from raw data files.
Stores results in database - only calculates values that can't be derived.

This service is responsible for:
1. Preprocessing Pnoe data (smoothing, derived columns)
2. Calculating spirometry metrics from extracted CSV
3. Calculating VO2 and cardiovascular metrics
4. Calculating VT1/VT2 thresholds and heart rate zones
5. Calculating RMR, TDEE, and nutrition metrics
6. Calculating recovery metrics
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class MetricsCalculator:
    """Calculate all fundamental metrics from raw data."""

    # NEAT/Activity Multipliers for TDEE calculation
    NEAT_MULTIPLIERS = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.7,
        "extreme": 1.9,
    }

    # Daily Calorie Deficit required for a specific Weekly Weight Loss (lbs)
    CALORIE_DEFICIT_MAP_LBS = {
        0.0: 0,
        0.2: 85,
        0.4: 169,
        0.6: 254,
        0.8: 339,
        1.1: 423,
        1.3: 508,
        1.5: 593,
        1.7: 677,
        1.9: 762,
        2.2: 847,
        2.4: 931,
        2.6: 1016,
    }

    # Protein Requirements (g/kg LBM) based on Age and Deficit Status
    PROTEIN_REQUIREMENTS = {
        "0-30": {"no_deficit": (1.8, 2.0), "deficit": (2.2, 2.4)},
        "30-40": {"no_deficit": (2.0, 2.3), "deficit": (2.4, 2.8)},
        "40-50": {"no_deficit": (2.3, 2.6), "deficit": (2.8, 3.1)},
        "50-60": {"no_deficit": (2.6, 2.9), "deficit": (3.1, 3.5)},
        "60-70": {"no_deficit": (2.9, 3.2), "deficit": (3.5, 3.8)},
    }

    # VO2 Max reference data by age and gender
    VO2_MAX_DATA = {
        "20-29 (M)": {
            "Very Poor": (29.0, 38.1), "Poor": (38.1, 44.9), "Fair": (44.9, 50.2),
            "Good": (50.2, 61.8), "Excellent": (57.1, 66.3), "Superior": (66.3, None),
        },
        "30-39 (M)": {
            "Very Poor": (27.2, 34.1), "Poor": (34.1, 39.6), "Fair": (39.6, 45.2),
            "Good": (45.2, 51.6), "Excellent": (51.6, 59.8), "Superior": (59.8, None),
        },
        "40-49 (M)": {
            "Very Poor": (24.2, 30.5), "Poor": (30.5, 35.7), "Fair": (35.7, 40.3),
            "Good": (40.3, 46.7), "Excellent": (46.7, 55.6), "Superior": (55.6, None),
        },
        "50-59 (M)": {
            "Very Poor": (20.9, 26.1), "Poor": (26.1, 30.7), "Fair": (30.7, 35.1),
            "Good": (35.1, 41.2), "Excellent": (41.2, 50.7), "Superior": (50.7, None),
        },
        "60-69 (M)": {
            "Very Poor": (17.4, 22.4), "Poor": (22.4, 26.6), "Fair": (26.6, 30.5),
            "Good": (30.5, 36.1), "Excellent": (36.1, 43.0), "Superior": (43.0, None),
        },
        "20-29 (F)": {
            "Very Poor": (21.7, 28.6), "Poor": (28.6, 34.6), "Fair": (34.6, 40.6),
            "Good": (40.6, 46.5), "Excellent": (46.5, 56.0), "Superior": (56.0, None),
        },
        "30-39 (F)": {
            "Very Poor": (19.0, 24.1), "Poor": (24.1, 28.2), "Fair": (28.2, 32.2),
            "Good": (32.2, 35.7), "Excellent": (35.7, 45.8), "Superior": (45.8, None),
        },
        "40-49 (F)": {
            "Very Poor": (17.0, 21.3), "Poor": (21.3, 24.9), "Fair": (24.9, 28.7),
            "Good": (28.7, 34.0), "Excellent": (34.0, 41.7), "Superior": (41.7, None),
        },
        "50-59 (F)": {
            "Very Poor": (16.0, 19.1), "Poor": (19.1, 24.4), "Fair": (21.8, 27.6),
            "Good": (25.2, 28.6), "Excellent": (28.6, 35.9), "Superior": (35.9, None),
        },
        "60-69 (F)": {
            "Very Poor": (13.4, 16.5), "Poor": (16.5, 18.9), "Fair": (18.9, 21.2),
            "Good": (21.2, 24.6), "Excellent": (24.6, 29.4), "Superior": (29.4, None),
        },
    }

    # RHR reference data by age and gender
    RHR_DATA = {
        "male": {
            "18-25": {"Poor": (85, None), "Below Average": (79, 85), "Average": (74, 79),
                      "Above Average": (70, 74), "Good": (66, 70), "Excellent": (61, 66), "Athlete": (40, 61)},
            "26-35": {"Poor": (83, None), "Below Average": (77, 83), "Average": (73, 77),
                      "Above Average": (69, 73), "Good": (65, 69), "Excellent": (60, 65), "Athlete": (42, 60)},
            "36-45": {"Poor": (85, None), "Below Average": (79, 85), "Average": (74, 79),
                      "Above Average": (70, 74), "Good": (65, 70), "Excellent": (60, 65), "Athlete": (45, 60)},
            "46-55": {"Poor": (84, None), "Below Average": (78, 84), "Average": (74, 78),
                      "Above Average": (70, 74), "Good": (66, 70), "Excellent": (61, 66), "Athlete": (48, 61)},
            "56-65": {"Poor": (84, None), "Below Average": (78, 84), "Average": (74, 78),
                      "Above Average": (70, 74), "Good": (65, 70), "Excellent": (60, 65), "Athlete": (50, 60)},
            "65+": {"Poor": (84, None), "Below Average": (77, 84), "Average": (73, 77),
                    "Above Average": (70, 73), "Good": (65, 70), "Excellent": (60, 65), "Athlete": (52, 60)},
        },
        "female": {
            "18-25": {"Poor": (82, None), "Below Average": (74, 82), "Average": (70, 74),
                      "Above Average": (66, 70), "Good": (62, 66), "Excellent": (56, 62), "Athlete": (40, 56)},
            "26-35": {"Poor": (82, None), "Below Average": (75, 82), "Average": (71, 75),
                      "Above Average": (66, 71), "Good": (62, 66), "Excellent": (55, 62), "Athlete": (44, 55)},
            "36-45": {"Poor": (83, None), "Below Average": (76, 83), "Average": (71, 76),
                      "Above Average": (67, 71), "Good": (63, 67), "Excellent": (57, 63), "Athlete": (47, 57)},
            "46-55": {"Poor": (84, None), "Below Average": (77, 84), "Average": (72, 77),
                      "Above Average": (68, 72), "Good": (64, 68), "Excellent": (58, 64), "Athlete": (49, 58)},
            "56-65": {"Poor": (82, None), "Below Average": (76, 82), "Average": (72, 76),
                      "Above Average": (68, 72), "Good": (62, 68), "Excellent": (57, 62), "Athlete": (51, 57)},
            "65+": {"Poor": (80, None), "Below Average": (74, 80), "Average": (70, 74),
                    "Above Average": (66, 70), "Good": (62, 66), "Excellent": (56, 62), "Athlete": (52, 56)},
        },
    }

    def __init__(self):
        """Initialize the metrics calculator."""
        self.pnoe_df: Optional[pd.DataFrame] = None
        self.spirometry_df: Optional[pd.DataFrame] = None
        self.oxygenation_df: Optional[pd.DataFrame] = None

    # ==================== Data Loading & Preprocessing ====================

    def load_pnoe_data(self, pnoe_path: str) -> pd.DataFrame:
        """
        Load and preprocess Pnoe CSV data.

        Args:
            pnoe_path: Path to the Pnoe CSV file

        Returns:
            Preprocessed DataFrame
        """
        self.pnoe_df = pd.read_csv(pnoe_path, delimiter=";")
        self._preprocess_pnoe_data()
        return self.pnoe_df

    def load_spirometry_data(self, spirometry_path: str) -> pd.DataFrame:
        """
        Load spirometry CSV data.

        Args:
            spirometry_path: Path to the extracted spirometry CSV

        Returns:
            DataFrame with spirometry data
        """
        self.spirometry_df = pd.read_csv(spirometry_path)
        return self.spirometry_df

    def load_oxygenation_data(self, oxygenation_path: str, skiprows: int = 445) -> pd.DataFrame:
        """
        Load muscle oxygenation CSV data.

        Args:
            oxygenation_path: Path to the oxygenation CSV
            skiprows: Number of rows to skip (for Train.Red format)

        Returns:
            DataFrame with oxygenation data
        """
        self.oxygenation_df = pd.read_csv(oxygenation_path, skiprows=skiprows)
        return self.oxygenation_df

    def _preprocess_pnoe_data(self) -> None:
        """Apply preprocessing steps to Pnoe data (smoothing, derived columns)."""
        # Convert numeric columns
        for col in self.pnoe_df.columns:
            try:
                self.pnoe_df[col] = pd.to_numeric(self.pnoe_df[col])
            except (ValueError, TypeError):
                pass

        # Derived columns
        self.pnoe_df["VO2 Pulse"] = self.pnoe_df["VO2(ml/min)"] / self.pnoe_df["HR(bpm)"]
        self.pnoe_df["VO2 Breath"] = self.pnoe_df["VO2(ml/min)"] / self.pnoe_df["BF(bpm)"]
        self.pnoe_df["CHO"] = self.pnoe_df["EE(kcal/min)"] * self.pnoe_df["CARBS(%)"] / 100
        self.pnoe_df["FAT"] = self.pnoe_df["EE(kcal/min)"] * self.pnoe_df["FAT(%)"] / 100

        # Smoothing
        window_size = 10
        columns_to_smooth = [
            "VO2(ml/min)", "VCO2(ml/min)", "HR(bpm)", "VT(l)", "BF(bpm)",
            "VE(l/min)", "VO2 Pulse", "VO2 Breath", "CHO", "FAT",
        ]

        for col in columns_to_smooth:
            if col in self.pnoe_df.columns:
                self.pnoe_df[f"{col}_smoothed"] = (
                    self.pnoe_df[col].rolling(window=window_size, min_periods=5).mean()
                )

    # ==================== Spirometry Metrics ====================

    def calculate_spirometry_metrics(self) -> Dict[str, Any]:
        """
        Calculate spirometry metrics from extracted CSV.

        Returns:
            Dictionary with FVC, FEV1, FEV1/FVC values and lung capacity assessment
        """
        if self.spirometry_df is None:
            return {}

        metrics = {}
        param_mapping = {
            "FVC": "fvc",
            "FEV1": "fev1",
            "FEV1/FVC%": "fev1_fvc",
        }

        for param, key in param_mapping.items():
            row = self.spirometry_df.loc[self.spirometry_df["Parameters"].str.strip() == param]
            if row.empty:
                row = self.spirometry_df.loc[
                    self.spirometry_df["Parameters"].str.strip().str.upper() == param.upper()
                ]
            if row.empty and "%" in param:
                param_no_pct = param.replace("%", "")
                row = self.spirometry_df.loc[
                    self.spirometry_df["Parameters"].str.strip() == param_no_pct
                ]

            if not row.empty:
                row_data = row.iloc[0]
                if pd.notna(row_data.get("Best")):
                    try:
                        metrics[f"{key}_best"] = float(row_data["Best"])
                    except (ValueError, TypeError):
                        pass
                if pd.notna(row_data.get("Pred.")) or pd.notna(row_data.get("Pred")):
                    try:
                        pred_col = "Pred." if "Pred." in row_data else "Pred"
                        metrics[f"{key}_predicted"] = float(row_data[pred_col])
                    except (ValueError, TypeError):
                        pass
                if pd.notna(row_data.get("%Pred.")) or pd.notna(row_data.get("%Pred")):
                    try:
                        pct_col = "%Pred." if "%Pred." in row_data else "%Pred"
                        metrics[f"{key}_percent"] = float(row_data[pct_col])
                    except (ValueError, TypeError):
                        pass

        # Determine lung capacity assessment
        fev1_fvc = metrics.get("fev1_fvc_best", 0)
        if fev1_fvc >= 70:
            metrics["lung_capacity"] = "normal"
        elif fev1_fvc >= 60:
            metrics["lung_capacity"] = "mild"
        elif fev1_fvc >= 50:
            metrics["lung_capacity"] = "moderate"
        else:
            metrics["lung_capacity"] = "severe"

        return metrics

    # ==================== VO2 and Cardiovascular Metrics ====================

    def calculate_vo2_metrics(self, weight_kg: float) -> Dict[str, Any]:
        """
        Calculate VO2 max and related cardiovascular metrics.

        Args:
            weight_kg: Patient weight in kg

        Returns:
            Dictionary with VO2 max, peak VT, fat max, and related metrics
        """
        if self.pnoe_df is None:
            return {}

        metrics = {}

        # VO2 Max
        metrics["vo2_max"] = float(self.pnoe_df["VO2(ml/min)_smoothed"].max())
        metrics["vo2_max_per_kg"] = metrics["vo2_max"] / weight_kg

        # Peak Heart Rate
        metrics["peak_hr"] = int(self.pnoe_df["HR(bpm)_smoothed"].max())

        # Peak VT
        peak_vt_idx = self.pnoe_df["VT(l)_smoothed"].idxmax()
        peak_vt_row = self.pnoe_df.loc[peak_vt_idx]
        metrics["peak_vt"] = float(peak_vt_row["VT(l)_smoothed"])
        metrics["peak_vt_hr"] = int(peak_vt_row["HR(bpm)_smoothed"])

        # Fat Max
        fat_max_idx = self.pnoe_df["FAT_smoothed"].idxmax()
        fat_max_row = self.pnoe_df.loc[fat_max_idx]
        metrics["fat_max_value"] = float(fat_max_row["FAT_smoothed"])
        metrics["fat_max_hr"] = int(fat_max_row["HR(bpm)_smoothed"])
        metrics["fat_max_vo2"] = float(fat_max_row["VO2(ml/min)_smoothed"])
        metrics["fat_max_speed"] = float(fat_max_row.get("Speed", 0))

        return metrics

    # ==================== VT1/VT2 Thresholds ====================

    def calculate_thresholds(self) -> Dict[str, Any]:
        """
        Detect VT1 and VT2 thresholds from Pnoe data.

        VT1: First crossover where CHO > FAT and remains higher
        VT2: Maximum second derivative of VE slope

        Returns:
            Dictionary with VT1 and VT2 HR, VO2, speed values
        """
        if self.pnoe_df is None:
            return {}

        metrics = {}

        # VT1: CHO/FAT crossover
        condition = self.pnoe_df["CHO_smoothed"] > self.pnoe_df["FAT_smoothed"]
        crossover_indices = condition[condition].index

        if len(crossover_indices) > 0:
            for idx in crossover_indices:
                remaining = self.pnoe_df.loc[idx:]
                if all(remaining["CHO_smoothed"] > remaining["FAT_smoothed"]):
                    vt1_row = self.pnoe_df.loc[idx]
                    metrics["vt1_hr"] = int(vt1_row["HR(bpm)_smoothed"])
                    metrics["vt1_vo2"] = float(vt1_row["VO2(ml/min)_smoothed"])
                    metrics["vt1_speed"] = float(vt1_row.get("Speed", 0))
                    break

        # VT2: VE slope inflection
        ve_slope = self.pnoe_df["VE(l/min)_smoothed"].diff()
        second_derivative = ve_slope.diff()
        vt2_idx = second_derivative.idxmax()

        if pd.notna(vt2_idx):
            vt2_row = self.pnoe_df.loc[vt2_idx]
            metrics["vt2_hr"] = int(vt2_row["HR(bpm)_smoothed"])
            metrics["vt2_vo2"] = float(vt2_row["VO2(ml/min)_smoothed"])
            metrics["vt2_speed"] = float(vt2_row.get("Speed", 0))

        # Crossover (same as VT1)
        metrics["crossover_hr"] = metrics.get("vt1_hr")
        metrics["crossover_speed"] = metrics.get("vt1_speed")

        return metrics

    # ==================== Optimal Fat Burning Zone ====================

    def find_optimal_fat_burning_zone(self) -> Dict[str, Any]:
        """
        Find the optimal fat burning zone - the point with the highest fat:carb ratio.

        Returns:
            Dictionary containing optimal fat burning zone data:
            - HeartRate: HR at optimal fat burning
            - Speed: Speed at optimal fat burning
            - Time: Time at optimal fat burning
            - FatBurnRate: Fat burn rate at this point
            - CarbBurnRate: Carb burn rate at this point
            - FatCarbRatio: Ratio of fat to carb burning
            - Index: DataFrame index
        """
        if self.pnoe_df is None:
            return {}

        # Calculate fat:carb ratio (add small value to avoid division by zero)
        df_copy = self.pnoe_df.copy()
        df_copy["fat_carb_ratio"] = df_copy["FAT_smoothed"] / (df_copy["CHO_smoothed"] + 1e-8)

        # Find index of maximum ratio
        optimal_idx = df_copy["fat_carb_ratio"].idxmax()
        optimal_row = df_copy.loc[optimal_idx]

        return {
            "HeartRate": int(optimal_row["HR(bpm)_smoothed"]),
            "Speed": float(optimal_row.get("Speed", 0)),
            "Time": float(optimal_row.get("T(sec)", 0)),
            "FatBurnRate": float(optimal_row["FAT_smoothed"]),
            "CarbBurnRate": float(optimal_row["CHO_smoothed"]),
            "FatCarbRatio": float(optimal_row["fat_carb_ratio"]),
            "Index": optimal_idx,
        }

    # ==================== Heart Rate Zones ====================

    def calculate_hr_zones(
        self,
        vt1_hr: Optional[int] = None,
        vt2_hr: Optional[int] = None,
        age: int = 30,
        zone_mode: str = "vt_based",
        manual_zones: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """
        Calculate heart rate zones based on VT1/VT2 or manual entry.

        Args:
            vt1_hr: VT1 heart rate (for VT-based calculation)
            vt2_hr: VT2 heart rate (for VT-based calculation)
            age: Patient age (for fallback calculation)
            zone_mode: 'vt_based' or 'manual'
            manual_zones: Dict with zone1_start, zone2_start, etc. (for manual mode)

        Returns:
            Dictionary with zone boundaries (zone1_start, zone1_end, etc.)
        """
        if zone_mode == "manual" and manual_zones:
            return {
                "zone1_start": manual_zones.get("zone1_start", 100),
                "zone1_end": manual_zones.get("zone2_start", 115),
                "zone2_start": manual_zones.get("zone2_start", 115),
                "zone2_end": manual_zones.get("zone3_start", 130),
                "zone3_start": manual_zones.get("zone3_start", 130),
                "zone3_end": manual_zones.get("zone4_start", 150),
                "zone4_start": manual_zones.get("zone4_start", 150),
                "zone4_end": manual_zones.get("zone5_start", 165),
                "zone5_start": manual_zones.get("zone5_start", 165),
                "zone5_end": manual_zones.get("zone5_end", 180),
            }

        if vt1_hr and vt2_hr and self.pnoe_df is not None:
            # Calculate optimal fat burning zone
            self.pnoe_df["fat_carb_ratio"] = self.pnoe_df["FAT_smoothed"] / (
                self.pnoe_df["CHO_smoothed"] + 0.00000001
            )
            optimal_fat_idx = self.pnoe_df["fat_carb_ratio"].idxmax()
            optimal_row = self.pnoe_df.loc[optimal_fat_idx]
            optimal_hr = int(optimal_row["HR(bpm)_smoothed"])

            zone1_start = math.floor(optimal_hr - 15)
            zone2_start = math.floor(optimal_hr)
            zone3_start = math.floor(vt1_hr)
            zone4_start = math.floor(vt2_hr - 10)
            zone5_start = math.floor(vt2_hr)
            zone5_end = math.floor(vt2_hr + 10)

            return {
                "zone1_start": zone1_start,
                "zone1_end": zone2_start,
                "zone2_start": zone2_start,
                "zone2_end": zone3_start,
                "zone3_start": zone3_start,
                "zone3_end": zone4_start,
                "zone4_start": zone4_start,
                "zone4_end": zone5_start,
                "zone5_start": zone5_start,
                "zone5_end": zone5_end,
            }

        # Fallback: age-based calculation
        max_hr = 220 - age
        return {
            "zone1_start": int(max_hr * 0.55),
            "zone1_end": int(max_hr * 0.65),
            "zone2_start": int(max_hr * 0.65),
            "zone2_end": int(max_hr * 0.75),
            "zone3_start": int(max_hr * 0.75),
            "zone3_end": int(max_hr * 0.85),
            "zone4_start": int(max_hr * 0.85),
            "zone4_end": int(max_hr * 0.95),
            "zone5_start": int(max_hr * 0.95),
            "zone5_end": int(max_hr * 1.05),
        }

    # ==================== VO2 Drop Points ====================

    def calculate_vo2_drop_points(self, zone_boundaries: Dict[str, int]) -> Dict[str, Any]:
        """
        Calculate VO2 Pulse and VO2 Breath efficiency drop points.

        Args:
            zone_boundaries: Dictionary with zone start/end values

        Returns:
            Dictionary with drop BPM, zone, and whether drop occurs
        """
        if self.pnoe_df is None:
            return {}

        metrics = {}
        window = max(1, len(self.pnoe_df) // 3)

        # VO2 Pulse drop
        vo2_pulse_slope = self.pnoe_df["VO2 Pulse_smoothed"].diff()
        vo2_pulse_slope_smoothed = vo2_pulse_slope.rolling(window=window, min_periods=5).mean()
        mask_pulse = vo2_pulse_slope_smoothed <= 0
        drop_indices_pulse = mask_pulse[mask_pulse].index

        if len(drop_indices_pulse) > 0:
            drop_idx = drop_indices_pulse[0]
            drop_row = self.pnoe_df.loc[drop_idx]
            metrics["vo2_pulse_drop_bpm"] = int(drop_row["HR(bpm)_smoothed"])
            metrics["vo2_pulse_drops"] = True
        else:
            metrics["vo2_pulse_drop_bpm"] = None
            metrics["vo2_pulse_drops"] = False

        # VO2 Breath drop
        vo2_breath_slope = self.pnoe_df["VO2 Breath_smoothed"].diff()
        vo2_breath_slope_smoothed = vo2_breath_slope.rolling(window=window, min_periods=5).mean()
        mask_breath = vo2_breath_slope_smoothed <= 0
        drop_indices_breath = mask_breath[mask_breath].index

        if len(drop_indices_breath) > 0:
            drop_idx = drop_indices_breath[0]
            drop_row = self.pnoe_df.loc[drop_idx]
            metrics["vo2_breath_drop_bpm"] = int(drop_row["HR(bpm)_smoothed"])
            metrics["vo2_breath_drops"] = True
        else:
            metrics["vo2_breath_drop_bpm"] = None
            metrics["vo2_breath_drops"] = False

        return metrics

    # ==================== Recovery Metrics ====================

    def calculate_recovery_metrics(self) -> Dict[str, float]:
        """
        Calculate cardiac, metabolic, and breath recovery percentages.

        Returns:
            Dictionary with recovery percentages
        """
        if self.pnoe_df is None:
            return {}

        # Find peak HR and time
        peak_hr = self.pnoe_df["HR(bpm)_smoothed"].max()
        peak_time = self.pnoe_df[self.pnoe_df["HR(bpm)_smoothed"] == peak_hr]["T(sec)"].max()

        # Cardiac recovery (1 minute)
        T_target_60s = peak_time + 60
        idx_60s = np.argmin(np.abs(self.pnoe_df["T(sec)"] - T_target_60s))
        hr_60s = self.pnoe_df.iloc[idx_60s]["HR(bpm)"]
        hrr_60s = peak_hr - hr_60s
        cardiac_recovery_pct = (hrr_60s / peak_hr * 100) if peak_hr > 0 else 33

        # Metabolic recovery (2 minutes) - using VCO2
        peak_vco2_idx = self.pnoe_df["VCO2(ml/min)_smoothed"].idxmax()
        peak_vco2 = self.pnoe_df.loc[peak_vco2_idx, "VCO2(ml/min)_smoothed"]
        T_target_120s = peak_time + 120
        idx_120s = np.argmin(np.abs(self.pnoe_df["T(sec)"] - T_target_120s))
        vco2_120s = self.pnoe_df.iloc[idx_120s]["VCO2(ml/min)"]
        metabolic_recovery_pct = ((peak_vco2 - vco2_120s) / peak_vco2 * 100) if peak_vco2 > 0 else 65

        # Breath frequency recovery (2.5 minutes)
        peak_bf = self.pnoe_df["BF(bpm)"].min()
        T_target_150s = peak_time + 150
        idx_150s = np.argmin(np.abs(self.pnoe_df["T(sec)"] - T_target_150s))
        bf_150s = self.pnoe_df.iloc[idx_150s]["BF(bpm)"]
        breath_recovery_pct = ((bf_150s - peak_bf) / peak_bf * 100) if peak_bf > 0 else 76

        return {
            "cardiac_recovery_pct": float(np.round(cardiac_recovery_pct)),
            "metabolic_recovery_pct": float(np.round(metabolic_recovery_pct)),
            "breath_recovery_pct": float(np.round(breath_recovery_pct)),
        }

    # ==================== Resting Heart Rate ====================

    def calculate_resting_hr(self) -> Dict[str, Any]:
        """
        Calculate resting heart rate from recovery data.

        Returns:
            Dictionary with resting HR value
        """
        if self.pnoe_df is None:
            return {}

        peak_hr = self.pnoe_df["HR(bpm)_smoothed"].max()
        peak_time = self.pnoe_df[self.pnoe_df["HR(bpm)_smoothed"] == peak_hr]["T(sec)"].max()

        T_target_60s = peak_time + 60
        idx_60s = np.argmin(np.abs(self.pnoe_df["T(sec)"] - T_target_60s))
        hr_60s = self.pnoe_df.iloc[idx_60s]["HR(bpm)"]
        resting_hr = int(peak_hr - hr_60s)

        return {"resting_hr": resting_hr}

    # ==================== RMR and Fuel Source ====================

    def calculate_rmr_and_fuel_source(
        self,
        rmr_time_start: Optional[float] = None,
        rmr_time_end: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate RMR and fuel source from Pnoe data.

        Args:
            rmr_time_start: Start time for RMR calculation window (seconds)
            rmr_time_end: End time for RMR calculation window (seconds)

        Returns:
            Dictionary with RMR and fuel source metrics
        """
        if self.pnoe_df is None:
            return {}

        metrics = {}

        # Filter by time window if specified
        if rmr_time_start is not None and rmr_time_end is not None:
            time_mask = (self.pnoe_df["T(sec)"] >= rmr_time_start) & (
                self.pnoe_df["T(sec)"] <= rmr_time_end
            )
            rest_phase = self.pnoe_df[time_mask]
        elif "MET" in self.pnoe_df.columns and "EE(kcal/day)" in self.pnoe_df.columns:
            rest_phase = self.pnoe_df[self.pnoe_df["MET"] <= 1.1]
        else:
            rest_phase = self.pnoe_df.head(30)  # Use first 30 rows as fallback

        # Calculate RMR
        if not rest_phase.empty and "EE(kcal/day)" in rest_phase.columns:
            metrics["rmr_kcal"] = float(rest_phase["EE(kcal/day)"].mean())
        elif "EE(kcal/min)" in self.pnoe_df.columns:
            min_ee = self.pnoe_df["EE(kcal/min)"].min()
            metrics["rmr_kcal"] = float(min_ee * 1440)
        else:
            metrics["rmr_kcal"] = 1500.0

        # Calculate fuel source
        if "FAT(%)" in self.pnoe_df.columns:
            if not rest_phase.empty:
                if "RER" in rest_phase.columns:
                    rest_phase = rest_phase.copy()
                    rest_phase["RER_diff"] = abs(rest_phase["RER"] - 0.9)
                    closest_idx = rest_phase["RER_diff"].idxmin()
                    metrics["rest_fat_percentage"] = float(rest_phase.loc[closest_idx, "FAT(%)"])
                else:
                    metrics["rest_fat_percentage"] = float(rest_phase["FAT(%)"].mean())
            else:
                metrics["rest_fat_percentage"] = float(self.pnoe_df["FAT(%)"].mean())
        else:
            metrics["rest_fat_percentage"] = 75.0

        metrics["rest_carb_percentage"] = 100.0 - metrics["rest_fat_percentage"]

        return metrics

    # ==================== TDEE and Calorie Targets ====================

    def calculate_tdee_and_targets(
        self,
        rmr_kcal: float,
        activity_level: str,
        weekly_weight_loss_lbs: float,
    ) -> Dict[str, Any]:
        """
        Calculate TDEE, calorie deficit, and target calories.

        Args:
            rmr_kcal: Resting metabolic rate in kcal/day
            activity_level: Activity level ('sedentary', 'light', 'moderate', 'active', 'extreme')
            weekly_weight_loss_lbs: Target weekly weight loss in pounds

        Returns:
            Dictionary with TDEE, deficit, and target metrics
        """
        activity_level_lower = activity_level.lower() if activity_level else "sedentary"
        if activity_level_lower not in self.NEAT_MULTIPLIERS:
            activity_level_lower = "sedentary"

        neat_multiplier = self.NEAT_MULTIPLIERS[activity_level_lower]
        tdee = rmr_kcal * neat_multiplier
        neat_calories = tdee - rmr_kcal

        weekly_loss = round(float(weekly_weight_loss_lbs), 1) if weekly_weight_loss_lbs else 0.0
        if weekly_loss in self.CALORIE_DEFICIT_MAP_LBS:
            weight_loss_calories = self.CALORIE_DEFICIT_MAP_LBS[weekly_loss]
        else:
            closest_key = min(self.CALORIE_DEFICIT_MAP_LBS.keys(), key=lambda x: abs(x - weekly_loss))
            weight_loss_calories = self.CALORIE_DEFICIT_MAP_LBS[closest_key]
            weekly_loss = closest_key

        target_calories = tdee - weight_loss_calories

        return {
            "tdee": float(tdee),
            "neat_calories": float(neat_calories),
            "calorie_deficit": float(weight_loss_calories),
            "target_calories": float(target_calories),
        }

    # ==================== Nutrition Metrics ====================

    def calculate_nutrition_metrics(
        self,
        weight_kg: float,
        fat_percentage: float,
        age: int,
        target_calories: float,
        calorie_deficit: float,
    ) -> Dict[str, Any]:
        """
        Calculate protein and macro targets.

        Args:
            weight_kg: Weight in kg
            fat_percentage: Body fat percentage
            age: Patient age
            target_calories: Daily calorie target
            calorie_deficit: Daily calorie deficit

        Returns:
            Dictionary with protein and macro values
        """
        # Calculate lean body mass
        lbm_kg = weight_kg * (1 - fat_percentage / 100)
        has_deficit = calorie_deficit > 0

        # Get protein factor
        protein_factor = self._get_protein_factor(age, has_deficit)
        protein_g = int(lbm_kg * protein_factor)

        # Calculate macros maintaining ratio
        macros = self._calculate_macros(target_calories, protein_g)

        # Calculate weekday/weekend split
        weekday_calories = int(target_calories * 0.9)
        weekend_calories = int(target_calories * 1.25)
        weekday_macros = self._calculate_macros(weekday_calories, protein_g)
        weekend_macros = self._calculate_macros(weekend_calories, protein_g)

        # Store original ratios for recalculation
        non_protein_cals = target_calories - (protein_g * 4)
        if non_protein_cals > 0:
            carbs_cals = macros["carbs"] * 4
            fat_cals = macros["fat"] * 9
            total_non_protein = carbs_cals + fat_cals
            original_carbs_ratio = carbs_cals / total_non_protein if total_non_protein > 0 else 0.5
            original_fat_ratio = fat_cals / total_non_protein if total_non_protein > 0 else 0.5
        else:
            original_carbs_ratio = 0.5
            original_fat_ratio = 0.5

        return {
            "protein_g": float(protein_g),
            "carbs_g": float(macros["carbs"]),
            "fat_g": float(macros["fat"]),
            "fibre_g": float(macros["fibre"]),
            "original_carbs_ratio": original_carbs_ratio,
            "original_fat_ratio": original_fat_ratio,
            "weekday_protein_g": float(protein_g),
            "weekday_carbs_g": float(weekday_macros["carbs"]),
            "weekday_fat_g": float(weekday_macros["fat"]),
            "weekday_fibre_g": float(weekday_macros["fibre"]),
            "weekday_calories": float(weekday_calories),
            "weekend_protein_g": float(protein_g),
            "weekend_carbs_g": float(weekend_macros["carbs"]),
            "weekend_fat_g": float(weekend_macros["fat"]),
            "weekend_fibre_g": float(weekend_macros["fibre"]),
            "weekend_calories": float(weekend_calories),
        }

    def _get_protein_factor(self, age: int, has_deficit: bool) -> float:
        """Get protein factor (g/kg LBM) based on age and deficit status."""
        if 0 <= age <= 30:
            age_key = "0-30"
        elif 30 < age <= 40:
            age_key = "30-40"
        elif 40 < age <= 50:
            age_key = "40-50"
        elif 50 < age <= 60:
            age_key = "50-60"
        else:
            age_key = "60-70"

        deficit_status = "deficit" if has_deficit else "no_deficit"
        min_factor, max_factor = self.PROTEIN_REQUIREMENTS[age_key][deficit_status]
        return (min_factor + max_factor) / 2

    def _calculate_macros(self, total_calories: float, protein_grams: float) -> Dict[str, int]:
        """Calculate carbs, fat, and fibre from total calories and protein."""
        protein_calories = protein_grams * 4
        carbs = (total_calories - protein_calories) / 8
        fat = (total_calories - protein_calories) / 18
        fibre = (total_calories * 15) / 1000
        return {"carbs": int(carbs), "fat": int(fat), "fibre": int(fibre)}

    def recalculate_macros_from_protein(
        self,
        new_protein_g: float,
        original_carbs_g: float,
        original_fat_g: float,
        total_calories: float,
    ) -> Dict[str, float]:
        """
        Recalculate carbs and fat when protein changes, maintaining original CHO/FAT ratio.

        Args:
            new_protein_g: New protein value in grams
            original_carbs_g: Original carbs value for ratio calculation
            original_fat_g: Original fat value for ratio calculation
            total_calories: Total daily calorie target

        Returns:
            Dictionary with new carbs and fat values
        """
        # Calculate remaining calories after protein
        protein_calories = new_protein_g * 4
        remaining_calories = total_calories - protein_calories

        if remaining_calories <= 0:
            return {"carbs_g": 0.0, "fat_g": 0.0}

        # Calculate original ratio
        original_carbs_cals = original_carbs_g * 4
        original_fat_cals = original_fat_g * 9
        original_total = original_carbs_cals + original_fat_cals

        if original_total > 0:
            carbs_ratio = original_carbs_cals / original_total
            fat_ratio = original_fat_cals / original_total
        else:
            carbs_ratio = 0.5
            fat_ratio = 0.5

        # Apply ratio to remaining calories
        new_carbs_cals = remaining_calories * carbs_ratio
        new_fat_cals = remaining_calories * fat_ratio

        return {
            "carbs_g": new_carbs_cals / 4,
            "fat_g": new_fat_cals / 9,
        }

    # ==================== Category Determination ====================

    def determine_vo2_max_category(self, vo2_max_per_kg: float, age: int, gender: str) -> str:
        """Determine VO2 max category based on value, age, and gender."""
        age_key = self._get_age_key_vo2(age)
        gender_key = "(M)" if gender.lower() == "male" else "(F)"
        key = f"{age_key} {gender_key}"

        ranges = self.VO2_MAX_DATA.get(key, self.VO2_MAX_DATA["30-39 (F)"])

        # Check Superior first (open-ended)
        min_val, max_val = ranges["Superior"]
        if max_val is None and vo2_max_per_kg >= min_val:
            return "Superior"

        for category in ["Excellent", "Good", "Fair", "Poor", "Very Poor"]:
            min_val, max_val = ranges[category]
            if min_val <= vo2_max_per_kg < max_val:
                return category

        return "Very Poor"

    def _get_age_key_vo2(self, age: int) -> str:
        """Get age key for VO2 max lookup."""
        if 20 <= age <= 29:
            return "20-29"
        elif 30 <= age <= 39:
            return "30-39"
        elif 40 <= age <= 49:
            return "40-49"
        elif 50 <= age <= 59:
            return "50-59"
        elif 60 <= age <= 69:
            return "60-69"
        elif age < 20:
            return "20-29"
        else:
            return "60-69"

    def determine_rhr_category(self, rhr: float, age: int, gender: str) -> str:
        """Determine resting heart rate category based on value, age, and gender."""
        age_key = self._get_age_key_rhr(age)
        gender_key = "male" if gender.lower().startswith("m") else "female"

        ranges = self.RHR_DATA[gender_key][age_key]

        # Check Poor first (open-ended at top)
        min_val, max_val = ranges["Poor"]
        if max_val is None and rhr >= min_val:
            return "Poor"

        for category in ["Below Average", "Average", "Above Average", "Good", "Excellent", "Athlete"]:
            min_val, max_val = ranges[category]
            if min_val <= rhr < max_val:
                return category

        return "Athlete"

    def _get_age_key_rhr(self, age: int) -> str:
        """Get age key for RHR lookup."""
        if 18 <= age <= 25:
            return "18-25"
        elif 26 <= age <= 35:
            return "26-35"
        elif 36 <= age <= 45:
            return "36-45"
        elif 46 <= age <= 55:
            return "46-55"
        elif 56 <= age <= 65:
            return "56-65"
        else:
            return "65+"

    # ==================== Body Composition ====================

    def calculate_body_composition(self, weight_kg: float, fat_percentage: float) -> Dict[str, float]:
        """
        Calculate body composition metrics.

        Args:
            weight_kg: Weight in kg
            fat_percentage: Body fat percentage

        Returns:
            Dictionary with fat mass and lean mass in both kg and lbs
        """
        fat_mass_kg = weight_kg * fat_percentage / 100
        lean_mass_kg = weight_kg - fat_mass_kg

        return {
            "fat_mass_kg": fat_mass_kg,
            "lean_mass_kg": lean_mass_kg,
            "fat_mass_lbs": fat_mass_kg * 2.20462,
            "lean_mass_lbs": lean_mass_kg * 2.20462,
        }

    # ==================== Zone Analysis ====================

    def calculate_zone_analysis(self, zone_boundaries: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Calculate detailed metrics for each heart rate zone.

        Args:
            zone_boundaries: Dictionary with zone start/end values

        Returns:
            List of dictionaries with zone-by-zone analysis
        """
        if self.pnoe_df is None:
            return []

        def speed_to_pace(s_mph: float) -> Tuple[int, int]:
            if s_mph <= 0:
                return 0, 0
            s_kmh = s_mph * 1.60934
            p_min = 60 / s_kmh
            p_m = int(p_min)
            p_s = int((p_min % 1) * 60)
            return p_m, p_s

        zones = []
        ideal_breath_ranges = [
            "15-20 breaths", "20-25 breaths", "25-30 breaths", "30-35 breaths", "40+ breaths"
        ]

        for i in range(1, 6):
            start = zone_boundaries.get(f"zone{i}_start", 0)
            end = zone_boundaries.get(f"zone{i}_end", 0)

            mask = (self.pnoe_df["HR(bpm)_smoothed"] >= start) & (
                self.pnoe_df["HR(bpm)_smoothed"] <= end
            )
            zone_df = self.pnoe_df[mask]

            zone_data = {
                "zone": i,
                "hr_start": start,
                "hr_end": end,
            }

            if not zone_df.empty:
                speed_series = zone_df[zone_df["Speed"] > 0.1]["Speed"]
                if not speed_series.empty:
                    zone_data["min_speed"] = float(speed_series.min())
                    zone_data["max_speed"] = float(speed_series.max())
                    min_pace_m, min_pace_s = speed_to_pace(speed_series.max())
                    max_pace_m, max_pace_s = speed_to_pace(speed_series.min())
                    zone_data["min_pace"] = f"{min_pace_m}:{min_pace_s:02d}"
                    zone_data["max_pace"] = f"{max_pace_m}:{max_pace_s:02d}"
                else:
                    zone_data["min_speed"] = 0.0
                    zone_data["max_speed"] = 0.0
                    zone_data["min_pace"] = "-"
                    zone_data["max_pace"] = "-"

                zone_data["avg_calories"] = float(zone_df["EE(kcal/min)"].mean())
                zone_data["avg_carbs_g"] = float(zone_df["CHO"].mean() / 4)
                zone_data["avg_breaths"] = int(zone_df["BF(bpm)_smoothed"].mean())
            else:
                zone_data.update({
                    "min_speed": 0.0, "max_speed": 0.0,
                    "min_pace": "-", "max_pace": "-",
                    "avg_calories": 0.0, "avg_carbs_g": 0.0, "avg_breaths": 0,
                })

            zone_data["ideal_breath_range"] = ideal_breath_ranges[i - 1]
            zones.append(zone_data)

        return zones

    # ==================== Master Calculation Method ====================

    def calculate_all_metrics(
        self,
        weight_kg: float,
        height_cm: float,
        age: int,
        gender: str,
        fat_percentage: float,
        activity_level: str,
        weekly_weight_loss_lbs: float,
        zone_mode: str = "vt_based",
        manual_zones: Optional[Dict[str, int]] = None,
        rmr_time_start: Optional[float] = None,
        rmr_time_end: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate all metrics from loaded data.

        This is the main entry point that orchestrates all calculations.

        Returns:
            Dictionary with all calculated metrics ready for database storage
        """
        metrics = {}

        # Spirometry
        spirometry = self.calculate_spirometry_metrics()
        metrics.update(spirometry)

        # VO2 and cardiovascular
        vo2_metrics = self.calculate_vo2_metrics(weight_kg)
        metrics.update(vo2_metrics)

        # Thresholds
        thresholds = self.calculate_thresholds()
        metrics.update(thresholds)

        # Heart rate zones
        zones = self.calculate_hr_zones(
            vt1_hr=thresholds.get("vt1_hr"),
            vt2_hr=thresholds.get("vt2_hr"),
            age=age,
            zone_mode=zone_mode,
            manual_zones=manual_zones,
        )
        metrics.update(zones)

        # VO2 drop points
        drop_points = self.calculate_vo2_drop_points(zones)
        metrics.update(drop_points)

        # Recovery
        recovery = self.calculate_recovery_metrics()
        metrics.update(recovery)

        # Resting HR
        resting_hr = self.calculate_resting_hr()
        metrics.update(resting_hr)

        # RMR and fuel source
        rmr_fuel = self.calculate_rmr_and_fuel_source(rmr_time_start, rmr_time_end)
        metrics.update(rmr_fuel)

        # TDEE and targets
        tdee_targets = self.calculate_tdee_and_targets(
            rmr_fuel.get("rmr_kcal", 1500),
            activity_level,
            weekly_weight_loss_lbs,
        )
        metrics.update(tdee_targets)

        # Nutrition
        nutrition = self.calculate_nutrition_metrics(
            weight_kg,
            fat_percentage,
            age,
            tdee_targets.get("target_calories", 1500),
            tdee_targets.get("calorie_deficit", 0),
        )
        metrics.update(nutrition)

        # Body composition
        body_comp = self.calculate_body_composition(weight_kg, fat_percentage)
        metrics.update(body_comp)

        # Category determinations
        metrics["vo2_max_category"] = self.determine_vo2_max_category(
            vo2_metrics.get("vo2_max_per_kg", 0), age, gender
        )
        metrics["resting_hr_category"] = self.determine_rhr_category(
            resting_hr.get("resting_hr", 60), age, gender
        )

        # Zone analysis (stored as JSON)
        zone_analysis = self.calculate_zone_analysis(zones)
        metrics["zone_analysis"] = zone_analysis

        return metrics
