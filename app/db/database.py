"""
Database configuration and session management for Bio-PerformX.
Uses SQLAlchemy with SQLite database stored in workspace root.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Database file location - workspace root level
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
DATABASE_PATH = WORKSPACE_ROOT / "bio_performx.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Generated files directory
GENERATED_DIR = WORKSPACE_ROOT / "generated"

# Create engine with SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite with FastAPI
    echo=False  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function for FastAPI routes.
    Yields a database session and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    Should be called on application startup.
    """
    from app.db import models  # Import models to register them with Base
    Base.metadata.create_all(bind=engine)
    
    # Ensure generated directory exists
    GENERATED_DIR.mkdir(exist_ok=True)


def get_session_dir(session_id: str) -> Path:
    """
    Get the directory path for a session's generated files.
    Creates the directory structure if it doesn't exist.
    
    Structure:
    generated/{session_id}/
        uploads/        - Original uploaded files
        static_charts/  - Immutable charts (spirometry, VO2, etc.)
        dynamic_charts/ - Metric-dependent charts (body comp, RMR, etc.)
        reports/        - Generated PDF reports
    """
    session_dir = GENERATED_DIR / session_id
    
    # Create subdirectories
    (session_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (session_dir / "static_charts").mkdir(parents=True, exist_ok=True)
    (session_dir / "dynamic_charts").mkdir(parents=True, exist_ok=True)
    (session_dir / "reports").mkdir(parents=True, exist_ok=True)
    
    return session_dir
