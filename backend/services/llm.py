import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
from pydantic import BaseModel
from json import JSONDecodeError
from models.schemas import QualityReport
from dotenv import load_dotenv
import os
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    logger.critical("GEMINI_API_KEY is missing. Application cannot start.")
    sys.exit(1)

genai.configure(api_key=api_key)

class AISummaryResponse(BaseModel):
    executive_summary: str

class LLMService:
    @staticmethod
    def enhance_report(report: QualityReport) -> QualityReport:
        if not report.issues:
            report.executive_summary = "Perfect dataset! No quality issues detected."
            return report
        
        issue_descriptions = [f"- {i.severity.upper()}: {i.inspector_name} found {i.count} issues in '{i.column}'." for i in report.issues]
        prompt_context = "\n".join(issue_descriptions)
        
        prompt = f""" You are a Data Engineer. Write a concise, 2 sentence executive summary about this dataset's quality based on the following issue:
        {prompt_context}
        """


        if not api_key or api_key == "your_gemini_api_key_here":
            report.executive_summary = "[Demo Mode] Please configure your GEMINI_API_KEY in the backend/.env file to see AI-generated insights."
            return report

        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AISummaryResponse,
                ),
            )

            result = json.loads(response.text)
            report.executive_summary = result.get(
                "executive_summary",
                "Summary generation failed."
            )

        except Exception as e:
            logger.exception(f"Error communicating with Gemini: {str(e)}")
            report.executive_summary = "AI Summary unavailable due to an error."

        return report