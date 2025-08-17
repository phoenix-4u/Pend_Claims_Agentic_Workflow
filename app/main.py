"""Main FastAPI application for the Pend Claim Analysis system."""
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import logging

# Import application components
from .config.settings import settings
from .db.base import Base, engine, get_db
from .db.init_db import init_db, clear_db
from .sops.loader import sop_loader
from .config.logging_config import logger

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize the FastAPI application
app = FastAPI(
    title="Pend Claim Analysis API",
    description="API for processing and analyzing pending claims using SOPs",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the Streamlit UI
app.mount("/static", StaticFiles(directory=settings.BASE_DIR / "app" / "ui" / "static"), name="static")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": settings.VERSION,
        "environment": "development"
    }

# API endpoints
@app.get("/api/claims/{icn}")
async def get_claim(icn: str, db=Depends(get_db)):
    """Get claim details by ICN."""
    from .db.crud import crud
    
    claim = crud.get_claim_with_lines(db, icn)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim with ICN {icn} not found")
    
    return claim

@app.get("/api/sops/{sop_code}")
async def get_sop(sop_code: str):
    """Get SOP definition by code."""
    sop = sop_loader.get_sop(sop_code)
    if not sop:
        raise HTTPException(status_code=404, detail=f"SOP {sop_code} not found")
    
    return JSONResponse(content=sop.dict())

# Initialize the application
def init_app():
    """Initialize the application."""
    # Initialize the database
    init_db()
    
    # Load all SOPs
    sop_loader.load_all()
    
    logger.info("Application initialized")

# Run the application
if __name__ == "__main__":
    # Initialize the application
    init_app()
    
    # Start the FastAPI server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
