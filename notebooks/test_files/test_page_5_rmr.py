import pandas as pd
import numpy as np

# --- CONFIGURATION TABLES (From your PDFs) ---

# From deficit.pdf
ACTIVITY_MULTIPLIERS = {
    "Sedentary": 1.2, "Light": 1.375, "Moderate": 1.55, "Active": 1.7, "Extreme": 1.9
}

# From deficit.pdf (Weight Loss kg -> Calorie Deficit)
DEFICIT_TABLE = {
    0.1: 85, 0.2: 169, 0.3: 254, 0.4: 339, 0.5: 423, 
    0.6: 508, 0.7: 593, 0.8: 677, 0.9: 762, 1.0: 847, 
    1.1: 931, 1.2: 1016
}

# From no_deficit.pdf (Protein Multipliers g/kg of Lean Body Mass)
PROTEIN_GUIDELINES = {
    (0, 30):  {'maintenance': 1.9, 'deficit': 2.3},   
    (30, 40): {'maintenance': 2.15, 'deficit': 2.6}, 
    (40, 50): {'maintenance': 2.45, 'deficit': 2.95}, 
    (50, 60): {'maintenance': 2.75, 'deficit': 3.3},  
    (60, 100): {'maintenance': 3.05, 'deficit': 3.65} 
}

def analyze_pnoe_data(csv_path):
    """
    Parses PNOE CSV. FIX: Uses MEDIAN instead of MEAN to avoid outliers.
    """
    df = pd.read_csv(csv_path, delimiter=';')
    df.columns = df.columns.str.strip()
    
    # Filter for RMR window (assumed T=60s to T=300s, 4 minutes of stable rest)
    df_stable = df[(df['T(sec)'] >= 60) & (df['T(sec)'] <= 300)].copy()

    # Ensure data columns are numeric
    for col in ['EE(kcal/day)', 'RER', 'T(sec)']:
        df_stable.loc[:, col] = pd.to_numeric(df_stable[col], errors='coerce')
        
    df_stable.dropna(subset=['EE(kcal/day)', 'RER'], inplace=True)

    if not df_stable.empty:
        # **CRITICAL CHANGE: Use Median instead of Mean**
        rmr_measured = df_stable['EE(kcal/day)'].median() 
        rer = df_stable['RER'].median()
    else:
        # Fallback if window is empty
        rmr_measured = 1386.0 
        rer = 0.85
        
    # Calculate Fuel Source
    clamped_rer = max(0.7, min(1.0, rer))
    percent_carbs = (clamped_rer - 0.7) / 0.3
    percent_fat = 1.0 - percent_carbs

    return {
        "measured_rmr": int(round(rmr_measured)),
        "rer": round(rer, 2),
        "fuel_source": {
            "fat_percent": round(percent_fat * 100, 1),
            "carb_percent": round(percent_carbs * 100, 1)
        }
    }

def assess_metabolic_health(measured_rmr, weight_kg, height_cm, age, sex):
    """
    Calculates Predicted RMR (Mifflin-St Jeor) and compares to Measured RMR.
    """
    # Mifflin-St Jeor Formula
    if sex.lower() == 'male':
        predicted_rmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        predicted_rmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
        
    variance = ((measured_rmr - predicted_rmr) / predicted_rmr) * 100
    
    # Interpretation 
    if variance > 10:
        metabolism_type = "Fast"
    elif variance < -10:
        metabolism_type = "Slow"
    else:
        metabolism_type = "Normal"
        
    return {
        "predicted_rmr_mifflin": int(round(predicted_rmr)),
        "variance_percent": round(variance, 1),
        "metabolism_type": metabolism_type
    }

