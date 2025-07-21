# Utility script to run Nagarro AgentiMigrate MVP on Windows

Write-Host "Cleaning up any previous Kubernetes deployments..."
kubectl delete -f ./k8s --ignore-not-found

Write-Host "Deploying all services to Minikube..."
kubectl apply -f ./k8s

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to deploy services. Check kubectl logs for details."
    exit 1
}

Write-Host "All services deployed successfully to Minikube."
Write-Host "Access services using Minikube service URLs:"
Write-Host "Frontend: minikube service frontend-service"
Write-Host "Backend: minikube service backend-service"
Write-Host "MegaParse: minikube service megaparse-service"
Write-Host "ChromaDB: minikube service chromadb-service"
Write-Host ""
Write-Host "To view logs: kubectl logs -l app=frontend --follow"
Write-Host "To stop all services: kubectl delete -f ./k8s"
