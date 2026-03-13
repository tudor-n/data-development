from google import genai
from google.genai import types
from pydantic import BaseModel
from models.schemas import QualityReport
from dotenv import load_dotenv
import os
import json
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")


if not api_key:
    logger.critical("GEMINI_API_KEY is missing. Application cannot start.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

class AISummaryResponse(BaseModel):
    executive_summary: str

class LLMService:
    @staticmethod
    def enhance_report(report: QualityReport) -> QualityReport:
        # If dataset is perfect, skip the LLM call
        if not report.issues:
            report.executive_summary = "Perfect dataset! No quality issues detected."
            return report

        # Fallback for missing/dummy API key
        if not api_key or api_key == "your_gemini_api_key_here":
            report.executive_summary = "[Demo Mode] Please configure your GEMINI_API_KEY in the backend/.env file to see AI-generated insights."
            return report

        # Sort issues by severity (critical first) and only send the top 30 to the LLM
        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        sorted_issues = sorted(
            report.issues,
            key=lambda i: severity_rank.get(i.severity.lower(), 3)
        )
        top_issues = sorted_issues[:30]

        issue_descriptions = [
            f"- {i.severity.upper()}: {i.inspector_name} found {i.count} issues in '{i.column}'."
            for i in top_issues
        ]
        prompt_context = "\n".join(issue_descriptions)

        if len(report.issues) > 30:
            prompt_context += f"\n...and {len(report.issues) - 30} more minor issues."

        prompt = f"""You are a Data Engineer. Write a concise, 2 sentence executive summary about this dataset's quality based on the following issues:
{prompt_context}
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AISummaryResponse,
                ),
            )
            result = json.loads(response.text)
            report.executive_summary = result.get("executive_summary", "Summary generation failed.")
        except Exception as e:
            logger.exception(f"Error communicating with Gemini: {str(e)}")
            report.executive_summary = "AI Summary unavailable due to an error."

        return report

    @staticmethod
    def auto_fix_csv(csv_data: str) -> str:
        """Sends the raw CSV to Gemini and asks it to clean the data."""
        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError("API key not configured for Auto-Fix.")

        prompt = f"""You are an expert Data Engineer AI. I am going to give you a messy dataset in CSV format.
Your job is to clean the dataset based on these strict rules:
1. Fix any inconsistent capitalization (e.g., standardise names to Title Case).
2. Remove any invisible leading/trailing whitespace.
3. If a numeric or email column has a missing value, replace it with a logical placeholder (e.g., "Unknown" for text, or an average/0 for numbers).
4. Do NOT change the column headers.
5. Do NOT add or remove rows.

Return ONLY the valid, cleaned CSV text. Do not include markdown formatting like ```csv or ```. Just the raw CSV text.

Here is the messy data:
{csv_data}
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            cleaned_csv = response.text.strip()

            # Strip markdown if the LLM accidentally includes it
            if cleaned_csv.startswith("```"):
                cleaned_csv = cleaned_csv.split("\n", 1)[1]
            if cleaned_csv.endswith("```"):
                cleaned_csv = cleaned_csv.rsplit("\n", 1)[0]

            return cleaned_csv.strip()
        except Exception as e:
            logger.exception(f"Error during Auto-Fix: {str(e)}")
            raise ValueError(f"AI Auto-Fix failed: {str(e)}")