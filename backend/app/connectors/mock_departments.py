import httpx
from typing import Dict, Any
from app.connectors.base import GovernmentConnector

class MockDepartmentConnector(GovernmentConnector):
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def submit_application(self, data: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/submit", json=data)
            response.raise_for_status()
            return response.json()

    async def get_status(self, reference_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/status/{reference_id}")
            response.raise_for_status()
            return response.json().get("status", "UNKNOWN")

    async def get_requirements(self) -> Dict[str, Any]:
        # Mock requirements
        return {}


class RevenueConnector(MockDepartmentConnector):
    def __init__(self, base_url: str = "http://localhost:8000/mock/revenue"):
        super().__init__(base_url)


class MunicipalConnector(MockDepartmentConnector):
    def __init__(self, base_url: str = "http://localhost:8000/mock/municipal"):
        super().__init__(base_url)


class TransportConnector(MockDepartmentConnector):
    def __init__(self, base_url: str = "http://localhost:8000/mock/transport"):
        super().__init__(base_url)
