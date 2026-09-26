"""
SEVA AI - Authoritative Government Service Rules Engine & Protocol

This module provides the protocol and default provider for official government service requirements,
acceptable alternative documents, document dependencies, responsible authorities, and jurisdiction rules.

PERSON 3 DECOUPLING:
An explicit async protocol `ServiceRulesProvider` is defined below. Person 3 can implement a database-backed
or external registry provider conforming to this protocol without altering the chatbot orchestrator.
"""

from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class ServiceRulesProvider(Protocol):
    """
    Protocol for authoritative government service rules retrieval.
    Enables Person 3 to swap this in-memory provider with a database-backed rules engine.
    """
    async def get_requirements(
        self,
        service_code: str,
        jurisdiction: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        ...

    async def evaluate_citizen_readiness(
        self,
        service_code: str,
        uploaded_doc_types: List[str],
        extracted_fields: Dict[str, Any],
        jurisdiction: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        ...


# Document Semantic Satisfaction & Alias Rules
# Legitimate parent identity documents (Voter ID, Aadhaar, Passport) can satisfy 'parent_identity_proof'.
# A child's identity CANNOT satisfy proof of birth or parent's identity.
DOCUMENT_SATISFACTION_RULES: Dict[str, Dict[str, Any]] = {
    "parent_identity_proof": {
        "description": "Proof of identity of child's father or mother",
        "category": "PARENT_IDENTITY",
        "allowed_subtypes": [
            "parent_identity_proof",
            "identity_proof",
            "aadhaar",
            "aadhaar_card",
            "voter_id",
            "passport",
            "pan_card",
            "driving_license"
        ],
        "prohibited_subtypes": ["child_aadhaar", "child_identity_proof"]
    },
    "hospital_certificate": {
        "description": "Institutional birth notification or discharge summary",
        "category": "PROOF_OF_BIRTH",
        "allowed_subtypes": [
            "hospital_certificate",
            "birth_notification",
            "discharge_summary",
            "institutional_birth_report",
            "form_1"
        ],
        "prohibited_subtypes": ["child_aadhaar", "identity_proof"]
    },
    "identity_proof": {
        "description": "Official government identity proof of the applicant",
        "category": "APPLICANT_IDENTITY",
        "allowed_subtypes": [
            "identity_proof",
            "aadhaar",
            "aadhaar_card",
            "voter_id",
            "passport",
            "pan",
            "pan_card",
            "driving_license"
        ],
        "prohibited_subtypes": []
    },
    "address_proof": {
        "description": "Proof of current residential address",
        "category": "PROOF_OF_ADDRESS",
        "allowed_subtypes": [
            "address_proof",
            "utility_bill",
            "electricity_bill",
            "water_bill",
            "ration_card",
            "domicile_certificate",
            "passport",
            "bank_passbook"
        ],
        "prohibited_subtypes": []
    },
    "income_proof": {
        "description": "Authoritative evidence of annual family earnings",
        "category": "PROOF_OF_INCOME",
        "allowed_subtypes": [
            "income_proof",
            "salary_slip",
            "salary_slips",
            "form_16",
            "itr",
            "income_affidavit",
            "agricultural_assessment",
            "land_assessment"
        ],
        "prohibited_subtypes": []
    },
    "photograph": {
        "description": "Recent passport size photograph of the applicant",
        "category": "BIOMETRIC_PHOTO",
        "allowed_subtypes": ["photograph", "photo", "passport_photo"],
        "prohibited_subtypes": []
    },
    "medical_declaration": {
        "description": "Physical fitness self-declaration or doctor medical certificate",
        "category": "MEDICAL_FITNESS",
        "allowed_subtypes": ["medical_declaration", "fitness_certificate", "form_1", "form_1a"],
        "prohibited_subtypes": []
    }
}


def is_requirement_satisfied(required_type: str, uploaded_doc_types: List[str]) -> bool:
    """
    Checks if any uploaded document satisfies the required type based on
    semantic document category and legal alias rules.
    """
    rule = DOCUMENT_SATISFACTION_RULES.get(required_type)
    if not rule:
        return required_type in uploaded_doc_types

    allowed = set(s.lower() for s in rule["allowed_subtypes"])
    prohibited = set(s.lower() for s in rule["prohibited_subtypes"])

    for uploaded in uploaded_doc_types:
        u_clean = uploaded.strip().lower()
        if u_clean in allowed and u_clean not in prohibited:
            return True

    return False


# Structured government service rules database
SERVICE_RULES: Dict[str, Dict[str, Any]] = {
    "income_certificate": {
        "service_code": "income_certificate",
        "service_name": "Income Certificate",
        "department": "revenue",
        "title": "Income Certificate",
        "description": "Official government certificate verifying annual family income for welfare schemes, educational fee concessions, and scholarships.",
        "responsible_authority": {
            "title": "Tahsildar / Taluk Revenue Officer",
            "office": "Taluk Office / Revenue Department",
            "appeal_authority": "Assistant Commissioner / Sub-Divisional Magistrate (SDM)"
        },
        "required_documents": ["identity_proof", "address_proof", "income_proof"],
        "required_fields": ["annual_income", "occupation"],
        "processing_time_days": 7,
        "fee_amount": 50.00,
        "document_options": {
            "identity_proof": [
                {"name": "Aadhaar Card", "authority": "UIDAI", "digital_verify": True},
                {"name": "Voter ID Card (EPIC)", "authority": "Election Commission of India", "digital_verify": True},
                {"name": "PAN Card", "authority": "Income Tax Department", "digital_verify": True},
                {"name": "Passport", "authority": "Ministry of External Affairs", "digital_verify": True}
            ],
            "address_proof": [
                {"name": "Electricity / Water Utility Bill (last 3 months)", "authority": "State DISCOM / Municipal Board"},
                {"name": "Ration Card (BPL / AAY / PHH)", "authority": "Food & Civil Supplies Department"},
                {"name": "Domicile / Residence Certificate", "authority": "Revenue Department"},
                {"name": "Bank Passbook with photo & address", "authority": "Scheduled Commercial Bank"}
            ],
            "income_proof": [
                {"name": "Salary Slips (last 3 months with employer seal)", "authority": "Employer HR / Payroll"},
                {"name": "Form 16 / Income Tax Return (ITR) Acknowledgment", "authority": "Income Tax Department"},
                {"name": "Income Affidavit on Non-Judicial Stamp Paper", "authority": "Executive Magistrate / Notary Public"},
                {"name": "Agricultural / Land Holding Revenue Assessment", "authority": "Village Accountant / Revenue Inspector"}
            ]
        },
        "document_dependencies": [
            {
                "rule": "income_proof_requires_source",
                "description": "Income proof must correspond to the declared occupation (e.g. Salary Slip for salaried, Form 16 / Affidavit for self-employed/business)."
            }
        ],
        "jurisdictions": {
            "default": {
                "portal": "State Revenue Citizen Services Portal",
                "validity_period": "1 Year from date of issue"
            },
            "karnataka": {
                "portal": "Nadakacheri / Seva Sindhu",
                "officer": "Tahsildar, Taluk Office",
                "validity_period": "1 Year"
            },
            "maharashtra": {
                "portal": "Aaple Sarkar (MahaOnline)",
                "officer": "Tahsildar / Sub-Divisional Officer",
                "validity_period": "1 Year"
            },
            "delhi": {
                "portal": "e-District Delhi",
                "officer": "Sub-Divisional Magistrate (SDM)",
                "validity_period": "6 Months to 1 Year"
            }
        },
        "scholarship_guidance": "Scholarships and educational concessions require an Income Certificate from the Revenue Department to verify that family income is within the prescribed eligibility ceiling."
    },
    "birth_certificate": {
        "service_code": "birth_certificate",
        "service_name": "Birth Certificate",
        "department": "municipal",
        "title": "Birth Certificate",
        "description": "Official legal record of birth registration issued under the Registration of Births and Deaths Act.",
        "responsible_authority": {
            "title": "Registrar of Births & Deaths / Municipal Health Officer",
            "office": "Civil Registration System (CRS) / Municipal Corporation / Gram Panchayat",
            "appeal_authority": "Chief Registrar of Births and Deaths"
        },
        "required_documents": ["hospital_certificate", "parent_identity_proof"],
        "required_fields": ["applicant_name", "date_of_birth", "place_of_birth", "father_name", "mother_name"],
        "processing_time_days": 5,
        "fee_amount": 30.00,
        "document_options": {
            "hospital_certificate": [
                {"name": "Institutional Birth Report / Discharge Summary", "authority": "Hospital / Medical Center"},
                {"name": "Form 1 (Birth Notification) signed by Hospital Authority", "authority": "Hospital Registrar"},
                {"name": "Doctor / Medical Practitioner Affidavit (for home births)", "authority": "Notary Public & ANM/ASHA Report"}
            ],
            "parent_identity_proof": [
                {"name": "Parent's Voter ID", "authority": "Election Commission of India"},
                {"name": "Parent's Aadhaar Card", "authority": "UIDAI"},
                {"name": "Parent's Passport", "authority": "Ministry of External Affairs"},
                {"name": "Parent's PAN Card", "authority": "Income Tax Department"}
            ]
        },
        "document_dependencies": [
            {
                "rule": "no_child_aadhaar_required_for_birth_registration",
                "description": "A newborn or child birth certificate CANNOT depend on the child's Aadhaar. Aadhaar for a newborn is obtained subsequent to birth registration using the Birth Certificate as primary evidence."
            },
            {
                "rule": "parent_id_suffices",
                "description": "Either parent's official identity proof is legally sufficient for registration."
            }
        ],
        "jurisdictions": {
            "default": {
                "portal": "Civil Registration System (CRS) / Municipal Corporation Portal",
                "registration_window": "Within 21 days of birth without late fee"
            },
            "karnataka": {
                "portal": "e-JanMa (Registrar General of Births & Deaths Karnataka)",
                "officer": "Medical Officer of Health (BBMP) / Village Accountant",
                "registration_window": "21 days"
            }
        }
    },
    "driving_license": {
        "service_code": "driving_license",
        "service_name": "Driving License",
        "department": "transport",
        "title": "Driving License",
        "description": "Official statutory permit authorizing the holder to operate motor vehicles on public roads.",
        "responsible_authority": {
            "title": "Licensing Authority / Regional Transport Officer (RTO)",
            "office": "Regional Transport Office (RTO) / Motor Vehicles Department",
            "appeal_authority": "Joint Transport Commissioner"
        },
        "required_documents": ["identity_proof", "address_proof", "photograph", "medical_declaration"],
        "required_fields": ["date_of_birth", "blood_group", "vehicle_class"],
        "processing_time_days": 14,
        "fee_amount": 200.00,
        "document_options": {
            "identity_proof": [
                {"name": "Aadhaar Card", "authority": "UIDAI"},
                {"name": "Electoral Photo ID (Voter ID)", "authority": "ECI"},
                {"name": "Passport", "authority": "MEA"},
                {"name": "10th Standard / Matriculation Certificate", "authority": "Recognized Educational Board"}
            ],
            "address_proof": [
                {"name": "Electricity / Water Utility Bill", "authority": "Utility Provider"},
                {"name": "Ration Card", "authority": "Civil Supplies"},
                {"name": "Passport", "authority": "MEA"},
                {"name": "Registered Rental Agreement", "authority": "Sub-Registrar"}
            ],
            "photograph": [
                {"name": "Recent Passport-Size Colour Photograph (White background)", "authority": "Applicant"}
            ],
            "medical_declaration": [
                {"name": "Form 1 (Self-Declaration of Physical Fitness for non-transport)", "authority": "Self-Attested"},
                {"name": "Form 1A (Medical Certificate for transport or age 40+)", "authority": "Registered Medical Practitioner"}
            ]
        },
        "document_dependencies": [
            {
                "rule": "learner_license_prerequisite",
                "description": "A valid Learner's License (LL) is required prior to taking the permanent driving test."
            }
        ],
        "jurisdictions": {
            "default": {
                "portal": "Sarathi Parivahan (Ministry of Road Transport and Highways)",
                "officer": "Licensing Authority / RTO"
            }
        }
    }
}


async def get_requirements(
    service_code: str,
    jurisdiction: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Authoritative async query interface for government service requirements.
    Eliminates silent fallback: if an unsupported jurisdiction is requested,
    it returns jurisdiction_supported=False and does NOT guess another state's rules.
    """
    normalized_code = service_code.strip().lower()
    rules = SERVICE_RULES.get(normalized_code)
    if not rules:
        return {
            "error": f"Service rules for '{service_code}' not found.",
            "service_code": service_code,
            "jurisdiction_supported": False,
            "required_documents": [],
            "required_fields": []
        }

    available_jurisdictions = rules.get("jurisdictions", {})
    requested_key = jurisdiction.strip().lower() if jurisdiction else "default"

    # Eliminate silent fallback
    if jurisdiction and requested_key != "default" and requested_key not in available_jurisdictions:
        supported_states = [k.title() for k in available_jurisdictions.keys() if k != "default"]
        return {
            "service_code": rules["service_code"],
            "service_name": rules["service_name"],
            "jurisdiction_supported": False,
            "requested_jurisdiction": jurisdiction,
            "supported_jurisdictions": supported_states,
            "error": (
                f"Official requirements for jurisdiction '{jurisdiction}' are not currently verified in SEVA. "
                f"Verified jurisdictions for this service are: {', '.join(supported_states) if supported_states else 'National standard'}."
            ),
            "required_documents": [],
            "required_fields": []
        }

    jurisdiction_data = available_jurisdictions.get(requested_key, available_jurisdictions.get("default", {}))

    return {
        "service_code": rules["service_code"],
        "service_name": rules["service_name"],
        "title": rules["title"],
        "department": rules["department"],
        "description": rules["description"],
        "jurisdiction_supported": True,
        "jurisdiction": jurisdiction_data,
        "responsible_authority": rules.get("responsible_authority", {}),
        "required_documents": list(rules["required_documents"]),
        "required_fields": list(rules["required_fields"]),
        "document_options": rules.get("document_options", {}),
        "document_dependencies": rules.get("document_dependencies", []),
        "processing_time_days": rules["processing_time_days"],
        "fee_amount": rules["fee_amount"],
        "scholarship_guidance": rules.get("scholarship_guidance")
    }


def get_alternative_documents(document_type: str, service_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns acceptable alternative official documents for a given document requirement.
    """
    doc_key = document_type.strip().lower()
    if service_code and service_code in SERVICE_RULES:
        options = SERVICE_RULES[service_code].get("document_options", {})
        if doc_key in options:
            return options[doc_key]

    for s_data in SERVICE_RULES.values():
        options = s_data.get("document_options", {})
        if doc_key in options:
            return options[doc_key]

    return []


def get_document_dependencies(service_code: str) -> List[Dict[str, str]]:
    """
    Returns legal and procedural document dependencies (e.g. child's birth cert does not need child's Aadhaar).
    """
    rules = SERVICE_RULES.get(service_code.strip().lower(), {})
    return rules.get("document_dependencies", [])


def get_responsible_officer(service_code: str, jurisdiction: Optional[str] = None) -> Dict[str, str]:
    """
    Returns the designated government officer and office for the service.
    """
    rules = SERVICE_RULES.get(service_code.strip().lower(), {})
    auth = rules.get("responsible_authority", {})
    juris = rules.get("jurisdictions", {}).get(jurisdiction.lower() if jurisdiction else "default", {})
    return {
        "officer": juris.get("officer") or auth.get("title", "Designated Competent Officer"),
        "office": auth.get("office", "Departmental Office"),
        "appeal_authority": auth.get("appeal_authority", "Appellate Authority")
    }


async def evaluate_citizen_readiness(
    service_code: str,
    uploaded_doc_types: List[str],
    extracted_fields: Dict[str, Any],
    jurisdiction: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Compares citizen's verified assets against authoritative rules.
    Uses semantic document satisfaction rules (e.g. legitimate parent ID satisfies parent_identity_proof).
    """
    reqs = await get_requirements(service_code, jurisdiction, db)
    if "error" in reqs and not reqs.get("jurisdiction_supported", True):
        return reqs

    all_docs = reqs.get("required_documents", [])
    all_fields = reqs.get("required_fields", [])

    missing_docs = [
        d for d in all_docs
        if not is_requirement_satisfied(d, uploaded_doc_types)
    ]
    verified_docs = [
        d for d in all_docs
        if is_requirement_satisfied(d, uploaded_doc_types)
    ]

    missing_fields = [f for f in all_fields if f not in extracted_fields or extracted_fields.get(f) in [None, ""]]
    provided_fields = [f for f in all_fields if f not in missing_fields]

    is_ready = len(missing_docs) == 0 and len(missing_fields) == 0

    return {
        "service_code": service_code,
        "service_name": reqs.get("service_name", service_code),
        "jurisdiction_supported": reqs.get("jurisdiction_supported", True),
        "is_ready_for_review": is_ready,
        "required_documents": all_docs,
        "verified_documents": verified_docs,
        "missing_documents": missing_docs,
        "required_fields": all_fields,
        "provided_fields": provided_fields,
        "missing_fields": missing_fields,
        "responsible_authority": reqs.get("responsible_authority", {}),
    }
