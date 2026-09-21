from app.connectors.base import GovernmentConnector
from app.connectors.mock_departments import RevenueConnector, MunicipalConnector, TransportConnector

def get_connector(service_code: str) -> GovernmentConnector:
    if service_code == "income_certificate":
        return RevenueConnector()
    elif service_code == "birth_certificate":
        return MunicipalConnector()
    elif service_code == "driving_license":
        return TransportConnector()
    else:
        raise ValueError(f"No connector registered for service code: {service_code}")
