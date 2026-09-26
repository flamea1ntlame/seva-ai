from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RegistryOutcome(BaseModel):
    is_matched: bool = False
    is_available: bool = False
    registry_name: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class GovernmentRegistryAdapter:
    """
    Adapter for matching document identifiers against state/central databases.
    Reports REGISTRY_UNAVAILABLE unless an active trusted integration endpoint is configured.
    """

    async def lookup(self, document_type: str, identifier: str, metadata: Optional[Dict[str, Any]] = None) -> RegistryOutcome:
        registries = {
            "aadhaar": "CIDR (UIDAI Central Identities Data Repository)",
            "pan": "NSDL / Protean / UTIITSL PAN Registry",
            "voter_id": "NVSP (National Voters' Service Portal / ECI)",
            "driving_licence": "Sarathi / Vahan National Register (MoRTH)"
        }
        name = registries.get(document_type, "Central Government Registry")

        # In local/hackathon environment without live government VPN endpoint:
        # Strictly report REGISTRY_UNREACHABLE rather than manufacturing a fake lookup match!
        return RegistryOutcome(
            is_matched=False,
            is_available=False,
            registry_name=name,
            checks_passed=["registry_target_identified"],
            checks_failed=["registry_endpoint_live"],
            risk_flags=["REGISTRY_UNREACHABLE"],
            details={
                "registry": name,
                "reason": "Direct registry connection requires government network gateway authorization."
            }
        )
