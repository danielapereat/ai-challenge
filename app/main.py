from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.api import api_router

# Get the static directory path
STATIC_DIR = Path(__file__).parent.parent / "static"


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

# CORS middleware - configure for security
# In production, replace with specific allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  # For local development with frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Mount static files directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return {
        "name": "Payment Reconciliation Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/dashboard")
async def dashboard():
    """Serve the payment reconciliation dashboard."""
    dashboard_path = STATIC_DIR / "dashboard.html"
    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(
        dashboard_path,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"}
    )
