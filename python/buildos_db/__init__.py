"""Top-level helper that exposes a singleton DB instance.
     Usage:
         from buildos_db import db
"""

from pathlib import Path
from .sqlite import SQLiteDB

# The database file lives next to the project root unless BUILDOS_DB_PATH is set
_DB_PATH = Path(__file__).with_name("sqlite.db")

db = SQLiteDB(str(_DB_PATH))
# Init (wipe + pre-seed from $SERVE) every time the app boots while we iterate
# Remove the next line for production behaviour
_db_initialized = db.init_db()

__all__ = ["db", "SQLiteDB"]