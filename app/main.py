from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Payment Reconciliation Engine",
    description="Backend service for matching payment transactions across data sources",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Payment Reconciliation Engine",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
