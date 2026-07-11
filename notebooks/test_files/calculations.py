import math

# --- Data Dictionaries from the provided PDF documents ---

# NEAT/Activity Multipliers from 'deficit.pdf'
NEAT_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.7,
    "extreme": 1.9
}

# Daily Calorie Deficit required for a specific Weekly Weight Loss (kg) from 'deficit.pdf'
# Note: The table is in lbs/kg, but we use kg as the key for consistency.
CALORIE_DEFICIT_MAP_KG = {
    1.2: 1016, # 2.6 lbs
    1.1: 931,  # 2.4 lbs
    1.0: 847,  # 2.2 lbs
    0.9: 762,  # 1.9 lbs
    0.8: 677,  # 1.7 lbs
    0.7: 593,  # 1.5 lbs
    0.6: 508,  # 1.3 lbs
    0.5: 423,  # 1.1 lbs
    0.4: 339,  # 0.8 lbs
    0.3: 254,  # 0.6 lbs
    0.2: 169,  # 0.4 lbs
    0.1: 85   # 0.2 lbs
}
CALORIE_DEFICIT_MAP_LBS = {
    2.6: 1016, # 2.6 lbs
    2.4: 931,  # 2.4 lbs
    2.2: 847,  # 2.2 lbs
    1.9: 762,  # 1.9 lbs
    1.7: 677,  # 1.7 lbs
    1.5: 593,  # 1.5 lbs
    1.3: 508,  # 1.3 lbs
    1.1: 423,  # 1.1 lbs
    0.8: 339,  # 0.8 lbs
    0.6: 254,  # 0.6 lbs
    0.4: 169,  # 0.4 lbs
    0.2: 85   # 0.2 lbs
}

# Protein Requirements (g/kg LBM) based on Age and Deficit Status from 'no_deficit.pdf'
PROTEIN_REQUIREMENTS = {
    "0-30": {"no_deficit": (1.8, 2.0), "deficit": (2.2, 2.4)},
    "30-40": {"no_deficit": (2.0, 2.3), "deficit": (2.4, 2.8)},
    "40-50": {"no_deficit": (2.3, 2.6), "deficit": (2.8, 3.1)},
    "50-60": {"no_deficit": (2.6, 2.9), "deficit": (3.1, 3.5)},
    "60-70": {"no_deficit": (2.9, 3.2), "deficit": (3.5, 3.8)}
}

# --- Core Calculation Functions ---

def calculate_rmr_mifflin(weight_kg, height_cm, age_years, sex):
    """
    Calculates the Resting Metabolic Rate (RMR) using the Mifflin-St Jeor Equation.
    This equation is used as a standard RMR estimator since the exact formula
    used for RMR in the original files is not provided.

    RMR = (10 * W) + (6.25 * H) - (5 * A) + S
    W = weight in kg
    H = height in cm
    A = age in years
    S = +5 for male, -161 for female
    """
    if sex.lower() == 'male':
        s = 5
    elif sex.lower() == 'female':
        s = -161
    else:
        raise ValueError("Sex must be 'male' or 'female'.")

    # RMR formula
    rmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + s
    return round(rmr)

def calculate_tdee(rmr, activity_level):
    """
    Calculates Total Daily Energy Expenditure (TDEE) using the RMR and the
    activity multiplier (NEAT).
    TDEE = RMR * NEAT Multiplier
    """
    level = activity_level.lower()
    if level not in NEAT_MULTIPLIERS:
        raise ValueError(f"Invalid activity level: {activity_level}. Choose from {', '.join(NEAT_MULTIPLIERS.keys())}")

    multiplier = NEAT_MULTIPLIERS[level]
    tdee = rmr * multiplier
    neat_calorie = tdee - rmr 
    return round(neat_calorie), multiplier

def calculate_calorie_goal(tdee, weekly_goal_kg):
    """
    Calculates the required daily calorie deficit and the resulting daily calorie
    intake based on the weekly weight goal (kg), using the provided lookup table.
    """
    goal_kg = round(weekly_goal_kg, 1)

    # Check for weight maintenance (goal is 0)
    if goal_kg == 0:
        return tdee, 0, "Maintenance"

    # Check for weight gain (positive goal)
    if goal_kg > 0:
        # The provided data is only for weight loss (deficit).
        # We will estimate a surplus for weight gain (e.g., +500 kcal).
        # This is not based on the table, but a standard practice.
        surplus = 500
        calorie_goal = tdee + surplus
        return calorie_goal, surplus, "Gain (Estimated +500kCal Surplus)"

    # Handle weight loss (negative goal)
    target_loss_kg = abs(goal_kg) # Convert loss goal to positive key for lookup

    if target_loss_kg in CALORIE_DEFICIT_MAP_KG:
        deficit = CALORIE_DEFICIT_MAP_KG[target_loss_kg]
        calorie_goal = tdee - deficit
        return calorie_goal, deficit, "Loss"
    else:
        # If the exact goal isn't in the table, raise an error or interpolate.
        # For simplicity, we'll raise an error for now.
        valid_goals = ', '.join(map(str, sorted(CALORIE_DEFICIT_MAP_KG.keys())))
        raise ValueError(f"Weekly weight loss goal of {target_loss_kg} kg not found in the table. Choose from: {valid_goals} kg.")


