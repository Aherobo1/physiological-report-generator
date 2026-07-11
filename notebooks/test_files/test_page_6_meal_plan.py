"""
Test script for Page 6 - Meal Plan Calculations
Using Keirstyn Moran's actual data

Expected values from PDF (Page 6):
Row 1 (Caloric Deficit - 7 days same):
- Calories: 1725 kCals
- Protein: 120g (28%)
- Carbs: 155g (36%)
- Fat: 69g (36%)
- Fiber: 25g

Row 2 (Caloric Deficit with Refeed - 5 weekdays low, 2 weekend high):
Weekdays (5 days):
- Calories: 1615 kCals
- Protein: 120g
- Carbs: 142g
- Fat: 63g
- Fiber: 24g

Weekends (2 days):
- Calories: 2000 kCals
- Protein: 120g
- Carbs: 190g
- Fat: 84g
- Fiber: 30g
"""

import sys

sys.path.insert(0, '/Users/macbook/bio-performx')

from app.services.context_generator import ContextGenerator

# Keirstyn Moran's patient data from PDF
PATIENT_DATA = {
    "name": "Keirstyn Moran",
    "first_name": "Keirstyn",
    "last_name": "Moran",
    "age": 34,
    "height": "5'4\"",  # 162.56 cm
    "weight": 55.79,  # 123 lbs = 55.79 kg
    "gender": "female",
    "fat_percentage": 20.0,  # Estimated
    "activity_level": "moderate",
}

# RMR metrics from Page 5 (using expected PDF values)
RMR_METRICS_EXPECTED = {
    "total_calories": 1725,
    "resting_calories": 1386,
    "neat_calories": 762,
    "weight_loss_calories": 423,
}

