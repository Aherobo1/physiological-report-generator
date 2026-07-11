import pandas as pd


def mifflin_st_jeor(weight_kg, height_cm, age_years, sex):
    """
    Compute predicted RMR with Mifflin St Jeor.
    sex: 'male' or 'female'
    """
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age_years
    if sex.lower().startswith("m"):
        return base + 5.0
    else:
        return base - 161.0


def classify_metabolism(measured_kcal_day, predicted_kcal_day):
    """
    Classify metabolic rate relative to prediction.
    Returns (label, ratio).
    """
    ratio = measured_kcal_day / predicted_kcal_day

    if ratio < 0.70:
        label = "very slow"
    elif ratio < 0.90:
        label = "slow"
    elif ratio <= 1.10:
        label = "average"
    elif ratio <= 1.30:
        label = "fast"
    else:
        label = "very fast"

    return label, ratio


def find_sampling_window(df):
    """
    Derive number of samples that represent about 2 minutes.
    """
    dt = df["T(sec)"].diff().median()
    if dt is None or dt <= 0:
        raise ValueError("Invalid time step in T(sec)")

    samples = int(round(120.0 / dt))
    if samples < 1:
        samples = 1
    return samples


def rolling_stable_window(df, window_samples):
    """
    Find the most stable 2-minute window using rolling standard deviation.
    Returns:
        means_series, t_start, t_end
    """
    cols_mean = [
        "VO2(ml/min)",
        "VCO2(ml/min)",
        "VE(l/min)",
        "VT(l)",
        "BF(bpm)",
        "EE(kcal/min)",
        "RER",
        "CARBS(%)",
        "FAT(%)",
    ]

    cols_std = [
        "VO2(ml/min)",
        "VCO2(ml/min)",
        "VE(l/min)",
        "VT(l)",
        "BF(bpm)",
    ]

    roll_mean = df[cols_mean].rolling(window_samples, min_periods=window_samples).mean()
    roll_std = df[cols_std].rolling(window_samples, min_periods=window_samples).std()

    # Sum std devs to get stability score; use skipna=False to preserve NaN for incomplete windows
    stability_score = roll_std.sum(axis=1, skipna=False)

    # Find index with lowest stability score (dropna to ignore incomplete windows)
    best_idx = stability_score.dropna().idxmin()

    means_series = roll_mean.loc[best_idx].copy()

    start_idx = max(best_idx - window_samples + 1, 0)
    end_idx = best_idx

    t_start = float(df["T(sec)"].iloc[start_idx])
    t_end = float(df["T(sec)"].iloc[end_idx])

    return means_series, t_start, t_end


def manual_window_means(df, t_start, t_end):
    """
    Compute mean values inside a user-selected time window.
    """
    mask = (df["T(sec)"] >= t_start) & (df["T(sec)"] <= t_end)
    slice_df = df.loc[mask].copy()

    if slice_df.empty:
        raise ValueError("Manual window has no rows inside T(sec) range")

    cols = [
        "VO2(ml/min)",
        "VCO2(ml/min)",
        "VE(l/min)",
        "VT(l)",
        "BF(bpm)",
        "EE(kcal/min)",
        "RER",
        "CARBS(%)",
        "FAT(%)",
    ]

    means = slice_df[cols].mean()
    return means, float(t_start), float(t_end)


def load_pnoe_csv(path):
    """
    Load and clean a PNOE CSV file.
    """
    df = pd.read_csv(path, sep=";")

    numeric_cols = [
        "T(sec)",
        "VO2(ml/min)",
        "VCO2(ml/min)",
        "RER",
        "VE(l/min)",
        "VT(l)",
        "BF(bpm)",
        "EE(kcal/min)",
        "CARBS(%)",
        "FAT(%)",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["VO2(ml/min)", "EE(kcal/min)"]).reset_index(drop=True)
    return df


def analyze_pnoe_rmr(
    path,
    weight_kg,
    height_cm,
    age_years,
    sex,
    subject_name=None,
    test_date=None,
    manual_window=None,
):
    """
    Analyze resting RMR from a PNOE CSV file.

    manual_window:
        None for automatic stable window
        or (t_start_sec, t_end_sec) for user-chosen window
    """
    df = load_pnoe_csv(path)
    window_samples = find_sampling_window(df)

    # Automatic stable window
    auto_means, auto_t_start, auto_t_end = rolling_stable_window(df, window_samples)

    # Manual override if provided
    manual_means = None
    manual_t_start = None
    manual_t_end = None

    if manual_window is not None:
        t_start_manual, t_end_manual = manual_window
        manual_means, manual_t_start, manual_t_end = manual_window_means(
            df, t_start_manual, t_end_manual
        )
        chosen_source = "manual"
        chosen_means = manual_means
        chosen_t_start = manual_t_start
        chosen_t_end = manual_t_end
    else:
        chosen_source = "auto"
        chosen_means = auto_means
        chosen_t_start = auto_t_start
        chosen_t_end = auto_t_end

    kcal_per_min = float(chosen_means["EE(kcal/min)"])
    rmr_kcal_day = kcal_per_min * 1440.0

    predicted_kcal_day = mifflin_st_jeor(weight_kg, height_cm, age_years, sex)
    label, ratio = classify_metabolism(rmr_kcal_day, predicted_kcal_day)

    def pack_metrics(prefix, means, t_start, t_end):
        if means is None:
            return {}
        return {
            f"{prefix}_window_start_sec": t_start,
            f"{prefix}_window_end_sec": t_end,
            f"{prefix}_VO2_L_min": float(means["VO2(ml/min)"]) / 1000.0,
            f"{prefix}_VCO2_L_min": float(means["VCO2(ml/min)"]) / 1000.0,
            f"{prefix}_VE_L_min": float(means["VE(l/min)"]),
            f"{prefix}_VT_L": float(means["VT(l)"]),
            f"{prefix}_BF_bpm": float(means["BF(bpm)"]),
            f"{prefix}_RER": float(means["RER"]),
            f"{prefix}_Fat_percent": float(means["FAT(%)"]),
            f"{prefix}_Carb_percent": float(means["CARBS(%)"]),
            f"{prefix}_kcal_per_min": float(means["EE(kcal/min)"]),
        }

    result = {
        "subject_name": subject_name,
        "test_date": test_date,
        "sex": sex,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "age_years": age_years,
        "chosen_window_source": chosen_source,
        "chosen_window_start_sec": chosen_t_start,
        "chosen_window_end_sec": chosen_t_end,
        "RMR_kcal_day": rmr_kcal_day,
        "Mifflin_kcal_day": predicted_kcal_day,
        "Measured_to_Mifflin_ratio": ratio,
        "Metabolic_classification": label,
    }

    result.update(pack_metrics("auto", auto_means, auto_t_start, auto_t_end))
    result.update(pack_metrics("manual", manual_means, manual_t_start, manual_t_end))

    return result


result = analyze_pnoe_rmr(
    path="/home/oluwasanmi/Documents/Work/MKD/report_generation/data/Pnoe_20250729_1550-Moran_Keirstyn.csv",
    weight_kg=56,
    height_cm=162,
    age_years=34,
    sex="female",
    subject_name="Cullen Pacas",
    test_date="2025-11-12",
    manual_window=None,  # or (t_start_sec, t_end_sec)
)

for key, value in result.items():
    print(f"{key}: {value}")
