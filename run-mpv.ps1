# Utility script to build and deploy Nagarro AgentiMigrate MVP on Rancher Desktop Kubernetes
[CmdletBinding()]
param (
    [switch]$SkipBackendBuild,
    [switch]$SkipFrontendBuild
)

Start-Transcript -Path "logs/platform.log" -Append
Write-Host "Starting build and deployment for Nagarro AgentiMigrate MVP..."

# Build backend image
if (-not $SkipBackendBuild) {
    Write-Host "Building backend Docker image..."
    docker build -t nagarro-backend:mvp ./backend
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Backend image build failed."
        exit 1
    }

    # Load backend image into Rancher Desktop's Kubernetes
    Write-Host "Loading backend image into Rancher Desktop Kubernetes..."
    docker save nagarro-backend:mvp | nerdctl -n k8s.io image load
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to load backend image into Kubernetes."
        exit 1
    }
} else {
    Write-Host "Skipping backend build as per -SkipBackendBuild flag."
}

# Build frontend image
if (-not $SkipFrontendBuild) {
    Write-Host "Building frontend Docker image..."
    docker build -t nagarro-frontend:mvp -f frontend/Dockerfile ./frontend
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Frontend image build failed."
        exit 1
    }

    # Load frontend image into Rancher Desktop's Kubernetes
    Write-Host "Loading frontend image into Rancher Desktop Kubernetes..."
    docker save nagarro-frontend:mvp | nerdctl -n k8s.io image load
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to load frontend image into Kubernetes."
        exit 1
    }
} else {
    Write-Host "Skipping frontend build as per -SkipFrontendBuild flag."
}

# Apply secrets and PVC first
Write-Host "Applying Kubernetes secrets and persistent volume claims..."
kubectl apply -f ./k8s/secrets.yaml
kubectl apply -f ./k8s/weaviate-pvc.yaml
kubectl apply -f ./k8s/neo4j-pvc.yaml

# Deploy all services
Write-Host "Deploying all services to Kubernetes..."
kubectl apply -f ./k8s

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to deploy services. Check kubectl logs for details."
    exit 1
}

Write-Host "All services deployed successfully to Rancher Desktop Kubernetes."
Write-Host "Access services using NodePort URLs:"
Write-Host "Frontend: http://localhost:30300"
Write-Host "Backend: http://localhost:30801"
Write-Host "MegaParse: http://localhost:30500"
Write-Host "Weaviate: http://localhost:8080"
Write-Host "Neo4j: http://localhost:7474"
Write-Host ""
Write-Host "To view logs: kubectl logs -l app=frontend --follow"
Write-Host "To stop all services: kubectl delete -f ./k8s"
