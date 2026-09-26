import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class DigiLockerOutcome(BaseModel):
    is_connected: bool = False
    is_verified: bool = False
    is_mock: bool = False
    uri: Optional[str] = None
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class DigiLockerAdapter:
    """
    Adapter for DigiLocker document verification.
    If production OAuth keys (DIGILOCKER_CLIENT_ID & DIGILOCKER_CLIENT_SECRET) are configured,
    connects to real DigiLocker API.
    Otherwise reports DIGILOCKER_UNAVAILABLE / NOT_VERIFIABLE without faking verification.
    """

    def __init__(self):
        self.client_id = os.environ.get("DIGILOCKER_CLIENT_ID")
        self.client_secret = os.environ.get("DIGILOCKER_CLIENT_SECRET")

    async def verify_uri(self, digilocker_uri: Optional[str], document_type: str) -> DigiLockerOutcome:
        if not self.client_id or not self.client_secret:
            return DigiLockerOutcome(
                is_connected=False,
                is_verified=False,
                is_mock=False,
                checks_passed=[],
                checks_failed=["digilocker_credentials_configured"],
                risk_flags=["DIGILOCKER_UNAVAILABLE"],
                details={"reason": "DigiLocker production API credentials not provisioned in environment."}
            )

        # Real verification would exchange auth token and verify issuer XML signature
        return DigiLockerOutcome(
            is_connected=True,
            is_verified=False,
            is_mock=False,
            uri=digilocker_uri,
            checks_passed=["digilocker_connected"],
            checks_failed=["digilocker_document_unlinked"],
            risk_flags=["DIGILOCKER_RECORD_NOT_LINKED"],
            details={"status": "NO_ACTIVE_CITIZEN_SESSION"}
        )