def generate_nutrition_plan(measured_rmr, weight_kg, body_fat_percent, age, activity_level, weekly_weight_loss_goal_kg):
    """
    Calculates TDEE, applies Deficit, and calculates Macros based on uploaded PDFs.
    """
    # 1. TDEE (Maintenance Calories)
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.2)
    maintenance_calories = measured_rmr * multiplier
    
    # 2. Daily Calorie Target
    daily_deficit = DEFICIT_TABLE.get(weekly_weight_loss_goal_kg, 0)
    target_calories = maintenance_calories - daily_deficit
    is_deficit = daily_deficit > 0
    
    # 3. Protein Needs (Based on Lean Body Mass and age/deficit status)
    lean_mass_kg = weight_kg * (1 - (body_fat_percent / 100))
    
    protein_multiplier = 1.8 # default fallback
    for (min_age, max_age), values in PROTEIN_GUIDELINES.items():
        if min_age <= age < max_age:
            protein_multiplier = values['deficit'] if is_deficit else values['maintenance']
            break
            
    daily_protein_grams = lean_mass_kg * protein_multiplier
    protein_calories = daily_protein_grams * 4
    
    # 4. Remaining Macros (Fats and Carbs)
    FAT_PERCENT_OF_TOTAL_CALORIES = 0.28 # Standard 25-30% fat allocation
    
    fat_calories = target_calories * FAT_PERCENT_OF_TOTAL_CALORIES
    fat_grams = fat_calories / 9
    
    carb_calories = target_calories - protein_calories - fat_calories
    carb_grams = carb_calories / 4
    
    if carb_calories < 0:
        carb_calories = 0
        carb_grams = 0
        
    return {
        "tdee_maintenance": int(round(maintenance_calories)),
        "daily_deficit": daily_deficit,
        "target_calories": int(round(target_calories)),
        "macros": {
            "protein_g": int(round(daily_protein_grams)),
            "fats_g": int(round(fat_grams)),
            "carbs_g": int(round(carb_grams))
        },
        "caloric_breakdown": {
            "protein_kcal": int(round(protein_calories)),
            "fats_kcal": int(round(fat_calories)),
            "carbs_kcal": int(round(carb_calories))
        }
    }

# --- EXECUTION EXAMPLE ---

# 1. Run Analysis on the CSV
# Replace with your actual file path
csv_result = analyze_pnoe_data('/home/oluwasanmi/Documents/Work/MKD/report_generation/data/Pnoe_20250729_1550-Moran_Keirstyn.csv')

# 2. Inputs for the Calculation (These would come from your UI/Form)
user_weight = 85.0 # kg
user_height = 180.0 # cm
user_age = 35
user_sex = 'male'
user_body_fat = 20.0 # %
user_activity = 'Moderate' # From the PDF list
user_goal_loss = 0.5 # kg per week

# 3. Assess Health
health_assessment = assess_metabolic_health(
    measured_rmr=csv_result['measured_rmr'],
    weight_kg=user_weight,
    height_cm=user_height,
    age=user_age,
    sex=user_sex
)

# 4. Get Nutrition Plan
nutrition_plan = generate_nutrition_plan(
    measured_rmr=csv_result['measured_rmr'],
    weight_kg=user_weight,
    body_fat_percent=user_body_fat,
    age=user_age,
    activity_level=user_activity,
    weekly_weight_loss_goal_kg=user_goal_loss
)

# --- OUTPUT ---
print("--- METABOLIC REPORT ---")
print(f"Measured RMR: {csv_result['measured_rmr']} kcal/day")
print(f"Predicted RMR: {health_assessment['predicted_rmr_mifflin']} kcal/day")
print(f"Metabolism Status: {health_assessment['metabolism_type']} ({health_assessment['variance_percent']}%)")
print(f"Fuel Source: {csv_result['fuel_source']['fat_percent']}% Fat, {csv_result['fuel_source']['carb_percent']}% Carbs")
print("\n--- NUTRITION PLAN ---")
print(f"Goal: Lose {user_goal_loss} kg/week")
print(f"Daily Calorie Target: {nutrition_plan['target_calories']} kcal (Deficit: {nutrition_plan['daily_deficit']})")
print("\nDaily Macros:")
print(f"Protein: {nutrition_plan['macros']['protein_g']}g")
print(f"Fats:    {nutrition_plan['macros']['fats_g']}g")
print(f"Carbs:   {nutrition_plan['macros']['carbs_g']}g")