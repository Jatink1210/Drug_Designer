"""Direct-run entrypoint: python -m apps.api or python run_server.py
Ensures correct working directory regardless of how it's launched.
"""
import os
import sys

def main():
    # Always run from the api directory so relative imports work
    api_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(api_dir)
    
    # Ensure api_dir is on sys.path for module resolution
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    
    # Load .env before anything else
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(api_dir, ".env"), override=True)
    except ImportError:
        pass
    
    import uvicorn
    
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    reload = os.environ.get("DSS_ENV", "development") == "development"
    
    print(f"Starting Drug Designer API on {host}:{port} (reload={reload})")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[api_dir] if reload else None,
    )

if __name__ == "__main__":
    main()
