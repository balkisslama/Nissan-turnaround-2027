"""
check_setup.py
==============
Purpose : Verify that the development environment is ready for the
          "Nissan Turnaround 2027" project: Python version, required
          libraries, SQLite and the project folder structure.

Usage   : Run from anywhere inside the project:
              python src/check_setup.py

Exit code: 0 if every check passes, 1 otherwise (useful for automation).
"""

import sqlite3
import sys
from importlib import import_module
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
MIN_PYTHON = (3, 10)

REQUIRED_LIBRARIES = [
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "openpyxl",
    "yfinance",
    "requests",
    "ipykernel",
]

REQUIRED_FOLDERS = [
    "data/raw",
    "data/processed",
    "sql",
    "notebooks",
    "src",
    "excel",
    "powerbi",
    "reports/figures",
    "docs",
]

# Project root = the parent of the "src" folder this file lives in.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# Individual checks (each returns True for pass, False for fail)
# ----------------------------------------------------------------------
def check_python_version() -> bool:
    """Check that the running Python is recent enough."""
    current = sys.version_info[:2]
    ok = current >= MIN_PYTHON
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] Python {current[0]}.{current[1]} "
          f"(minimum required: {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
    return ok


def check_virtual_environment() -> bool:
    """Check that we are running inside a virtual environment."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    status = "PASS" if in_venv else "FAIL"
    print(f"[{status}] Virtual environment active")
    if not in_venv:
        print("       -> Activate it first (see Step 1.3).")
    return in_venv


def check_libraries() -> bool:
    """Try to import every required library and print its version."""
    all_ok = True
    for name in REQUIRED_LIBRARIES:
        try:
            module = import_module(name)
            version = getattr(module, "__version__", "version n/a")
            print(f"[PASS] {name:<12} {version}")
        except ImportError:
            print(f"[FAIL] {name:<12} not installed -> run: pip install -r requirements.txt")
            all_ok = False
    return all_ok


def check_sqlite() -> bool:
    """Create an in-memory SQLite database and run a tiny query."""
    try:
        connection = sqlite3.connect(":memory:")
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER, label TEXT)")
        cursor.execute("INSERT INTO test VALUES (1, 'nissan')")
        cursor.execute("SELECT label FROM test WHERE id = 1")
        result = cursor.fetchone()[0]
        connection.close()
        ok = result == "nissan"
    except sqlite3.Error as error:
        print(f"[FAIL] SQLite error: {error}")
        return False

    status = "PASS" if ok else "FAIL"
    print(f"[{status}] SQLite {sqlite3.sqlite_version} read/write test")
    return ok


def check_folders() -> bool:
    """Check that every expected project folder exists."""
    all_ok = True
    for folder in REQUIRED_FOLDERS:
        exists = (PROJECT_ROOT / folder).is_dir()
        status = "PASS" if exists else "FAIL"
        print(f"[{status}] Folder: {folder}")
        if not exists:
            all_ok = False
    return all_ok


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main() -> int:
    """Run all checks and print a summary. Returns a process exit code."""
    print("=" * 60)
    print("NISSAN TURNAROUND 2027 - ENVIRONMENT CHECK")
    print(f"Project root: {PROJECT_ROOT}")
    print("=" * 60)

    results = {
        "Python version": check_python_version(),
        "Virtual environment": check_virtual_environment(),
        "Libraries": check_libraries(),
        "SQLite": check_sqlite(),
        "Folders": check_folders(),
    }

    print("=" * 60)
    failed = [name for name, passed in results.items() if not passed]
    if failed:
        print("RESULT: FAILED -> " + ", ".join(failed))
        return 1

    print("RESULT: ALL CHECKS PASSED. You are ready for Step 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())