# 🚀 Nagarro's Ascent Platform - Complete Startup Guide

**Complete instructions for stopping and starting the entire Nagarro's Ascent platform**

---

## 🛑 **STEP 1: COMPLETE PLATFORM SHUTDOWN**

### 1.1 Stop Local Development Services

**Stop all running local services in this order:**

```powershell
# Stop Frontend (if running in terminal)
# Press Ctrl+C in the frontend terminal (Terminal 3)

# Stop Backend (if running in terminal)
# Press Ctrl+C in the backend terminal (Terminal 1)

# Stop Project Service (if running in terminal)
# Press Ctrl+C in the project service terminal (Terminal 2)

# Stop Reporting Service (if running in terminal)
# Press Ctrl+C in the reporting service terminal (if running)
```

### 1.2 Stop All Docker Containers

```powershell
# Stop all platform containers
docker-compose down --remove-orphans

# Verify all containers are stopped
docker-compose ps

# Optional: Remove all containers and networks (clean slate)
docker-compose down --remove-orphans --volumes
```

### 1.3 Verify Complete Shutdown

```powershell
# Check no platform processes are running
docker ps | findstr "migration_platform"

# Check no local services on platform ports
netstat -an | findstr ":3000 :8000 :8002 :5001"
```

---

## 🚀 **STEP 2: COMPLETE PLATFORM STARTUP**

### 2.1 Prerequisites Check

```powershell
# Verify Rancher Desktop is running
docker --version

# Verify you're in the correct directory
pwd
# Should show: C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2
```

### 2.2 Start Infrastructure Services (Docker Containers)

**Start infrastructure services FIRST and wait for them to be healthy:**

```powershell
# Start core infrastructure services
docker-compose up -d postgres neo4j weaviate minio t2v-transformers

# Wait for services to initialize (2-3 minutes)
Write-Host "⏳ Waiting for infrastructure services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 120

# Check infrastructure health
docker-compose ps
```

**Expected Infrastructure Services:**
- ✅ **PostgreSQL**: `localhost:5432` (Database)
- ✅ **Neo4j**: `localhost:7474` (Graph Database)
- ✅ **Weaviate**: `localhost:8080` (Vector Database)
- ✅ **MinIO**: `localhost:9000` (Object Storage)
- ✅ **Transformers**: Internal service for Weaviate

### 2.3 Start MegaParse Service

```powershell
# Start document parsing service
docker-compose up -d megaparse

# Wait for MegaParse to be ready (1-2 minutes)
Write-Host "⏳ Waiting for MegaParse service..." -ForegroundColor Yellow
Start-Sleep -Seconds 60

# Verify MegaParse is running
docker-compose ps megaparse
```

**Expected Service:**
- ✅ **MegaParse**: `localhost:5001` (Document Processing)

### 2.4 Start Platform Services (Local Development)

**Start platform services in this EXACT order with proper timing:**

#### 2.4.1 Start Project Service (Terminal 1)

```powershell
# Open new PowerShell terminal
cd "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\project-service"

# Start project service
python main.py
```

**Wait for Project Service to be ready:**
- ⏳ **Startup Time**: ~10-15 seconds
- ✅ **Ready Signal**: "Application startup complete"
- ✅ **Health Check**: http://localhost:8002/health
- ✅ **Port**: 8002

#### 2.4.2 Start Backend Service (Terminal 2)

```powershell
# Open new PowerShell terminal
cd "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\backend"

# Start backend service
python -m app.main
```

**Wait for Backend Service to be ready:**
- ⏳ **Startup Time**: **UP TO 20 MINUTES** (be very patient!)
- ⚠️ **Initial Warnings**: Protobuf warnings are normal
- ✅ **Ready Signal**: "Application startup complete"
- ✅ **Health Check**: http://localhost:8000/health
- ✅ **Port**: 8000

**Backend Startup Progress Indicators:**
1. "Starting FastAPI application..."
2. "Loading AI models..." (takes 5-10 minutes)
3. "Connecting to databases..."
4. "Initializing RAG service..."
5. "Application startup complete"

#### 2.4.3 Start Frontend Service (Terminal 3)

```powershell
# Open new PowerShell terminal
cd "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\frontend"

# Start frontend development server
npm start
```

**Wait for Frontend Service to be ready:**
- ⏳ **Startup Time**: ~30-60 seconds
- ✅ **Ready Signal**: "webpack compiled successfully"
- ✅ **Auto-Open**: Browser opens to http://localhost:3000
- ✅ **Port**: 3000

#### 2.4.4 Start Reporting Service (Terminal 4) - Optional

```powershell
# Open new PowerShell terminal
cd "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\reporting-service"

# Start reporting service
python main.py
```

**Reporting Service Details:**
- ⏳ **Startup Time**: ~5-10 seconds
- ✅ **Port**: 8001
- ⚠️ **Note**: Optional service for enhanced reporting

---

## 📊 **STEP 3: VERIFY PLATFORM STATUS**

### 3.1 Check All Services

```powershell
# Check Docker containers
docker-compose ps

# Check local services
netstat -an | findstr ":3000 :8000 :8002 :5001"
```

