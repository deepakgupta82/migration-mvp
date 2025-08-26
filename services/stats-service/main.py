"""
Stats Service Entry Point
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

if __name__ == "__main__":
    import uvicorn
    
    # Import after adding to path
    from app.main import app
    
    port = int(os.getenv("SERVICE_PORT", 8004))
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    
    print(f"Starting Stats Service on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,  # Disable reload to prevent import issues
        log_level="info"
    )
