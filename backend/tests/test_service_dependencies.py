import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Service, User, Application, Document
from app.agent.tools import tool_create_application, tool_get_service_requirements
from app.agent.dependencies import check_citizen_prerequisites, get_service_prerequisites


@pytest.fixture
async def setup_test_services(db_session: AsyncSession):
    services = [
        Service(
            code="driving_license",
            title="Driving Licence",
            department="transport",
            description="Permanent driving licence",
            required_documents=["age_proof", "address_proof", "passport_photo", "application_form", "self_declaration", "learner_licence"],
            required_fields=["date_of_birth", "vehicle_class"],
            processing_time_days=30,
            fee_amount=200.0,
            is_active=True,
        ),
        Service(
            code="learner_license",
            title="Learner's Licence",
            department="transport",
            description="Learner licence",
            required_documents=["age_proof", "address_proof", "passport_photo", "application_form"],
            required_fields=["date_of_birth", "vehicle_class"],
            processing_time_days=7,
            fee_amount=150.0,
            is_active=True,
        ),
        Service(
            code="death_certificate",
            title="Death Certificate",
            department="revenue",
            description="Death registration certificate",
            required_documents=["identity_proof"],
            required_fields=["deceased_name", "date_of_death"],
            processing_time_days=21,
            fee_amount=0.0,
            is_active=True,
        ),
        Service(
            code="widow_certificate",
            title="Widow Certificate",
            department="revenue",
            description="Certificate for widow benefits",
            required_documents=["death_certificate"],
            required_fields=["husband_name"],
            processing_time_days=20,
            fee_amount=0.0,
            is_active=True,
        ),
        Service(
            code="income_certificate",
            title="Income Certificate",
            department="revenue",
            description="Official annual income certificate",
            required_documents=["aadhaar", "address_proof", "income_proof"],
            required_fields=["annual_income", "occupation"],
            processing_time_days=21,
            fee_amount=15.0,
            is_active=True,
        ),
        Service(
            code="agriculturist_certificate",
            title="Agriculturist Certificate",
            department="revenue",
            description="Quarantined stub service",
            required_documents=["unknown_requirements"],
            required_fields=[],
            processing_time_days=7,
            fee_amount=0.0,
            is_active=True,
        ),
        Service(
            code="birth_certificate",
            title="Birth Certificate",
            department="revenue",
            description="Official birth certificate",
            required_documents=[],
            required_fields=["child_name", "date_of_birth"],
            processing_time_days=21,
            fee_amount=0.0,
            is_active=True,
        ),
    ]
    for s in services:
        db_session.add(s)
    await db_session.commit()
    return {s.code: s for s in services}


