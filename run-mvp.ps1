# Utility script to run Nagarro AgentiMigrate MVP on Windows

Write-Host "Stopping any running containers and cleaning up..."
docker-compose down -v --remove-orphans

# Set environment variables (edit as needed)
$env:OPENAI_API_KEY="your_key_here"
Write-Host "IMPORTANT: Edit OPENAI_API_KEY above with your actual key before running!"

Write-Host "Building and starting all services..."
docker-compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to start services. Check Docker logs for details."
    exit 1
}

Write-Host "All services started successfully."
Write-Host "Frontend available at: http://localhost:3000"
Write-Host "Backend API available at: http://localhost:8000"
Write-Host "MegaParse service at: http://localhost:5001"
Write-Host "ChromaDB service at: http://localhost:8001"
Write-Host ""
Write-Host "To view logs: docker-compose logs -f"
Write-Host "To stop all services: docker-compose down"
