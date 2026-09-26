from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.config import settings


class RegistryOutcome(BaseModel):
    is_matched: bool = False
    is_available: bool = False
    registry_name: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


# Deterministic demo fixtures for staging/demo environments.
# Maps document type -> identifier token -> demo record.
# Crucial: These are staging fixtures ONLY. Arbitrary inputs NOT in these fixtures will NOT be verified.
DEMO_REGISTRY_FIXTURES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "aadhaar": {
        "883920491122": {
            "name": "Rahul Kumar",
            "masked_id": "XXXXXXXX1122",
            "dob": "1990-01-01",
            "state": "Karnataka",
            "status": "ACTIVE",
            "gender": "M"
        },
        "XXXXXXXX1122": {
            "name": "Rahul Kumar",
            "masked_id": "XXXXXXXX1122",
            "dob": "1990-01-01",
            "state": "Karnataka",
            "status": "ACTIVE",
            "gender": "M"
        },
        "234567890123": {
            "name": "Priya Sharma",
            "masked_id": "XXXXXXXX0123",
            "dob": "1988-06-15",
            "state": "Maharashtra",
            "status": "ACTIVE",
            "gender": "F"
        },
        "XXXXXXXX0123": {
            "name": "Priya Sharma",
            "masked_id": "XXXXXXXX0123",
            "dob": "1988-06-15",
            "state": "Maharashtra",
            "status": "ACTIVE",
            "gender": "F"
        },
    },
    "pan": {
        "ABCPS1234F": {
            "name": "Rahul Sharma",
            "masked_id": "XXXXX1234F",
            "category": "INDIVIDUAL",
            "status": "OPERATIVE"
        },
        "XXXXX1234F": {
            "name": "Rahul Sharma",
            "masked_id": "XXXXX1234F",
            "category": "INDIVIDUAL",
            "status": "OPERATIVE"
        },
        "ABCDE1234F": {
            "name": "Demo Taxpayer",
            "masked_id": "XXXXX1234F",
            "category": "INDIVIDUAL",
            "status": "OPERATIVE"
        }
    },
    "voter_id": {
        "WBF1234567": {
            "name": "Demo Elector",
            "masked_id": "WBF****567",
            "state": "West Bengal",
            "status": "ACTIVE",
            "constituency": "Kolkata North"
        },
        "WBF****567": {
            "name": "Demo Elector",
            "masked_id": "WBF****567",
            "state": "West Bengal",
            "status": "ACTIVE",
            "constituency": "Kolkata North"
        }
    },
    "driving_licence": {
        "KA0120180001234": {
            "name": "Demo Driver",
            "masked_id": "KA012018*******",
            "status": "CURRENT",
            "rto": "KA-01",
            "vehicle_classes": ["MCWG", "LMV"]
        },
        "KA012018*******": {
            "name": "Demo Driver",
            "masked_id": "KA012018*******",
            "status": "CURRENT",
            "rto": "KA-01",
            "vehicle_classes": ["MCWG", "LMV"]
        },
        "DL0120190001234": {
            "name": "Demo Delhi Driver",
            "masked_id": "DL012019*******",
            "status": "CURRENT",
            "rto": "DL-01",
            "vehicle_classes": ["LMV"]
        },
        "DL012019*******": {
            "name": "Demo Delhi Driver",
            "masked_id": "DL012019*******",
            "status": "CURRENT",
            "rto": "DL-01",
            "vehicle_classes": ["LMV"]
        }
    }
}


