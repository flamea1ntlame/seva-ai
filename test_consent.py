import asyncio
import os
import sys
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.database import AsyncSessionLocal
from app.models import User, Service, Application, Document, Consent
from sqlalchemy import select
from app.agent.tools import tool_create_application, tool_request_consent, tool_submit_application
from app.documents.extract import extract_document_fields

# We will manipulate the DB directly for test cases.
async def setup_app(db, service_code, citizen_id):
    # Create app
    app_res = await tool_create_application(db, service_code, citizen_id)
    app_id = app_res["application_id"]
    
    # Upload docs
    service = (await db.execute(select(Service).where(Service.code == service_code))).scalar_one()
    for dtype in service.required_documents:
        doc = Document(
            id=uuid.uuid4(),
            user_id=uuid.UUID(citizen_id),
            application_id=uuid.UUID(app_id),
            document_type=dtype,
            title=dtype,
            file_path="mock",
            file_size=10,
            mime_type="text/plain",
            verified=True,
            verification_status="VERIFIED",
            extracted_data={
                "name": "Test User",
                "dob": "2000-01-01",
                "address": "Test",
                "id_number": "123",
                "annual_income": 1000,
                "employer": "Test",
                "applicant_name": "Test",
                "date_of_birth": "2000-01-01",
                "place_of_birth": "Test",
                "mother_name": "Test",
                "father_name": "Test",
                "blood_group": "O+",
                "fitness_confirmed": True,
                "occupation": "Test",
                "vehicle_class": "LMV"
            }
        )
        db.add(doc)
    await db.commit()
    
    # Advance state to READY_FOR_REVIEW
    from app.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db)
    await engine.advance_application(uuid.UUID(app_id))
    
    # Create consent
    consent_res = await tool_request_consent(db, app_id, ["dummy"], service.department, "test")
    if "error" in consent_res:
        print("CONSENT ERROR:", consent_res)
    consent_id = consent_res["consent_id"]
    
    # Approve consent
    consent = (await db.execute(select(Consent).where(Consent.id == uuid.UUID(consent_id)))).scalar_one()
    consent.status = "APPROVED"
    await db.commit()
    
    return app_id

async def clear_db(db):
    await db.execute(Document.__table__.delete())
    await db.execute(Application.__table__.delete())
    await db.commit()

async def run_tests():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == "citizen@example.com"))).scalar_one()
        user_id = str(user.id)
        
        # Case 1: Normal
        await clear_db(db)
        print("CASE 1: Normal")
        app_id = await setup_app(db, "income_certificate", user_id)
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" not in res
        
        # Case 2: Change form_data after consent
        await clear_db(db)
        print("\nCASE 2: Change form_data (extracted_data) after consent")
        app_id = await setup_app(db, "income_certificate", user_id)
        docs = (await db.execute(select(Document).where(Document.application_id == uuid.UUID(app_id)))).scalars().all()
        # modify extracted data which influences form_data
        for doc in docs:
            doc.extracted_data = {"name": "Hacked Name"}
        await db.commit()
        # advance application checks if data changed and invalidates consent
        from app.workflows.engine import WorkflowEngine
        await WorkflowEngine(db).advance_application(uuid.UUID(app_id))
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" in res
        
        # Case 3: Replace document after consent
        await clear_db(db)
        print("\nCASE 3: Replace document")
        app_id = await setup_app(db, "income_certificate", user_id)
        docs = (await db.execute(select(Document).where(Document.application_id == uuid.UUID(app_id)))).scalars().all()
        old_id = docs[0].id
        doc_type = docs[0].document_type
        await db.delete(docs[0])
        new_doc = Document(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            application_id=uuid.UUID(app_id),
            document_type=doc_type,
            title="Replaced",
            file_path="mock2",
            file_size=20,
            mime_type="text/plain",
            verified=True,
            verification_status="VERIFIED",
            extracted_data={
                "name": "Test User",
                "dob": "2000-01-01",
                "address": "Test",
                "id_number": "123",
                "annual_income": 1000,
                "employer": "Test",
                "applicant_name": "Test",
                "date_of_birth": "2000-01-01",
                "place_of_birth": "Test",
                "mother_name": "Test",
                "father_name": "Test",
                "blood_group": "O+",
                "fitness_confirmed": True,
                "occupation": "Test",
                "vehicle_class": "LMV"
            }
        )
        db.add(new_doc)
        await db.commit()
        await WorkflowEngine(db).advance_application(uuid.UUID(app_id))
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" in res
        
        # Case 4: Delete document after consent
        await clear_db(db)
        print("\nCASE 4: Delete document")
        app_id = await setup_app(db, "income_certificate", user_id)
        docs = (await db.execute(select(Document).where(Document.application_id == uuid.UUID(app_id)))).scalars().all()
        await db.delete(docs[0])
        await db.commit()
        await WorkflowEngine(db).advance_application(uuid.UUID(app_id))
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" in res
        
        # Case 5: Unchanged
        await clear_db(db)
        print("\nCASE 5: Unchanged")
        app_id = await setup_app(db, "income_certificate", user_id)
        await WorkflowEngine(db).advance_application(uuid.UUID(app_id))
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" not in res
        
        # Case 6: 3 Services
        await clear_db(db)
        print("\nCASE 6: Birth Certificate")
        app_id = await setup_app(db, "birth_certificate", user_id)
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" not in res
        
        await clear_db(db)
        print("\nCASE 6: Driving Licence")
        app_id = await setup_app(db, "driving_license", user_id)
        res = await tool_submit_application(db, app_id)
        print("Result:", res)
        assert "error" not in res
        
if __name__ == "__main__":
    asyncio.run(run_tests())
