from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Service
from app.schemas import ServiceRead

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("/", response_model=List[ServiceRead])
async def list_services(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.is_active == True))
    return result.scalars().all()


@router.get("/{code}", response_model=ServiceRead)
async def get_service_by_code(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.code == code))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.get("/{code}/requirements")
async def get_service_requirements(
    code: str,
    jurisdiction: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns authoritative government requirements, alternative documents,
    fees, processing time, and authorities for a service and jurisdiction.
    """
    from app.service_rules import get_requirements
    reqs = await get_requirements(code, jurisdiction=jurisdiction, db=db)
    if not reqs or not reqs.get("service_code"):
        raise HTTPException(status_code=404, detail="Requirements not found for service")
    return reqs

