# Utility script to build and deploy Nagarro AgentiMigrate MVP on Rancher Desktop Kubernetes

Write-Host "Starting build and deployment for Nagarro AgentiMigrate MVP..."

# Build backend image
Write-Host "Building backend Docker image..."
docker build -t nagarro-backend:mvp ./backend
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Backend image build failed."
    exit 1
}

# Build frontend image
Write-Host "Building frontend Docker image..."
docker build -t nagarro-frontend:mvp ./frontend
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Frontend image build failed."
    exit 1
}

# Load backend image into Rancher Desktop's Kubernetes
Write-Host "Loading backend image into Rancher Desktop Kubernetes..."
docker save nagarro-backend:mvp | nerdctl -n k8s.io image load
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to load backend image into Kubernetes."
    exit 1
}

# Load frontend image into Rancher Desktop's Kubernetes
Write-Host "Loading frontend image into Rancher Desktop Kubernetes..."
docker save nagarro-frontend:mvp | nerdctl -n k8s.io image load
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to load frontend image into Kubernetes."
    exit 1
}

# Apply secrets and PVC first
Write-Host "Applying Kubernetes secrets and persistent volume claim..."
kubectl apply -f ./k8s/secrets.yaml
kubectl apply -f ./k8s/chromadb-pvc.yaml

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
Write-Host "ChromaDB: http://localhost:30800"
Write-Host ""
Write-Host "To view logs: kubectl logs -l app=frontend --follow"
Write-Host "To stop all services: kubectl delete -f ./k8s"
