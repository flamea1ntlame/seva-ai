from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class IssuerOutcome(BaseModel):
    is_supported: bool = False
    is_reachable: bool = False
    is_verified: bool = False
    issuer_name: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class BaseIssuerAdapter(ABC):
    @property
    @abstractmethod
    def issuer_code(self) -> str:
        pass

    @property
    @abstractmethod
    def issuer_name(self) -> str:
        pass

    @abstractmethod
    async def verify(self, document_type: str, identifier: str, metadata: Optional[Dict[str, Any]] = None) -> IssuerOutcome:
        pass


class DefaultGovernmentIssuerAdapter(BaseIssuerAdapter):
    """
    Standard Government Issuer Adapter.
    Identifies expected authority (UIDAI, ITD, ECI, MoRTH).
    In the absence of live production VPN/mTLS gateway credentials,
    it strictly reports ISSUER_UNREACHABLE / NOT_VERIFIABLE rather than manufacturing a fake success.
    """
    @property
    def issuer_code(self) -> str:
        return "GOV_INDIA"

    @property
    def issuer_name(self) -> str:
        return "Government of India Official Issuing Authority"

    async def verify(self, document_type: str, identifier: str, metadata: Optional[Dict[str, Any]] = None) -> IssuerOutcome:
        issuer_names = {
            "aadhaar": "Unique Identification Authority of India (UIDAI)",
            "pan": "Income Tax Department (ITD)",
            "voter_id": "Election Commission of India (ECI)",
            "driving_licence": "Ministry of Road Transport and Highways (MoRTH)"
        }
        authority = issuer_names.get(document_type, "Government Issuing Authority")

        # Live government gateway is not provisioned in this environment
        return IssuerOutcome(
            is_supported=True,
            is_reachable=False,
            is_verified=False,
            issuer_name=authority,
            checks_passed=["issuer_identified"],
            checks_failed=["issuer_gateway_connection"],
            risk_flags=["ISSUER_UNREACHABLE"],
            details={
                "authority": authority,
                "status": "NOT_VERIFIABLE",
                "reason": "Direct government gateway requires production mTLS / VPN credentials."
            }
        )
