import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.agent.orchestrator import run_agent_workflow
from app.config import settings
from app.documents.extract import extract_document_fields

async def run_smoke_test():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set in environment.")
        sys.exit(1)
    
    settings.GEMINI_API_KEY = api_key
    settings.GEMINI_MODEL = "gemini-2.5-flash"
    
    print(f"Starting Gemini Smoke Test with model: {settings.GEMINI_MODEL}")
    
    mock_db = AsyncMock(spec=AsyncSession)
    
    citizen_id = "smoke-test-citizen-id"
    message = "I want to apply for an Income Certificate."
    
    print("User Message:", message)
    print("Executing workflow...")
    
    try:
        result = await run_agent_workflow(message, citizen_id, mock_db)
        print("\n--- Workflow Result ---")
        for k, v in result.items():
            print(f"{k}: {v}")
        print("-----------------------")
        
        if result.get("service_code") == "SVC-INC-01":
            print("SUCCESS: Target service code extracted correctly via tool call.")
        else:
            print("WARNING: Service code not extracted as expected. Found:", result.get("service_code"))
            
    except Exception as e:
        print(f"Test failed with exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
