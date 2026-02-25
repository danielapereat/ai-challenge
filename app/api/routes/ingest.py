import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ingestion import IngestionService
from app.schemas.transaction import TransactionIngest, TransactionCreate, IngestResponse
from app.schemas.settlement import SettlementIngest, SettlementCreate
from app.schemas.adjustment import AdjustmentIngest, AdjustmentCreate

router = APIRouter()


@router.post("/transactions", response_model=IngestResponse)
async def ingest_transactions(
    data: TransactionIngest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple transactions."""
    service = IngestionService(db)
    ingested, errors = await service.ingest_transactions(data.transactions)
    return IngestResponse(ingested=ingested, errors=errors)


@router.post("/settlements", response_model=IngestResponse)
async def ingest_settlements(
    data: SettlementIngest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple settlements."""
    service = IngestionService(db)
    ingested, errors = await service.ingest_settlements(data.settlements)
    return IngestResponse(ingested=ingested, errors=errors)


@router.post("/adjustments", response_model=IngestResponse)
async def ingest_adjustments(
    data: AdjustmentIngest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple adjustments (refunds/chargebacks)."""
    service = IngestionService(db)
    ingested, errors = await service.ingest_adjustments(data.adjustments)
    return IngestResponse(ingested=ingested, errors=errors)


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    type: Literal["transactions", "settlements", "adjustments"] = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Ingest data from a JSON or CSV file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Read file content
    content = await file.read()

    try:
        if file.filename.endswith(".json"):
            data = json.loads(content)
        else:
            raise HTTPException(
                status_code=400,
                detail="Only JSON files are currently supported"
            )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    service = IngestionService(db)

    if type == "transactions":
        # Handle both array and object with "transactions" key
        if isinstance(data, list):
            items = data
        else:
            items = data.get("transactions", data)

        transactions = [TransactionCreate(**item) for item in items]
        ingested, errors = await service.ingest_transactions(transactions)

    elif type == "settlements":
        if isinstance(data, list):
            items = data
        else:
            items = data.get("settlements", data)

        settlements = [SettlementCreate(**item) for item in items]
        ingested, errors = await service.ingest_settlements(settlements)

    elif type == "adjustments":
        if isinstance(data, list):
            items = data
        else:
            items = data.get("adjustments", data)

        adjustments = [AdjustmentCreate(**item) for item in items]
        ingested, errors = await service.ingest_adjustments(adjustments)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown type: {type}")

    return IngestResponse(ingested=ingested, errors=errors)
