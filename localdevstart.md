# Local Development Startup Guide

**Nagarro AgentiMigrate Platform - Local Development Environment**

This guide explains how to start all platform components locally for development.

---

## Prerequisites

- **Rancher Desktop** (instead of Docker Desktop)
- **Node.js** (for frontend)
- **Python 3.11+** (for backend services)
- **Git** (for version control)

---

## Infrastructure Services (Docker/Rancher)

These services must be started **BEFORE** starting the platform services:

### 1. Start Infrastructure Services

```bash
# Start core infrastructure services
docker-compose up -d postgres neo4j weaviate minio

# Verify services are running
docker-compose ps
```

**Infrastructure Services:**
- **PostgreSQL**: `localhost:5432`
  - Database: `projectdb`
  - User: `projectuser`
  - Password: `projectpass`
  - Status: Must be healthy before starting platform services

- **Neo4j**: `localhost:7474` (Browser), `localhost:7687` (Bolt)
  - User: `neo4j`
  - Password: `password`
  - Purpose: Graph database for relationships

- **Weaviate**: `localhost:8080`
  - Purpose: Vector database for embeddings
  - API: REST and GraphQL

- **MinIO**: `localhost:9000` (API), `localhost:9001` (Console)
  - User: `minioadmin`
  - Password: `minioadmin`
  - Purpose: Object storage for files

### 2. Start MegaParse Service (Docker)

```bash
# Start document parsing service
docker-compose up -d megaparse
```

**MegaParse Service:**
- **URL**: `localhost:5001`
- **Purpose**: Document parsing and text extraction
- **Status**: Should be running in Docker

---

## Platform Services (Local Development)

Start these services in the following order:

### 1. Project Service

```bash
# Terminal 1
cd project-service
python main.py
```

**Project Service Details:**
- **Port**: `8002`
- **URL**: `http://localhost:8002`
- **Purpose**: Database management and project operations
- **Startup Time**: ~10 seconds
- **Health Check**: `http://localhost:8002/health`

### 2. Backend Service

```bash
# Terminal 2
cd backend
python -m app.main
```

**Backend Service Details:**
- **Port**: `8000`
- **URL**: `http://localhost:8000`
- **Purpose**: Main API, AI agents, WebSocket connections
- **Startup Time**: **Up to 20 minutes** (be patient!)
- **Health Check**: `http://localhost:8000/health`
- **Note**: Shows protobuf warnings initially (normal)

### 3. Frontend Service

```bash
# Terminal 3
cd frontend
npm start
```

**Frontend Service Details:**
- **Port**: `3000`
- **URL**: `http://localhost:3000`
- **Purpose**: React development server with hot reload
- **Startup Time**: ~30-60 seconds
- **Note**: Opens browser automatically

### 4. Reporting Service (Optional)

```bash
# Terminal 4
cd reporting-service
python main.py
```

**Reporting Service Details:**
- **Port**: `8003`
- **URL**: `http://localhost:8003`
- **Purpose**: PDF/DOCX report generation
- **Note**: May have dependency issues (pypandoc)

---

## Service URLs Summary

| Service | URL | Purpose | Type |
|---------|-----|---------|------|
| **Frontend** | http://localhost:3000 | Main UI | Local Dev |
| **Backend API** | http://localhost:8000 | Core API | Local Dev |
| **Project Service** | http://localhost:8002 | Project Management | Local Dev |
| **Reporting Service** | http://localhost:8003 | Report Generation | Local Dev |
| **MegaParse** | http://localhost:5001 | Document Parsing | Docker |
| **PostgreSQL** | localhost:5432 | Database | Docker |
| **Neo4j Browser** | http://localhost:7474 | Graph Database | Docker |
| **Weaviate** | http://localhost:8080 | Vector Database | Docker |
| **MinIO Console** | http://localhost:9001 | Object Storage | Docker |

---

## Startup Sequence

### Step 1: Infrastructure First
```bash
# Start all infrastructure services
docker-compose up -d postgres neo4j weaviate minio megaparse

# Wait for services to be healthy (check with docker-compose ps)
```

### Step 2: Platform Services
```bash
# Terminal 1: Project Service
cd project-service && python main.py

# Terminal 2: Backend Service (wait for project service to start)
cd backend && python -m app.main

# Terminal 3: Frontend (wait for backend to start)
cd frontend && npm start
```

### Step 3: Verify
- Open http://localhost:3000
- Check all services are responding
- Test file upload and assessment functionality

---

## Troubleshooting

### Common Issues

1. **Backend takes 20 minutes to start**
   - This is normal due to ML model loading
   - Monitor logs for progress
   - Look for "Uvicorn running on http://0.0.0.0:8000"

2. **PostgreSQL connection errors**
   - Ensure PostgreSQL container is healthy
   - Check docker-compose ps
   - Restart if needed: `docker-compose restart postgres`

3. **Frontend compilation errors**
   - Ensure node_modules exists
   - If not: `cd frontend && npm install`

4. **Port conflicts**
   - Check if ports are already in use
   - Kill existing processes if needed

### Rancher Desktop Specific

- Use `docker-compose` commands (same as Docker Desktop)
- Ensure Rancher Desktop is running
- Check container runtime is set to dockerd (not containerd)

### Health Checks

```bash
# Check infrastructure services
docker-compose ps

# Check platform services
curl http://localhost:8002/health  # Project Service
curl http://localhost:8000/health  # Backend Service
curl http://localhost:3000         # Frontend
```

---

## Development Notes

- **Hot Reload**: Frontend and backend support hot reload
- **Logs**: Check individual terminal windows for service logs
- **Database**: PostgreSQL data persists in Docker volumes
- **File Storage**: MinIO data persists in Docker volumes
- **Environment**: Uses .env file for configuration

---

## Quick Start Commands

```bash
# One-time setup (if needed)
cd frontend && npm install

# Daily startup
docker-compose up -d postgres neo4j weaviate minio megaparse
cd project-service && python main.py &
cd backend && python -m app.main &
cd frontend && npm start
```

**Access the platform**: http://localhost:3000

---

*Last Updated: 2025-07-29*
