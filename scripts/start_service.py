#!/usr/bin/env python3
"""
Simple script to start the project service with proper error handling
"""
import sys
import traceback

def main():
    try:
        print("Starting project service...")
        
        # Import the main module
        print("Importing main module...")
        import main
        print("Main module imported successfully")
        
        # Get the FastAPI app
        app = main.app
        print("FastAPI app retrieved successfully")
        
        # Start uvicorn
        print("Starting uvicorn server...")
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
        
    except Exception as e:
        print(f"Error starting service: {e}")
        print("Full traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
