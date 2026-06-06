"""
start.py - One-click launcher for LazyBIZ FastAPI backend.
Run this from the project root with: python start.py
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
VENV_PYTHON = os.path.join(ROOT, "venv", "Scripts", "python.exe")

# Use venv python if it exists, otherwise fall back to current python
PYTHON = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable

print(f"[LazyBIZ] Using Python: {PYTHON}")
print("[LazyBIZ] Installing / verifying dependencies...")

# Install all required packages
packages = [
    "fastapi==0.115.6",
    "uvicorn[standard]",
    "python-multipart",
    "pymongo",
    "certifi",
    "PyJWT",
    "bcrypt",
    "python-dotenv",
    "werkzeug",
    "pydantic==2.7.4",
    "pydantic-core==2.18.4",
]

subprocess.check_call(
    [PYTHON, "-m", "pip", "install", "--quiet"] + packages
)
print("[LazyBIZ] All dependencies ready.")

# Change into backend and start uvicorn
os.chdir(BACKEND)
PORT = os.environ.get("PORT", "5001")
print(f"[LazyBIZ] Starting server on http://localhost:{PORT}")
print("[LazyBIZ] Press Ctrl+C to stop.\n")

subprocess.run([
    PYTHON, "-m", "uvicorn", "app:app",
    "--host", "0.0.0.0",
    "--port", PORT,
    "--workers", "1"
])
