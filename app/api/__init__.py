from fastapi import APIRouter

from app.api.routes import ingest, reconcile, discrepancies, matches, analysis

api_router = APIRouter()

api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
api_router.include_router(reconcile.router, prefix="/reconcile", tags=["Reconciliation"])
api_router.include_router(discrepancies.router, prefix="/discrepancies", tags=["Discrepancies"])
api_router.include_router(matches.router, prefix="/matches", tags=["Matches"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["AI Analysis"])
