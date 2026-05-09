import subprocess
import sys
import os

def check_requirements():
    print("Installing requirements.txt to ensure all packages are available...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"])
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    
    print("\nStarting LazyBIZ RAG Analytics Platform...")
    print("---------------------------------------------")
    
    # Ensure dependencies are installed
    check_requirements()
    
    os.chdir(backend_dir)
    print("Backend server is starting up. Press Ctrl+C to stop.")
    
    # Run the Flask app
    try:
        subprocess.check_call([sys.executable, "app.py"])
    except KeyboardInterrupt:
        print("\nStopping server...")

if __name__ == "__main__":
    main()
