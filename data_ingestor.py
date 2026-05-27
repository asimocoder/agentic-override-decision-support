import pandas as pd
from typing import Dict, Literal
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from enum import Enum
from datetime import datetime, date


class SheetClassification(BaseModel):
    classifications: Dict[str, Literal[
        "financial_statements",
        "bureau_data", 
        "banking",
        "emi_table",
        "debtor_creditor",
        "scoring",
        "irrelevant"
    ]]

class DataIngestor:

    def __init__(self):
        self.llm_0 = ChatAnthropic(model="claude-haiku-4-5-20251001", verbose=True)
        self.llm_0_with_structured_output = self.llm_0.with_structured_output(SheetClassification)
    
    def classify_sheets_with_llm(self, sheet_samples) -> Dict:
        # SYSTEM PROMPT REDACTED
        # Classification prompt instructs the LLM to assign each sheet to one of the
        # seven categories defined in SheetClassification. Loaded from config in production.
        system_message = ""

        user_message = f"""Here are the sheet samples:\n {sheet_samples}\n"""
        messages = [SystemMessage(content=system_message), HumanMessage(content=user_message)]
        response = self.llm_0_with_structured_output.invoke(messages)

        return response.classifications
    
    def serialize_value(self, val):
        if isinstance(val, (datetime, date)):
            return val.isoformat()
        return val

    def serialize_key(self, key):
        if isinstance(key, (datetime, date)):
            return key.isoformat()
        return str(key)

    def serialize_records(self, records):
        return [
            {self.serialize_key(k): self.serialize_value(v) for k, v in row.items()}
            for row in records
        ]

    def excel_ingestor(self, state):
        excel_path = state["excel_path"]
        workbook = pd.ExcelFile(excel_path)
        
        # Step 1 — sample all sheets
        sheet_samples = {}
        for sheet_name in workbook.sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
            df = df.dropna(how="all").dropna(axis=1, how="all")
            sheet_samples[sheet_name] = {
                "columns": [self.serialize_key(col) for col in df.columns],
                "row_count": len(df),
                "preview": self.serialize_records(df.head(15).to_dict(orient="records"))
                }
        
        # Step 2 — LLM classifies sheets
        classifications = self.classify_sheets_with_llm(sheet_samples)
        
        # Step 3 — ingest only relevant sheets fully
        relevant_categories = {
            "financial_statements", "bureau_data", 
            "banking", "emi_table", 
            "debtor_creditor", "scoring"
        }
        
        cran_data = {}
        for sheet_name, category in classifications.items():
            if category in relevant_categories:
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
                df = df.dropna(how="all").dropna(axis=1, how="all")
                cran_data[sheet_name] = {
                    "category": category,
                    "data": self.serialize_records(df.to_dict(orient="records"))
                }
        
        return {"cran_data": cran_data}
