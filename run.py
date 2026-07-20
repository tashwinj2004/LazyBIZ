import subprocess
import sys
import os

def check_requirements():
    print("Checking packages inside virtual environment...")
    try:
        # Use the local venv pip to prevent global pip connection failures
        pip_path = os.path.join("venv", "Scripts", "pip.exe")
        if os.path.exists(pip_path):
            subprocess.check_call([pip_path, "install", "-r", "backend/requirements.txt"])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"])
    except subprocess.CalledProcessError as e:
        print(f"Warning installing requirements: {e}")

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")

    print("\nStarting LazyBIZ RAG Analytics Platform (FastAPI)...")
    print("---------------------------------------------")

    # Ensure dependencies are installed
    check_requirements()

    os.chdir(backend_dir)
    print("Backend server is starting up on http://localhost:5001")
    print("Press Ctrl+C to stop.")

    # Run the FastAPI app via uvicorn
    try:
        subprocess.check_call([
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", "127.0.0.1",
            "--port", "5001",
            "--reload",
            "--workers", "1"
        ])
    except KeyboardInterrupt:
        print("\nStopping server...")

if __name__ == "__main__":
    main()
