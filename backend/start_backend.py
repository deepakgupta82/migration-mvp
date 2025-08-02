#!/usr/bin/env python3
"""
Backend startup script
"""
import os
import sys

# Ensure we're in the backend directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
current_dir = os.getcwd()
sys.path.insert(0, current_dir)
print(f"Current directory: {current_dir}")
print(f"Python path: {sys.path[:3]}")

# Set environment variables
os.environ['SERVICE_AUTH_TOKEN'] = 'service-backend-token'
# Remove OpenAI dependency - using local embeddings
# os.environ['OPENAI_API_KEY'] = 'your-openai-key-here'

try:
    print("Starting backend import process...")
    from app.main import app
    print("Backend app imported successfully!")

    print("Starting uvicorn server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

except Exception as e:
    print(f"Error starting backend: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
