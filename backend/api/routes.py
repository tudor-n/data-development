from services.engine import QualityEngine 
from services.llm import LLMService

from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
router = APIRouter()

@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File (...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        try:
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', encoding='latin1')

        raw_report = QualityEngine.run(df, file.filename)
        
        final_report = LLMService.enhance_report(raw_report)
        
        return final_report
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    