def main():
    print("=" * 80)
    print("PAGE 6 - MEAL PLAN CALCULATION TEST")
    print("=" * 80)
    print(f"\nPatient: {PATIENT_DATA['name']}")
    print(f"Weight: {PATIENT_DATA['weight']}kg ({PATIENT_DATA['weight'] * 2.20462:.1f}lbs)")
    print(f"Body Fat: {PATIENT_DATA['fat_percentage']}%")
    
    # Create context generator
    gen = ContextGenerator()
    
    # Set patient info manually
    gen.patient_info = PATIENT_DATA.copy()
    
    # Calculate fat mass and lean mass
    weight_kg = PATIENT_DATA["weight"]
    fat_pct = PATIENT_DATA["fat_percentage"]
    lean_mass_kg = weight_kg * (1 - fat_pct / 100)
    lean_mass_lbs = lean_mass_kg * 2.20462
    
    gen.patient_info["fat_mass_lbs"] = weight_kg * fat_pct / 100 * 2.20462
    gen.patient_info["lean_mass_lbs"] = lean_mass_lbs
    
    print(f"Lean Mass: {lean_mass_lbs:.2f} lbs ({lean_mass_kg:.2f} kg)")
    print(f"Fat Mass: {gen.patient_info['fat_mass_lbs']:.2f} lbs")
    
    print("\n" + "=" * 80)
    print("CALCULATING MEAL PLAN (using our formula)")
    print("=" * 80)
    print(f"\nTotal Daily Calories (from Page 5): {RMR_METRICS_EXPECTED['total_calories']} kcal")
    
    # Calculate meal plan using our formula
    try:
        meal_metrics = gen.calculate_meal_plan_breakdown(RMR_METRICS_EXPECTED)
        
        print("\n--- Protein Calculation (Bio-PerformX Formula) ---")
        print(f"Formula: Total Body Weight (kg) × 2.15 g/kg")
        print(f"       = {weight_kg:.2f} × 2.15")
        protein_grams = weight_kg * 2.15
        print(f"       = {protein_grams:.0f}g protein")
        protein_calories = protein_grams * 4
        print(f"       = {protein_calories:.0f} kcal from protein")
        
        print("\n--- Carbs and Fats (50/50 split of remaining calories) ---")
        remaining = RMR_METRICS_EXPECTED['total_calories'] - protein_calories
        print(f"Remaining calories: {RMR_METRICS_EXPECTED['total_calories']} - {protein_calories:.0f} = {remaining:.0f} kcal")
        print(f"Carbs (50%): {remaining * 0.5:.0f} kcal ÷ 4 = {remaining * 0.5 / 4:.0f}g")
        print(f"Fats (50%): {remaining * 0.5:.0f} kcal ÷ 9 = {remaining * 0.5 / 9:.0f}g")
        
        print("\n--- Fiber Calculation ---")
        print(f"Formula: 15g per 1000 calories")
        print(f"       = {RMR_METRICS_EXPECTED['total_calories']} ÷ 1000 × 15")
        print(f"       = {RMR_METRICS_EXPECTED['total_calories'] / 1000 * 15:.0f}g")
        
        print("\n" + "=" * 80)
        print("ROW 1: CALORIC DEFICIT (7 days same)")
        print("=" * 80)
        print(f"Calories: {meal_metrics['deficit_calories']} kcal")
        print(f"Protein:  {meal_metrics['deficit_protein']}g ({meal_metrics['protein_percentage']}%)")
        print(f"Carbs:    {meal_metrics['deficit_carbs']}g ({meal_metrics['carbs_percentage']}%)")
        print(f"Fat:      {meal_metrics['deficit_fat']}g ({meal_metrics['fats_percentage']}%)")
        print(f"Fiber:    {meal_metrics['deficit_fiber']}g")
        
        print("\n" + "=" * 80)
        print("ROW 2: CALORIC DEFICIT WITH REFEED (5 weekdays + 2 weekends)")
        print("=" * 80)
        
        print("\nWeekdays (5 days):")
        print(f"Calories: {meal_metrics['refeed_weekday_calories']} kcal")
        print(f"Protein:  {meal_metrics['refeed_weekday_protein']}g")
        print(f"Carbs:    {meal_metrics['refeed_weekday_carbs']}g")
        print(f"Fat:      {meal_metrics['refeed_weekday_fat']}g")
        print(f"Fiber:    {meal_metrics['refeed_weekday_fiber']}g")
        
        print("\nWeekends (2 days):")
        print(f"Calories: {meal_metrics['refeed_weekend_calories']} kcal")
        print(f"Protein:  {meal_metrics['refeed_weekend_protein']}g")
        print(f"Carbs:    {meal_metrics['refeed_weekend_carbs']}g")
        print(f"Fat:      {meal_metrics['refeed_weekend_fat']}g")
        print(f"Fiber:    {meal_metrics['refeed_weekend_fiber']}g")
        
        print("\n--- Weekly Total Verification ---")
        weekly_total_row1 = meal_metrics['deficit_calories'] * 7
        weekly_total_row2 = (meal_metrics['refeed_weekday_calories'] * 5) + (meal_metrics['refeed_weekend_calories'] * 2)
        print(f"Row 1 Weekly Total: {meal_metrics['deficit_calories']} × 7 = {weekly_total_row1} kcal")
        print(f"Row 2 Weekly Total: ({meal_metrics['refeed_weekday_calories']} × 5) + ({meal_metrics['refeed_weekend_calories']} × 2) = {weekly_total_row2} kcal")
        print(f"Difference: {abs(weekly_total_row1 - weekly_total_row2)} kcal (should be ~0)")
        
        print("\n" + "=" * 80)
        print("EXPECTED VALUES (From PDF Page 6)")
        print("=" * 80)
        
        print("\nRow 1 (Deficit - 7 days):")
        print("Calories: 1725 kcal")
        print("Protein:  120g (28%)")
        print("Carbs:    155g (36%)")
        print("Fat:      69g (36%)")
        print("Fiber:    25g")
        
        print("\nRow 2 Weekdays:")
        print("Calories: 1615 kcal")
        print("Protein:  120g")
        print("Carbs:    142g")
        print("Fat:      63g")
        print("Fiber:    24g")
        
        print("\nRow 2 Weekends:")
        print("Calories: 2000 kcal")
        print("Protein:  120g")
        print("Carbs:    190g")
        print("Fat:      84g")
        print("Fiber:    30g")
        
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        
        expected_row1 = {
            "calories": 1725,
            "protein": 120,
            "carbs": 155,
            "fat": 69,
            "fiber": 25
        }
        
        expected_weekday = {
            "calories": 1615,
            "protein": 120,
            "carbs": 142,
            "fat": 63,
            "fiber": 24
        }
        
        expected_weekend = {
            "calories": 2000,
            "protein": 120,
            "carbs": 190,
            "fat": 84,
            "fiber": 30
        }
        
        def compare(label, expected_val, actual_val, unit=""):
            diff = actual_val - expected_val
            pct_diff = (diff / expected_val * 100) if expected_val != 0 else 0
            status = "✓" if abs(pct_diff) < 5 else "✗"
            print(f"{status} {label:25} Expected: {expected_val:5}{unit}  Actual: {actual_val:5}{unit}  Diff: {diff:+5.0f} ({pct_diff:+.1f}%)")
        
        print("\nRow 1 (Deficit - 7 days):")
        compare("Calories", expected_row1['calories'], meal_metrics['deficit_calories'], " kcal")
        compare("Protein", expected_row1['protein'], meal_metrics['deficit_protein'], "g")
        compare("Carbs", expected_row1['carbs'], meal_metrics['deficit_carbs'], "g")
        compare("Fat", expected_row1['fat'], meal_metrics['deficit_fat'], "g")
        compare("Fiber", expected_row1['fiber'], meal_metrics['deficit_fiber'], "g")
        
        print("\nRow 2 Weekdays:")
        compare("Calories", expected_weekday['calories'], meal_metrics['refeed_weekday_calories'], " kcal")
        compare("Protein", expected_weekday['protein'], meal_metrics['refeed_weekday_protein'], "g")
        compare("Carbs", expected_weekday['carbs'], meal_metrics['refeed_weekday_carbs'], "g")
        compare("Fat", expected_weekday['fat'], meal_metrics['refeed_weekday_fat'], "g")
        compare("Fiber", expected_weekday['fiber'], meal_metrics['refeed_weekday_fiber'], "g")
        
        print("\nRow 2 Weekends:")
        compare("Calories", expected_weekend['calories'], meal_metrics['refeed_weekend_calories'], " kcal")
        compare("Protein", expected_weekend['protein'], meal_metrics['refeed_weekend_protein'], "g")
        compare("Carbs", expected_weekend['carbs'], meal_metrics['refeed_weekend_carbs'], "g")
        compare("Fat", expected_weekend['fat'], meal_metrics['refeed_weekend_fat'], "g")
        compare("Fiber", expected_weekend['fiber'], meal_metrics['refeed_weekend_fiber'], "g")
        
        # Overall assessment
        row1_match = all([
            abs(meal_metrics['deficit_calories'] - expected_row1['calories']) <= 5,
            abs(meal_metrics['deficit_protein'] - expected_row1['protein']) <= 5,
            abs(meal_metrics['deficit_carbs'] - expected_row1['carbs']) <= 5,
            abs(meal_metrics['deficit_fat'] - expected_row1['fat']) <= 5,
        ])
        
        weekday_match = all([
            abs(meal_metrics['refeed_weekday_calories'] - expected_weekday['calories']) <= 10,
            abs(meal_metrics['refeed_weekday_protein'] - expected_weekday['protein']) <= 5,
            abs(meal_metrics['refeed_weekday_carbs'] - expected_weekday['carbs']) <= 5,
            abs(meal_metrics['refeed_weekday_fat'] - expected_weekday['fat']) <= 5,
        ])
        
        weekend_match = all([
            abs(meal_metrics['refeed_weekend_calories'] - expected_weekend['calories']) <= 10,
            abs(meal_metrics['refeed_weekend_protein'] - expected_weekend['protein']) <= 5,
            abs(meal_metrics['refeed_weekend_carbs'] - expected_weekend['carbs']) <= 10,
            abs(meal_metrics['refeed_weekend_fat'] - expected_weekend['fat']) <= 5,
        ])
        
        print("\n" + "=" * 80)
        if row1_match and weekday_match and weekend_match:
            print("✓ SUCCESS: Our formula produces values matching the PDF!")
        else:
            print("✗ WARNING: Significant differences found. Check:")
            if not row1_match:
                print("  - Row 1 calculations (daily deficit)")
            if not weekday_match:
                print("  - Weekday calculations (10% reduction)")
            if not weekend_match:
                print("  - Weekend calculations (maintaining weekly total)")
            print("\nNote: Protein formula is Bio-PerformX specific: Lean Mass (lbs) × 2.2")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error calculating metrics: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