### 3.2 Expected Running Services

**Docker Containers:**
- ✅ `postgres_service` (port 5432)
- ✅ `neo4j_service` (ports 7474, 7687)
- ✅ `weaviate_service` (port 8080)
- ✅ `minio_service` (port 9000)
- ✅ `megaparse_service` (port 5001)
- ✅ `weaviate_transformers` (internal)

**Local Development Services:**
- ✅ `project-service` (port 8002)
- ✅ `backend` (port 8000)
- ✅ `frontend` (port 3000)
- ✅ `reporting-service` (port 8001) - optional

### 3.3 Health Check URLs

```powershell
# Test all service endpoints
curl http://localhost:3000        # Frontend
curl http://localhost:8000/health # Backend
curl http://localhost:8002/health # Project Service
curl http://localhost:5001/health # MegaParse
curl http://localhost:8080/v1/.well-known/ready # Weaviate
```

### 3.4 Platform Access

**Primary Access:**
- 🌍 **Command Center**: http://localhost:3000
- 📊 **Backend API**: http://localhost:8000/docs
- 🗄️ **Project API**: http://localhost:8002/docs

**Infrastructure Access:**
- 📈 **Neo4j Browser**: http://localhost:7474 (neo4j/password)
- 🗃️ **MinIO Console**: http://localhost:9000 (minioadmin/minioadmin)

---

## ⚠️ **IMPORTANT STARTUP NOTES**

### Timing and Patience

1. **Infrastructure First**: Always start Docker services before local services
2. **Sequential Startup**: Start services in the exact order specified
3. **Backend Patience**: Backend can take up to 20 minutes - this is normal
4. **Health Checks**: Wait for each service to be healthy before starting the next

### Common Startup Issues

**Backend Taking Too Long:**
- ✅ Normal: Up to 20 minutes for first startup
- ✅ Normal: Protobuf warnings during startup
- ❌ Problem: If no progress after 25 minutes

**Port Conflicts:**
```powershell
# Check what's using a port
netstat -ano | findstr ":8000"

# Kill process if needed
taskkill /PID <process_id> /F
```

**Docker Issues:**
```powershell
# Restart Docker/Rancher Desktop
# Then restart infrastructure services
docker-compose up -d postgres neo4j weaviate minio megaparse
```

### Memory and Resources

**Recommended System Resources:**
- 💾 **RAM**: 16GB minimum (8GB for Docker, 8GB for local services)
- 🖥️ **CPU**: 4+ cores
- 💽 **Disk**: 10GB free space

---

## 🔄 **QUICK RESTART COMMANDS**

### Full Platform Restart

```powershell
# Stop everything
docker-compose down --remove-orphans
# Kill local services with Ctrl+C in each terminal

# Start everything
docker-compose up -d postgres neo4j weaviate minio megaparse
Start-Sleep -Seconds 120

# Start local services in separate terminals:
# Terminal 1: cd project-service && python main.py
# Terminal 2: cd backend && python -m app.main
# Terminal 3: cd frontend && npm start
```

### Infrastructure Only Restart

```powershell
# Restart just Docker services
docker-compose restart postgres neo4j weaviate minio megaparse
```

### Local Services Only Restart

```powershell
# Restart local services (Ctrl+C then restart in each terminal)
# Keep Docker services running
```

---

## 📋 **STARTUP CHECKLIST**

**Pre-Startup:**
- [ ] Rancher Desktop is running
- [ ] In correct directory
- [ ] All previous services stopped

**Infrastructure (Docker):**
- [ ] PostgreSQL started and healthy
- [ ] Neo4j started and healthy
- [ ] Weaviate started and healthy
- [ ] MinIO started and healthy
- [ ] MegaParse started and healthy

**Platform Services (Local):**
- [ ] Project Service started (port 8002)
- [ ] Backend Service started (port 8000) - **WAIT UP TO 20 MINUTES**
- [ ] Frontend Service started (port 3000)
- [ ] Reporting Service started (port 8001) - optional

**Verification:**
- [ ] All health checks pass
- [ ] Frontend loads at http://localhost:3000
- [ ] Can create/view projects
- [ ] Can upload files
- [ ] Can start assessments

---

## 🆘 **TROUBLESHOOTING**

### Backend Won't Start
1. Check if all infrastructure services are healthy
2. Verify .env file exists in backend directory
3. Check Python dependencies: `pip install -r requirements.txt`
4. Look for specific error messages in terminal

### Frontend Won't Start
1. Check Node.js version: `node --version` (should be 16+)
2. Install dependencies: `npm install`
3. Clear cache: `npm start -- --reset-cache`

### Docker Services Won't Start
1. Restart Rancher Desktop
2. Check available memory and disk space
3. Run: `docker system prune` to clean up

### Port Conflicts
1. Check what's using the port: `netstat -ano | findstr ":PORT"`
2. Kill conflicting process: `taskkill /PID <pid> /F`
3. Restart the service

---

**🎉 Platform should now be fully operational at http://localhost:3000**

*Last Updated: 2025-07-29*
