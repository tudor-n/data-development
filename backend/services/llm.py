import json
import logging
import os

from dotenv import load_dotenv
from pydantic import BaseModel

from models.schemas import QualityReport

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error("Failed to initialise Gemini client: %s", e)
else:
    logger.warning("GEMINI_API_KEY not set — LLM features disabled.")


class AISummaryResponse(BaseModel):
    executive_summary: str


class LLMService:
    @staticmethod
    def enhance_report(report: QualityReport) -> QualityReport:
        if not report.issues:
            report.executive_summary = "Perfect dataset — no quality issues detected."
            return report

        if not client:
            report.executive_summary = "AI summary unavailable: GEMINI_API_KEY is not configured."
            return report

        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        sorted_issues = sorted(report.issues, key=lambda i: severity_rank.get(i.severity.lower(), 3))
        top_issues = sorted_issues[:30]

        lines = [
            f"- {i.severity.upper()}: {i.inspector_name} found {i.count} issues in '{i.column}'."
            for i in top_issues
        ]
        context = "\n".join(lines)
        if len(report.issues) > 30:
            context += f"\n...and {len(report.issues) - 30} more minor issues."

        prompt = (
            "You are a Data Engineer. Write a concise 2-sentence executive summary about this "
            f"dataset's quality based on the following issues:\n{context}\n"
        )

        try:
            from google.genai import types
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
            logger.exception("Gemini error: %s", e)
            report.executive_summary = "AI summary unavailable due to an error."

        return report

    @staticmethod
    def auto_fix_csv(csv_data: str) -> str:
        if not client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        prompt = (
            "You are an expert Data Engineer AI. Clean the following messy CSV dataset.\n"
            "Rules:\n"
            "1. Fix inconsistent capitalisation (names → Title Case).\n"
            "2. Remove leading/trailing whitespace.\n"
            "3. Replace missing values with a logical placeholder.\n"
            "4. Do NOT change column headers.\n"
            "5. Do NOT add or remove rows.\n"
            "Return ONLY the valid cleaned CSV. No markdown fences.\n\n"
            f"{csv_data}"
        )

        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            cleaned = response.text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            return cleaned.strip()
        except Exception as e:
            logger.exception("Auto-fix error: %s", e)
            raise ValueError(f"AI auto-fix failed: {e}")