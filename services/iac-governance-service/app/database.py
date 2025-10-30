"""
Database compatibility shim.
This module re-exports database functions from app.core.database for backward compatibility.
"""

from app.core.database import get_db_session

# Alias for compatibility
get_db = get_db_session

__all__ = ['get_db', 'get_db_session']
