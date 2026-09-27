import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Application, Document, Service

# Authoritative statutory prerequisite registry aligned with service_dependencies.json
SERVICE_DEPENDENCY_REGISTRY = [
    {
        "from_service": "learner_license",
        "to_service": "driving_license",
        "relationship": "DEPENDS_ON",
        "condition": None,
        "document_type": "learner_licence",
        "evidence_refs": ["EV-KA-DL-005"],
        "status": "VERIFIED",
        "title": "Learner's Licence",
        "description": "Holding an effective Learner's Licence for at least 30 days is legally required before applying for a permanent Driving Licence (Motor Vehicles Act 1988 §9(3), CMVR 1989 Rule 14)."
    },
    {
        "from_service": "death_certificate",
        "to_service": "widow_certificate",
        "relationship": "DEPENDS_ON",
        "condition": None,
        "document_type": "death_certificate",
        "evidence_refs": ["EV-KA-WIDOW-002"],
        "status": "VERIFIED",
        "title": "Death Certificate",
        "description": "Registration of the husband's death and an official Death Certificate is legally required before applying for a Widow Certificate (RBD Act 1969, Karnataka Revenue Department)."
    },
    {
        "from_service": "driving_license",
        "to_service": "learner_license",
        "relationship": "DEPENDS_ON",
        "condition": "transport_vehicle",
        "document_type": "prior_driving_license",
        "evidence_refs": ["EV-KA-LL-002"],
        "status": "VERIFIED",
        "title": "Prior Driving Licence (LMV ≥ 1 Year)",
        "description": "Prior LMV Driving Licence held for at least one year is legally required when applying for a Transport vehicle Learner's Licence (Motor Vehicles Act 1988 §7(1))."
    }
]

# Anti-circular and downstream proof protection rules:
# A downstream certificate must NOT automatically prove or satisfy an upstream prerequisite.
FORBIDDEN_DOWNSTREAM_SUBSTITUTIONS = {
    # e.g., death_certificate cannot be proven by widow_certificate
    "death_certificate": ["widow_certificate"],
    # learner_licence cannot be proven by driving_license for initial issue
    "learner_licence": ["driving_license"],
}


def get_service_prerequisites(service_code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Returns the applicable statutory prerequisites for a given service_code.
    Conditions are evaluated based on the provided context (e.g. vehicle_class).
    """
    applicable = []
    ctx = context or {}
    vehicle_class = str(ctx.get("vehicle_class", "")).lower()
    is_transport = ctx.get("is_transport", False) or "transport" in vehicle_class or "trans" in vehicle_class or "commercial" in vehicle_class

    for dep in SERVICE_DEPENDENCY_REGISTRY:
        if dep["to_service"] != service_code:
            continue

        cond = dep.get("condition")
        if cond is None:
            applicable.append(dep)
        elif cond == "transport_vehicle" and is_transport:
            applicable.append(dep)

    return applicable


async def check_citizen_prerequisites(
    db: AsyncSession,
    citizen_id: uuid.UUID,
    service_code: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates whether a citizen satisfies all prerequisites for a service.
    
    A prerequisite is satisfied ONLY by:
    1. An existing Application for the upstream service in an approved/completed/valid state:
       ('READY_FOR_REVIEW', 'SUBMITTING', 'SUBMITTED', 'TRACKING', 'COMPLETED', 'APPROVED').
    2. An officially verified Document of the prerequisite document_type in the citizen's vault
       with verified == True and verification_status == 'VERIFIED'.
       
    Strict Safety Rules:
    - Arbitrary unverified uploads NEVER satisfy a prerequisite.
    - Downstream certificates NEVER substitute for upstream prerequisites.
    """
    prereqs = get_service_prerequisites(service_code, context)
    if not prereqs:
        return {"satisfied": True, "missing_prerequisites": []}

    missing = []

    for dep in prereqs:
        upstream_service = dep["from_service"]
        required_doc_type = dep.get("document_type")

        # 1. Check upstream application status
        app_query = select(Application).join(Service).where(
            Application.user_id == citizen_id,
            Service.code == upstream_service,
            Application.status.in_([
                "READY_FOR_REVIEW",
                "SUBMITTING",
                "SUBMITTED",
                "TRACKING",
                "COMPLETED",
                "APPROVED"
            ])
        )
        app_res = await db.execute(app_query)
        upstream_app = app_res.scalars().first()

        if upstream_app:
            continue  # Prerequisite satisfied via official upstream application workflow

        # 2. Check verified vault document
        # Ensure downstream documents cannot masquerade as upstream documents
        forbidden = FORBIDDEN_DOWNSTREAM_SUBSTITUTIONS.get(required_doc_type, [])

        doc_query = select(Document).where(
            Document.user_id == citizen_id,
            Document.document_type == required_doc_type,
            Document.verified == True,
            Document.verification_status == "VERIFIED"
        )
        doc_res = await db.execute(doc_query)
        matching_docs = doc_res.scalars().all()

        valid_doc_found = False
        for doc in matching_docs:
            if doc.document_type not in forbidden:
                valid_doc_found = True
                break

        if valid_doc_found:
            continue  # Prerequisite satisfied via verified credential in vault

        # If neither, prerequisite is unmet
        missing.append({
            "service_code": upstream_service,
            "title": dep["title"],
            "description": dep["description"],
            "evidence_refs": dep["evidence_refs"],
            "condition": dep.get("condition")
        })

    if missing:
        return {
            "satisfied": False,
            "missing_prerequisites": missing,
            "primary_prerequisite": missing[0]
        }

    return {"satisfied": True, "missing_prerequisites": []}
