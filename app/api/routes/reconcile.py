from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.matching import MatchingEngine
from app.services.reporting import ReportingService
from app.schemas.discrepancy import ReconcileRequest, ReconcileResponse, ReconcileStatus

router = APIRouter()


@router.post("", response_model=ReconcileResponse)
async def run_reconciliation(
    request: ReconcileRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """Run the reconciliation process."""
    if request is None:
        request = ReconcileRequest()

    engine = MatchingEngine(db)
    result = await engine.run_reconciliation(
        date_from=request.date_from,
        date_to=request.date_to,
    )

    return ReconcileResponse(**result)


@router.get("/status", response_model=ReconcileStatus)
async def get_reconciliation_status(
    db: AsyncSession = Depends(get_db),
):
    """Get the status of the last reconciliation run."""
    service = ReportingService(db)
    result = await service.get_reconciliation_status()
    return ReconcileStatus(**result)
