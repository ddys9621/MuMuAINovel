"""Shared SQLAlchemy declarative base.

Keep this module free of model imports so model files can safely import Base
without triggering database/session initialization or circular imports.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