def get_protein_range(age_years, lean_body_mass_kg, goal_type):
    """
    Determines the protein requirement range (g) based on age, LBM, and goal (deficit or no deficit).
    """
    # 1. Determine the Age Range key
    if 0 <= age_years <= 30:
        age_key = "0-30"
    elif 30 < age_years <= 40:
        age_key = "30-40"
    elif 40 < age_years <= 50:
        age_key = "40-50"
    elif 50 < age_years <= 60:
        age_key = "50-60"
    elif 60 < age_years <= 70:
        age_key = "60-70"
    else:
        # Beyond the scope of the provided table
        return (None, None, "Age outside of lookup table (0-70 years)")

    # 2. Determine the Deficit Status key
    deficit_status = "deficit" if goal_type == "Loss" else "no_deficit"

    # 3. Get the g/kg LBM protein factors
    min_factor, max_factor = PROTEIN_REQUIREMENTS[age_key][deficit_status]

    # 4. Calculate the total gram range
    min_protein = round(min_factor * lean_body_mass_kg)
    max_protein = round(max_factor * lean_body_mass_kg)

    return (min_protein, max_protein, f"{min_factor}-{max_factor} g/kg LBM")

# --- Main Program Execution ---

def main_calculator():
    """
    Collects user inputs and displays the calculated metabolic and nutritional values.
    """
    print("--- Metabolic & Nutritional Targets Calculator ---")
    print("Please enter your data for calculation (using metric units):\n")

    # 1. User Inputs (Required for all calculations)
    try:
        # RMR inputs
        weight_kg = float(input("Enter Weight (kg): "))
        height_cm = float(input("Enter Height (cm): "))
        age_years = int(input("Enter Age (years): "))
        sex = input("Enter Sex (Male/Female): ").strip()

        # TDEE input
        print("\nNEAT / Activity Levels: sedentary, light, moderate, active, extreme")
        activity_level = input("Enter Activity Level: ").strip().lower()

        # Protein input (Assumed to be known from a body composition scan)
        lean_body_mass_kg = float(input("Enter Lean Body Mass (LBM) (kg): "))

        # Calorie Goal input
        print("\nCalorie Goals:")
        print("To MAINTAIN: Enter 0")
        print("To LOSE: Enter a negative value (e.g., -0.5 for 0.5kg/week loss).")
        print("Supported Loss Goals (kg/week): 0.1 to 1.2 in 0.1 increments.")
        print("To GAIN: Enter a positive value (uses a standard +500 kcal surplus).")
        weekly_goal_kg = float(input("Enter Weekly Weight Goal (kg): "))

    except ValueError:
        print("\nERROR: Invalid input. Please ensure numerical values are entered correctly.")
        return

    # 2. Perform Calculations
    try:
        # A. RMR Calculation (Mifflin-St Jeor proxy)
        rmr_calc = calculate_rmr_mifflin(weight_kg, height_cm, age_years, sex)

        # B. TDEE Calculation (RMR * NEAT Multiplier)
        tdee_calc, multiplier = calculate_tdee(rmr_calc, activity_level)

        # C. Calorie Goal Calculation (TDEE +/- Deficit/Surplus)
        calorie_goal, delta, goal_type = calculate_calorie_goal(tdee_calc, weekly_goal_kg)

        # D. Protein Requirement Calculation
        min_p, max_p, p_factor_text = get_protein_range(age_years, lean_body_mass_kg, goal_type.split()[0])

    except ValueError as e:
        print(f"\nERROR: {e}")
        return

    # 3. Display Results
    print("\n" + "="*50)
    print("         METABOLIC & NUTRITIONAL RESULTS")
    print("="*50)

    # --- Metabolism & TDEE ---
    print("\n--- Energy Expenditure (Calories Burned) ---")
    print(f"1. RMR (Resting Metabolic Rate)     : {rmr_calc:,} kCals/day (Mifflin-St Jeor)")
    print(f"2. NEAT Multiplier (Activity Level): {multiplier} ({activity_level.title()})")
    print(f"3. TDEE (Total Daily Energy Exp.)  : {tdee_calc:,} kCals/day (Maintenance Calories)")

    # --- Calorie Goal ---
    print("\n--- Calorie Goal & Deficit ---")
    print(f"Goal Type                          : {goal_type} ({abs(weekly_goal_kg)} kg/week)")
    print(f"Daily Deficit/Surplus (Delta)      : {delta:,} kCals")
    print(f"TARGET DAILY CALORIE INTAKE        : {calorie_goal:,} kCals")

    # --- Protein Goal ---
    print("\n--- Protein Requirement (From Table) ---")
    if min_p is not None:
        print(f"Age Range / Deficit Status         : {age_years} years / {'Deficit' if goal_type == 'Loss' else 'No Deficit'}")
        print(f"g/kg LBM Range                     : {p_factor_text}")
        print(f"TARGET DAILY PROTEIN INTAKE        : {min_p:,}g - {max_p:,}g")
    else:
        print(f"TARGET DAILY PROTEIN INTAKE        : {max_p}")

    print("="*50)
    print("\nNOTE: RMR is an estimate based on the Mifflin-St Jeor equation.")

# Execute the main function
if __name__ == "__main__":
    main_calculator()