from services.engine import QualityEngine 
from services.llm import LLMService

from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io

from fastapi import Response

router = APIRouter()

@router.post("/analyze")
async def analyze_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    try:
        contents = await file.read()
        
        # 1. OPTIMIZATION: Try the lightning-fast C engine first
        try:
            df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
        except Exception:
            # Fallback for weird delimiters or encodings only if necessary
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df = df.dropna(axis=1, how='all')

        # 2. EDGE CASE PREVENTION: Stop if the file is empty or just headers
        if df.empty or len(df) == 0:
            raise HTTPException(status_code=400, detail="The uploaded CSV contains no data rows.")

        # Run the inspection engine
        raw_report = QualityEngine.run(df, file.filename)
        final_report = LLMService.enhance_report(raw_report)
        
        return final_report
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
@router.post("/autofix")
async def autofix_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    try:
        contents = await file.read()
        
        # 1. Load data into Pandas
        try:
            df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
        except Exception:
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine='python', encoding='latin1', on_bad_lines='skip')

        # --- THE LIGHTNING FAST "AUTO-FIX" ENGINE ---
        for col in df.columns:
            # Fix 1: Strip hidden whitespaces from all text columns
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

            # Fix 2: Standardize casing for Name columns (Title Case)
            col_lower = str(col).lower()
            if 'name' in col_lower or 'first' in col_lower or 'last' in col_lower:
                df[col] = df[col].apply(lambda x: x.title() if isinstance(x, str) else x)

            # Fix 3: Impute (fill in) Missing Values logically
            if df[col].isnull().any():
                if df[col].dtype == 'object':
                    # If it's an email column, put a placeholder
                    if 'email' in col_lower:
                        df[col] = df[col].fillna('unknown@missing.com')
                    else:
                        df[col] = df[col].fillna('Unknown')
                else:
                    # For numeric columns (like Age or Salary), fill with 0
                    df[col] = df[col].fillna(0)

        # --------------------------------------------

        # 2. Convert back to CSV string safely
        output = io.StringIO()
        df.to_csv(output, index=False)
        cleaned_csv_string = output.getvalue()
        
        return Response(content=cleaned_csv_string, media_type="text/csv")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fixing file: {str(e)}")