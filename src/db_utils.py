"""
db_utils.py
===========
Purpose : Small helpers shared by the scripts that load data into the
          database. Keeping them here means every script opens the database
          in exactly the same safe way.

          This file is not run on its own; other scripts import it.
"""

import sqlite3
from pathlib import Path

# The project folder is the parent of the "src" folder this file lives in.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "nissan.db"


def connect() -> sqlite3.Connection:
    """Open the project database with foreign-key checking switched ON."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Build it first with: python src/create_database.py")
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")   # SQLite ignores links unless told
    return connection


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    """Return how many rows a table holds. (Table names come from our own code.)"""
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]