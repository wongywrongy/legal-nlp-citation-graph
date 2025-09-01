#!/usr/bin/env python3
"""
Startup script for the Legal Citation Graph backend
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Check if data directory exists
    data_dir = project_root / "data"
    pdfs_dir = data_dir / "pdfs"
    
    if not data_dir.exists():
        print("Creating data directory...")
        data_dir.mkdir(exist_ok=True)
        pdfs_dir.mkdir(exist_ok=True)
    
    # Check if .env file exists, create from example if not
    env_file = project_root / ".env"
    env_example = project_root / "env.example"
    
    if not env_file.exists() and env_example.exists():
        print("Creating .env file from env.example...")
        import shutil
        shutil.copy(env_example, env_file)
        print("Please edit .env file with your configuration")
    
    # Add current directory to Python path
    sys.path.insert(0, str(project_root))
    
    # Import and run the FastAPI app
    try:
        print("Starting Legal Citation Graph API server...")
        print("API will be available at: http://localhost:8000")
        print("API docs available at: http://localhost:8000/docs")
        print("Press Ctrl+C to stop")
        
        from backend.main import app
        import uvicorn
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except ImportError as e:
        print(f"Error importing backend modules: {e}")
        print("Make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