@pytest.fixture
async def citizen_user(db_session: AsyncSession):
    user = User(
        email="citizen_test@example.com",
        full_name="Citizen Tester",
        password_hash="hashed_pw",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# TEST 1: User requests Driving Licence. No Learner Licence. -> Downstream application NOT created.
@pytest.mark.asyncio
async def test_1_dl_without_ll_blocked(db_session: AsyncSession, setup_test_services, citizen_user):
    res = await tool_create_application(db_session, "driving_license", str(citizen_user.id))
    assert "error" in res
    assert res["error"] == "PREREQUISITE_NOT_MET"
    assert res["prerequisite_service"] == "learner_license"
    assert "Learner's Licence" in res["message"]

    # Verify no downstream application exists in database
    dl_service = setup_test_services["driving_license"]
    app_query = select(Application).where(Application.user_id == citizen_user.id, Application.service_id == dl_service.id)
    apps = (await db_session.execute(app_query)).scalars().all()
    assert len(apps) == 0


# TEST 2: User requests Driving Licence. Valid/completed Learner Licence exists. -> Downstream application proceeds.
@pytest.mark.asyncio
async def test_2_dl_with_valid_ll_proceeds(db_session: AsyncSession, setup_test_services, citizen_user):
    ll_service = setup_test_services["learner_license"]
    # Provide completed Learner Licence application
    ll_app = Application(
        application_number="SEVA-LL-123456",
        user_id=citizen_user.id,
        service_id=ll_service.id,
        status="COMPLETED",
        form_data={"vehicle_class": "LMV"},
    )
    db_session.add(ll_app)
    await db_session.commit()

    res = await tool_create_application(db_session, "driving_license", str(citizen_user.id))
    assert "application_id" in res
    assert res["service_code"] == "driving_license"
    assert res["application_number"].startswith("SEVA-")


# TEST 3: User requests Learner Licence. MCWOG age 16, <=50cc. -> parent/guardian consent condition applies.
def test_3_ll_minor_consent_condition_applies():
    reqs = tool_get_service_requirements
    # Check conditional rules from learner_license.json
    import json, os
    kb_path = "service_catalog/services/karnataka/learner_license.json"
    if not os.path.exists(kb_path):
        kb_path = os.path.join(os.path.dirname(__file__), "..", "..", "service_catalog", "services", "karnataka", "learner_license.json")
    data = json.load(open(kb_path))
    consent_req = next(r for r in data["requirements"] if r.get("document") == "parent_guardian_consent")
    assert consent_req["type"] == "CONDITIONAL"
    assert "16 and 18" in consent_req["condition_description"]
    assert "<= 50cc" in consent_req["condition_description"]


# TEST 4: User requests Learner Licence. MCWOG age 16, >50cc. -> must NOT incorrectly allow the <=50cc minor rule.
def test_4_ll_minor_over_50cc_disallowed():
    import json, os
    kb_path = "service_catalog/services/karnataka/learner_license.json"
    if not os.path.exists(kb_path):
        kb_path = os.path.join(os.path.dirname(__file__), "..", "..", "service_catalog", "services", "karnataka", "learner_license.json")
    data = json.load(open(kb_path))
    consent_req = next(r for r in data["requirements"] if r.get("document") == "parent_guardian_consent")
    # Condition explicitly specifies MCWOG <= 50cc; motor vehicles > 50cc require age >= 18 under §4(1)
    desc = consent_req["condition_description"]
    assert "<= 50cc" in desc
    assert "> 50cc" not in desc


# TEST 5: User requests Transport Learner Licence. No qualifying prior LMV licence. -> prerequisite failure.
@pytest.mark.asyncio
async def test_5_transport_ll_without_prior_lmv_fails(db_session: AsyncSession, setup_test_services, citizen_user):
    context = {"vehicle_class": "Transport", "is_transport": True}
    res = await tool_create_application(db_session, "learner_license", str(citizen_user.id), context=context)
    assert "error" in res
    assert res["error"] == "PREREQUISITE_NOT_MET"
    assert res["prerequisite_service"] == "driving_license"


# TEST 6: User requests Transport Learner Licence. Qualifying LMV licence >=1 year. -> condition satisfied.
@pytest.mark.asyncio
async def test_6_transport_ll_with_prior_lmv_satisfied(db_session: AsyncSession, setup_test_services, citizen_user):
    # Citizen possesses verified prior_driving_license document in vault
    doc = Document(
        user_id=citizen_user.id,
        document_type="prior_driving_license",
        title="Prior LMV Driving Licence",
        file_path="documents/mock_dl.pdf",
        verified=True,
        verification_status="VERIFIED",
    )
    db_session.add(doc)
    await db_session.commit()

    context = {"vehicle_class": "Transport", "is_transport": True}
    res = await tool_create_application(db_session, "learner_license", str(citizen_user.id), context=context)
    assert "application_id" in res
    assert res["service_code"] == "learner_license"


# TEST 7: Widow Certificate. No Death Certificate. -> downstream application blocked / prerequisite requested.
@pytest.mark.asyncio
async def test_7_widow_cert_without_death_cert_blocked(db_session: AsyncSession, setup_test_services, citizen_user):
    res = await tool_create_application(db_session, "widow_certificate", str(citizen_user.id))
    assert "error" in res
    assert res["error"] == "PREREQUISITE_NOT_MET"
    assert res["prerequisite_service"] == "death_certificate"


# TEST 8: Widow Certificate. Death Certificate exists/completed. -> application may proceed.
@pytest.mark.asyncio
async def test_8_widow_cert_with_death_cert_proceeds(db_session: AsyncSession, setup_test_services, citizen_user):
    doc = Document(
        user_id=citizen_user.id,
        document_type="death_certificate",
        title="Husband's Death Certificate",
        file_path="documents/mock_death.pdf",
        verified=True,
        verification_status="VERIFIED",
    )
    db_session.add(doc)
    await db_session.commit()

    res = await tool_create_application(db_session, "widow_certificate", str(citizen_user.id))
    assert "application_id" in res
    assert res["service_code"] == "widow_certificate"


# TEST 9: Downstream certificate cannot satisfy upstream prerequisite automatically.
@pytest.mark.asyncio
async def test_9_downstream_cannot_satisfy_upstream(db_session: AsyncSession, setup_test_services, citizen_user):
    # Having a widow certificate cannot satisfy the death certificate prerequisite for another workflow
    doc = Document(
        user_id=citizen_user.id,
        document_type="widow_certificate",
        title="Widow Certificate",
        file_path="documents/mock_widow.pdf",
        verified=True,
        verification_status="VERIFIED",
    )
    db_session.add(doc)
    await db_session.commit()

    # Checking prerequisite for a service depending on death_certificate must still fail
    prereq_res = await check_citizen_prerequisites(db_session, citizen_user.id, "widow_certificate")
    assert not prereq_res["satisfied"]
    assert prereq_res["primary_prerequisite"]["service_code"] == "death_certificate"


# TEST 10: UNKNOWN / DO_NOT_EXPOSE KB rules never appear as citizen requirements.
@pytest.mark.asyncio
async def test_10_unknown_quarantined_not_exposed(db_session: AsyncSession, setup_test_services):
    # Check agriculturist_certificate which only has unknown_requirements
    reqs = await tool_get_service_requirements(db_session, "agriculturist_certificate")
    assert "unknown_requirements" not in reqs["required_documents"]
    assert len(reqs["required_documents"]) == 0

    # Check birth_certificate where identity_proof is UNKNOWN / DO_NOT_EXPOSE
    bc_reqs = await tool_get_service_requirements(db_session, "birth_certificate")
    assert "identity_proof" not in bc_reqs["required_documents"]


# TEST 11: Existing normal services without dependencies continue working.
@pytest.mark.asyncio
async def test_11_normal_services_continue_working(db_session: AsyncSession, setup_test_services, citizen_user):
    res = await tool_create_application(db_session, "income_certificate", str(citizen_user.id))
    assert "application_id" in res
    assert res["service_code"] == "income_certificate"
    assert res["current_status"] in ["DISCOVER", "COLLECTING_DOCUMENTS"]


# TEST 12: No duplicate applications are created while prerequisite routing is occurring.
@pytest.mark.asyncio
async def test_12_no_duplicate_applications_created(db_session: AsyncSession, setup_test_services, citizen_user):
    # First application creation
    res1 = await tool_create_application(db_session, "income_certificate", str(citizen_user.id))
    app_id_1 = res1["application_id"]

    # Second call for the same service while in active workflow
    res2 = await tool_create_application(db_session, "income_certificate", str(citizen_user.id))
    app_id_2 = res2["application_id"]

    # Must reuse the active application ID, preventing duplicate records
    assert app_id_1 == app_id_2

    # Query DB to guarantee count is exactly 1
    income_service = setup_test_services["income_certificate"]
    app_query = select(Application).where(Application.user_id == citizen_user.id, Application.service_id == income_service.id)
    apps = (await db_session.execute(app_query)).scalars().all()
    assert len(apps) == 1