class GovernmentRegistryAdapter:
    """
    Adapter for matching document identifiers against state/central databases.
    Reports REGISTRY_UNAVAILABLE unless an active trusted integration endpoint is configured
    or explicit demo/staging mock registry mode is enabled with matching fixtures.
    """

    def __init__(self, mock_enabled: Optional[bool] = None):
        self._mock_enabled = mock_enabled

    @property
    def is_mock_enabled(self) -> bool:
        if self._mock_enabled is not None:
            return self._mock_enabled
        return getattr(settings, "ENABLE_MOCK_REGISTRY_VERIFICATION", False)

    async def lookup(
        self,
        document_type: str,
        identifier: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RegistryOutcome:
        registries = {
            "aadhaar": "CIDR (UIDAI Central Identities Data Repository)",
            "pan": "NSDL / Protean / UTIITSL PAN Registry",
            "voter_id": "NVSP (National Voters' Service Portal / ECI)",
            "driving_licence": "Sarathi / Vahan National Register (MoRTH)"
        }
        name = registries.get(document_type, "Central Government Registry")

        # -------------------------------------------------------------
        # 1. PRODUCTION / DEFAULT PATH:
        # Strictly report REGISTRY_UNREACHABLE if mock mode is not explicitly enabled.
        # No fake verification without real government credentials.
        # -------------------------------------------------------------
        if not self.is_mock_enabled:
            return RegistryOutcome(
                is_matched=False,
                is_available=False,
                registry_name=name,
                checks_passed=["registry_target_identified"],
                checks_failed=["registry_endpoint_live"],
                risk_flags=["REGISTRY_UNREACHABLE"],
                details={
                    "status": "REGISTRY_UNAVAILABLE",
                    "registry": name,
                    "environment": "production",
                    "reason": "Direct registry connection requires government network gateway authorization."
                }
            )

        # -------------------------------------------------------------
        # 2. DEMO / STAGING MODE (Explicitly configured):
        # Match only against predefined deterministic fixtures.
        # -------------------------------------------------------------
        type_fixtures = DEMO_REGISTRY_FIXTURES.get(document_type, {})

        candidate_keys = []
        if identifier:
            candidate_keys.append(str(identifier).strip().upper())
            candidate_keys.append(str(identifier).strip())
            # Strip non-alphanumeric
            alphanumeric = "".join(ch for ch in str(identifier).strip().upper() if ch.isalnum())
            if alphanumeric:
                candidate_keys.append(alphanumeric)
            digits = "".join(filter(str.isdigit, str(identifier)))
            if digits:
                candidate_keys.append(digits)

        if metadata and isinstance(metadata, dict):
            extracted = metadata.get("extracted_fields") or {}
            for k in ("id_number", "aadhaar_number", "pan_number", "epic_number", "dl_number"):
                val = extracted.get(k)
                if val:
                    candidate_keys.append(str(val).strip().upper())
                    clean_val = "".join(ch for ch in str(val).strip().upper() if ch.isalnum())
                    if clean_val:
                        candidate_keys.append(clean_val)

        matched_fixture = None
        for k in candidate_keys:
            if k in type_fixtures:
                matched_fixture = type_fixtures[k]
                break

        if matched_fixture:
            # Deterministic demo fixture matched
            return RegistryOutcome(
                is_matched=True,
                is_available=True,
                registry_name=f"DEMO_REGISTRY ({name})",
                checks_passed=["registry_target_identified", "demo_registry_fixture_matched"],
                checks_failed=[],
                risk_flags=[],
                details={
                    "status": "REGISTRY_MATCHED",
                    "source": "DEMO_REGISTRY",
                    "environment": "staging",
                    "registry": name,
                    "is_demo_fixture": True,
                    "matched_record": {
                        "status": matched_fixture.get("status"),
                        "masked_id": matched_fixture.get("masked_id", "DEMO_RECORD"),
                        "verification_note": "Verified against staging demo fixture records. NOT an authoritative government registry verification."
                    }
                }
            )
        else:
            # Staging mode enabled, but document NOT in demo fixtures
            return RegistryOutcome(
                is_matched=False,
                is_available=True,
                registry_name=f"DEMO_REGISTRY ({name})",
                checks_passed=["registry_target_identified"],
                checks_failed=["demo_registry_record_not_found"],
                risk_flags=["DEMO_REGISTRY_NO_RECORD"],
                details={
                    "status": "REGISTRY_NO_RECORD",
                    "source": "DEMO_REGISTRY",
                    "environment": "staging",
                    "registry": name,
                    "is_demo_fixture": True,
                    "reason": "Submitted document identifier does not match any configured demo staging fixtures."
                }
            )
