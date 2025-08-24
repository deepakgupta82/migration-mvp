from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Test Project Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "project-service-test"}

@app.get("/")
async def root():
    return {"message": "Project Service Test is running"}

if __name__ == "__main__":
    print("Starting test service on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
