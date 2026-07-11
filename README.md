# Physiological-Report-Generator

A comprehensive **medical performance report generation system** built with FastAPI. This application processes physiological test data (spirometry, metabolic analysis, oxygenation) and generates detailed, personalized PDF reports for patients undergoing performance assessments.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Data Flow](#data-flow)
- [Report Pages](#report-pages)
- [Database Schema](#database-schema)
- [Services](#services)
- [Configuration](#configuration)

---

## Overview

Physiological-Report-Generator is designed  to automate the generation of comprehensive performance assessment reports. The system takes raw physiological data from various medical devices and tests, processes it through sophisticated algorithms, and produces professional PDF reports with:

- **Spirometry Analysis** - Lung function metrics (FVC, FEV1, FEV1/FVC%)
- **VO2 Max & Cardiovascular Metrics** - Peak performance indicators
- **Heart Rate Zone Training** - Personalized training zones based on VT1/VT2 thresholds
- **Metabolic Analysis** - RMR, TDEE, and fuel utilization
- **Body Composition** - Fat mass, lean mass, and percentage analysis
- **Nutrition Planning** - Macro calculations for weekday/weekend plans
- **Recovery Metrics** - Cardiac, metabolic, and breathing recovery analysis
- **Muscle Oxygenation** - SmO2/TSI analysis (when available)

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-file Upload** | Process Spirometry PDF, Pnoe CSV, and optional Oxygenation CSV |
| **AI-Powered Extraction** | Uses Gemini AI to extract spirometry data from PDF tables |
| **Automated Calculations** | 50+ metrics calculated from raw data |
| **Dynamic Charts** | Matplotlib-generated visualizations |
| **Editable Metrics** | Preview and modify calculated values before report generation |
| **PDF Generation** | Professional multi-page reports via Playwright |
| **Session Persistence** | SQLAlchemy-based database for data storage |
| **Two Report Types** | Full (21 pages) and Minimal versions |

### Metric Categories

1. **Spirometry Metrics**
   - FVC (Forced Vital Capacity)
   - FEV1 (Forced Expiratory Volume)
   - FEV1/FVC Ratio
   - Lung capacity classification

2. **Cardiovascular Metrics**
   - VO2 Max (absolute & relative)
   - Peak Heart Rate
   - Resting Heart Rate
   - VT1/VT2 Thresholds

3. **Heart Rate Zones**
   - 5-zone training model
   - VT-based or manual calculation modes
   - Speed/pace at each zone boundary

4. **Metabolic Metrics**
   - Resting Metabolic Rate (RMR)
   - Total Daily Energy Expenditure (TDEE)
   - Fat/Carb oxidation at rest
   - Fat Max (peak fat burning point)

5. **Nutrition Metrics**
   - Target calories
   - Protein/Carbs/Fat/Fibre macros
   - Weekday vs Weekend meal plans
   - Calorie deficit calculations

6. **Recovery Metrics**
   - Cardiac recovery percentage
   - Metabolic (CO2) recovery
   - Breathing frequency recovery

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │────▶│  FastAPI App    │────▶│   SQLite DB     │
│   (Upload UI)   │     │  (main.py)      │     │ (bio_performx)  │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
           ┌────────────┐ ┌────────────┐ ┌────────────┐
           │  Metrics   │ │   Static   │ │  Dynamic   │
           │ Calculator │ │   Chart    │ │   Chart    │
           │  Service   │ │ Generator  │ │ Generator  │
           └────────────┘ └────────────┘ └────────────┘
                    │            │            │
                    └────────────┼────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │  Unified Report         │
                    │  Generator              │
                    │  (HTML → PDF)           │
                    └─────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Generated PDF Report   │
                    │  (21 pages)             │
                    └─────────────────────────┘
```

---

## Tech Stack

| Category | Technology |
|----------|------------|
| **Backend Framework** | FastAPI 0.118+ |
| **Database** | SQLite with SQLAlchemy ORM |
| **Data Processing** | Pandas, NumPy |
| **Visualization** | Matplotlib, Seaborn |
| **PDF Generation** | Playwright (Chromium) |
| **Templating** | Jinja2 |
| **AI/ML** | OpenRouter API (Gemini 2.5 Flash) |
| **Styling** | TailwindCSS (via CDN) |
| **Package Manager** | uv (recommended) |

---

## Project Structure

```
physiological-report-generator/
├── app/
│   ├── main.py                 # FastAPI application & routes
│   ├── db/
│   │   ├── database.py         # SQLAlchemy configuration
│   │   └── models.py           # Database models (Session, Metrics, etc.)
│   ├── services/
│   │   ├── metrics_calculator.py          # All metric calculations
│   │   ├── static_chart_generator.py      # Immutable charts (data-dependent)
│   │   ├── dynamic_chart_table_generator.py # Editable metric charts
│   │   ├── spirometry_table_extractor.py  # AI-powered PDF extraction
│   │   └── unified_report_generator.py    # HTML→PDF report generation
│   ├── report_gen/             # Jinja2 HTML templates for each report page
│   │   ├── header.html
│   │   ├── footer.html
│   │   ├── page_1.html         # Cover page
│   │   ├── page_2.html         # Overview
│   │   ├── ...
│   │   └── page_21.html        # Recommendations
│   ├── templates/              # Web UI templates
│   │   ├── base.html
│   │   ├── upload.html
│   │   ├── preview.html
│   │   └── edit.html
│   └── static_charts/          # Pre-made reference charts
│       ├── body_fat_percentage_master_chart.png
│       └── estimated_carb_storage.png
├── generated/                  # Session-specific output files
│   └── {session_uuid}/
│       ├── uploads/            # Original uploaded files
│       ├── static_charts/      # Generated immutable charts
│       ├── dynamic_charts/     # Generated editable charts
│       └── reports/            # Final PDF reports
├── notebooks/                  # Development & analysis notebooks
├── bio_performx.db             # SQLite database
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (API keys)
```

---

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd physiological-report-generator
   ```

2. **Install dependencies**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Configure environment**
   ```bash
   # Create .env file with your OpenRouter API key
   echo "OPENROUTER_API_KEY=your-api-key-here" > .env
   ```

5. **Run the application**
   ```bash
   # Using uv
   uv run fastapi dev app/main.py
   
   # Or directly
   fastapi dev app/main.py
   ```

6. **Access the application**
   Open `http://localhost:8000` in your browser

---

## Usage

### 1. Upload Patient Data

Navigate to the home page and fill in:

- **Patient Information**: Name, age, gender, height, weight, body fat %
- **Settings**: Activity level, weekly weight loss goal, report type
- **Files**:
  - Spirometry PDF (required) - Lung function test results
  - Pnoe CSV (required) - Metabolic cart data
  - Oxygenation CSV (optional) - Train.Red or similar SmO2 data

### 2. Preview & Edit

After upload:
- Review calculated metrics on the preview page
- Click "Edit" to modify any values
- Changes automatically regenerate dependent charts

### 3. Generate Report

- Click "Generate Report" to create the PDF
- View the report inline in the browser
- Download for printing or sharing

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Upload form (home page) |
| `POST` | `/upload` | Process files and calculate metrics |
| `GET` | `/preview` | Preview calculated data and charts |
| `GET` | `/edit` | Edit form for calculated metrics |
| `POST` | `/edit` | Save edited metrics |
| `POST` | `/generate-report` | Generate PDF report |
| `GET` | `/view-report` | View PDF in browser |
| `GET` | `/download-report` | Download PDF file |
| `GET` | `/chart/{session_id}/{type}/{filename}` | Serve generated charts |
| `GET` | `/health` | Health check endpoint |

---

## Data Flow

```
1. UPLOAD PHASE
   ├── User submits form with patient data + files
   ├── Files saved to generated/{session_id}/uploads/
   ├── Spirometry PDF → AI extraction → CSV
   └── Session record created in database

2. CALCULATION PHASE
   ├── MetricsCalculator loads all data files
   ├── Pnoe data preprocessed (smoothing, derived columns)
   ├── 50+ metrics calculated
   └── Metrics stored in database

3. CHART GENERATION PHASE
   ├── Static charts generated (data-dependent only)
   │   ├── Spirometry Z-score chart
   │   ├── VT/Respiratory chart
   │   ├── Relative VO2 chart
   │   ├── Fuel utilization chart
   │   ├── VO2 pulse/breath charts
   │   └── Recovery chart
   └── Dynamic charts generated (metric-dependent)
       ├── Body composition donut
       ├── Body fat percentage gauge
       ├── Metabolism comparison
       ├── HR zones table
       └── RHR table

4. EDIT PHASE (optional)
   ├── User modifies metrics
   ├── Dynamic charts regenerated
   └── Database updated

5. REPORT GENERATION PHASE
   ├── UnifiedReportGenerator loads session data
   ├── Page contexts built with consistent naming
   ├── Jinja2 templates rendered to HTML
   ├── Playwright converts HTML → PDF
   └── PDF saved to generated/{session_id}/reports/
```

---

## Report Pages

The generated report consists of up to 21 pages:

| Page | Content |
|------|---------|
| 1 | Cover page with patient name and date |
| 2 | Executive summary and key metrics overview |
| 3 | Testing overview and methodology |
| 4 | Body composition analysis |
| 5 | Resting Metabolic Rate (RMR) analysis |
| 6 | Daily nutrition and meal planning |
| 7 | Lung function / Spirometry results |
| 8 | VO2 Max assessment |
| 9 | Relative VO2 and cardiovascular efficiency |
| 10 | Fuel utilization during exercise |
| 11 | Fat metabolism and crossover point |
| 12 | VO2 per pulse and breath analysis |
| 13 | Recovery metrics and RHR |
| 14 | Muscle oxygenation (SmO2) analysis |
| 15 | Heart rate zone training guide |
| 16-17 | Zone-specific training recommendations |
| 18 | Fuel and carbohydrate storage |
| 19 | Hydration and electrolyte guidance |
| 20-21 | Summary recommendations and next steps |

**Note**: Minimal reports exclude certain pages for a condensed version.

---

## Database Schema

### Session Table
Stores patient information and report configuration.

```sql
sessions (
    session_id       VARCHAR(36) PRIMARY KEY,
    patient_name     VARCHAR(255),
    age              INTEGER,
    gender           VARCHAR(10),
    height_cm        FLOAT,
    weight_kg        FLOAT,
    body_fat_pct     FLOAT,
    activity_level   VARCHAR(50),
    weekly_weight_loss_lbs FLOAT,
    report_type      VARCHAR(20),  -- 'full' or 'minimal'
    respiratory_indication VARCHAR(20),
    zone_mode        VARCHAR(20),  -- 'vt_based' or 'manual'
    created_at       DATETIME,
    updated_at       DATETIME
)
```

### Metrics Table
Stores all calculated metrics (50+ fields).

```sql
metrics (
    metric_id        INTEGER PRIMARY KEY,
    session_id       VARCHAR(36) FOREIGN KEY,
    -- Spirometry
    fvc_best, fvc_predicted, fvc_percent,
    fev1_best, fev1_predicted, fev1_percent,
    -- VO2 & Cardiovascular
    vo2_max, vo2_max_per_kg, peak_hr,
    vt1_hr, vt1_vo2, vt2_hr, vt2_vo2,
    -- Heart Rate Zones
    zone1_start, zone1_end, ... zone5_end,
    -- Metabolic
    rmr_kcal, tdee, fat_max_value,
    -- Nutrition
    protein_g, carbs_g, fat_g, fibre_g,
    weekday_calories, weekend_calories,
    -- Recovery
    cardiac_recovery_pct, metabolic_recovery_pct,
    -- JSON fields for complex data
    zone_analysis_json, oxygenation_metrics_json
)
```

### Supporting Tables
- **UploadedFile**: Tracks all uploaded files per session
- **StaticChart**: References immutable chart images
- **DynamicChart**: References metric-dependent chart images

---

## Services

### MetricsCalculator
Central calculation engine handling:
- Pnoe data preprocessing (rolling averages, derived columns)
- Spirometry metric extraction
- VO2 Max and cardiovascular calculations
- VT1/VT2 threshold detection
- Heart rate zone calculations (VT-based or manual)
- RMR, TDEE, and nutrition macros
- Recovery percentage calculations

### StaticChartGenerator
Generates charts that only change when input data changes:
- Spirometry Z-score horizontal bar chart
- VT/Respiratory multi-panel chart
- Relative VO2 over time
- Fuel utilization (Fat vs CHO)
- VO2 per pulse and breath efficiency
- Recovery comparison chart
- Muscle oxygenation (SmO2) if data available

### DynamicChartTableGenerator
Generates charts/tables that update when metrics are edited:
- Body composition donut chart
- Body fat percentage gauge with ranges
- Metabolism comparison bar chart
- VO2 Max reference table
- Heart Rate Zones table with zone metrics
- Resting Heart Rate reference table

### SpirometerTableExtractor
Uses AI (Gemini via OpenRouter) to:
- Read spirometry PDF documents
- Extract tabular data (FVC, FEV1, etc.)
- Convert to clean CSV format

### UnifiedReportGenerator
Orchestrates the entire report generation:
- Loads session data from database
- Builds page-specific contexts
- Renders Jinja2 templates
- Uses Playwright for HTML→PDF conversion

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | API key for Gemini AI (spirometry extraction) |
| `SECRET_KEY` | Session middleware secret (optional, has default) |

### Activity Level Multipliers (TDEE)

| Level | Multiplier |
|-------|------------|
| Sedentary | 1.2 |
| Light | 1.375 |
| Moderate | 1.55 |
| Active | 1.7 |
| Extreme | 1.9 |

### Zone Calculation Modes

1. **VT-Based** (default): Zones derived from VT1/VT2 thresholds
2. **Manual**: User-specified zone boundaries

---

## Development

### Running in Development Mode
```bash
uv run fastapi dev app/main.py --reload
```

### Running Tests
```bash
# Run from notebooks/test_files for specific module tests
python notebooks/test_files/test_page_5_rmr.py
```

### Jupyter Notebooks
Development notebooks are available in `notebooks/` for:
- Data analysis and exploration
- Chart prototyping
- Zone calculation testing


---

## Support

For issues or feature requests, please contact the development team.
# physiological-report-generator
