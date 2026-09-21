from abc import ABC, abstractmethod
from typing import Dict, Any

class GovernmentConnector(ABC):
    @abstractmethod
    async def submit_application(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit the application data to the department.
        Returns a dictionary containing 'reference_id' and 'status'.
        """
        pass

    @abstractmethod
    async def get_status(self, reference_id: str) -> str:
        """
        Get the current status of the application from the department.
        """
        pass

    @abstractmethod
    async def get_requirements(self) -> Dict[str, Any]:
        """
        Get the service requirements defined by the department.
        """
        pass
