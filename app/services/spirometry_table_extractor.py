import base64
import os

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY_REF = os.getenv("OPENROUTER_API_KEY")


def encode_pdf_to_base64(pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        return base64.b64encode(pdf_file.read()).decode("utf-8")


def extract_spirometry_table_from_pdf(pdf_path, output_dir="data"):
    """
    Extract spirometry table from PDF using AI and save as clean CSV.

    Args:
        pdf_path: Path to the spirometry PDF file
        output_dir: Directory to save the extracted CSV

    Returns:
        Path to the saved CSV file
    """
    import csv
    import re
    from pathlib import Path

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY_REF}",
        "Content-Type": "application/json",
    }

    # Read and encode the PDF
    base64_pdf = encode_pdf_to_base64(pdf_path)
    data_url = f"data:application/pdf;base64,{base64_pdf}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Extract the Spirometry table from the pdf and return ONLY the values in CSV format. "
                    "The CSV should have these columns: Parameters,Pre,Best,LLN,Pred.,%Pred.,ZScore\n"
                    "Rules:\n"
                    "1. Do NOT include units in the data (units are part of parameter name)\n"
                    "2. Use empty string for missing values (not '-' or 'N/A')\n"
                    "3. Do NOT add 'csv' markers or code blocks\n"
                    "4. First line should be the header\n"
                    "5. There are 9 columns in total: Parameters (unit), Best, LLN, Pred, %Pred, ZScore, PRE#1, PRE#2, PRE#3\n"
                    "6. I only want the first 3 Rows: FVC, FEV1, FEV1/FVC%\n"
                },
                {
                    "type": "file",
                    "file": {"filename": "document.pdf", "file_data": data_url},
                },
            ],
        }
    ]

    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": messages,
    }

    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()

    if "choices" in response_data and len(response_data["choices"]) > 0:
        content = response_data["choices"][0]["message"]["content"]

        # Clean the content - remove markdown code blocks if present
        content = re.sub(r"```csv\n?", "", content)
        content = re.sub(r"```\n?", "", content)
        content = content.strip()

        # Parse and validate CSV
        lines = content.split("\n")
        if not lines:
            raise ValueError("No data extracted from PDF")

        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        output_file = output_path / "extracted_spirometry_table.csv"

        # Write cleaned CSV with proper formatting
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            # Parse the first line as header
            header_line = lines[0].strip()
            if "," in header_line:
                header = [col.strip() for col in header_line.split(",")]
            else:
                # Default header if not provided
                header = [
                    "Parameters",
                    "Pre",
                    "Best",
                    "LLN",
                    "Pred.",
                    "%Pred.",
                    "ZScore",
                ]

            writer = csv.writer(f)
            writer.writerow(header)

            # Process data rows
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue

                # Split by comma and clean each field
                fields = [field.strip() for field in line.split(",")]

                # Ensure we have the right number of fields
                if len(fields) < len(header):
                    # Pad with empty strings
                    fields.extend([""] * (len(header) - len(fields)))
                elif len(fields) > len(header):
                    # Take only the first N fields
                    fields = fields[: len(header)]

                # Replace '-' or 'N/A' with empty string
                fields = ["" if f in ["-", "N/A", "n/a", "NA"] else f for f in fields]

                writer.writerow(fields)

        return str(output_file)
    else:
        error_msg = response_data.get("error", {}).get("message", "Unknown error")
        raise Exception(f"No content found in response: {error_msg}")
