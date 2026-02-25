from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.reporting import ReportingService
from app.schemas.discrepancy import DiscrepancyResponse, DiscrepancySummary

router = APIRouter()


@router.get("", response_model=DiscrepancyResponse)
async def get_discrepancies(
    type: Optional[str] = Query(
        None,
        description="Filter by discrepancy type: unmatched_transactions, unmatched_settlements, unmatched_adjustments, amount_mismatches"
    ),
    currency: Optional[str] = Query(None, description="Filter by currency (MXN, COP, BRL)"),
    min_amount: Optional[float] = Query(None, description="Minimum amount filter"),
    priority: Optional[str] = Query(None, description="Filter by priority: high, medium, low"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get discrepancies with optional filtering."""
    service = ReportingService(db)

    min_amount_decimal = Decimal(str(min_amount)) if min_amount else None

    result = await service.get_discrepancies(
        discrepancy_type=type,
        currency=currency,
        min_amount=min_amount_decimal,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    return DiscrepancyResponse(
        discrepancies=result["discrepancies"],
        summary=result["summary"],
    )


@router.get("/summary", response_model=DiscrepancySummary)
async def get_discrepancy_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get a high-level summary of all discrepancies."""
    service = ReportingService(db)
    result = await service.get_summary()
    return DiscrepancySummary(**result)
