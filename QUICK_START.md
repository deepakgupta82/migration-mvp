# 🚀 Nagarro AgentiMigrate Platform - Quick Start Guide

## **Prerequisites**

### **Required Software**
- **Docker Desktop** (Latest version)
  - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - macOS: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)
- **Git** (for cloning the repository)
- **OpenAI API Key** (Required for AI agents)

### **System Requirements**
- **RAM**: Minimum 8GB, Recommended 16GB
- **Storage**: At least 10GB free space
- **CPU**: Multi-core processor recommended
- **Network**: Internet connection for downloading dependencies

---

## **🎯 One-Command Setup**

### **For Windows Users**
```cmd
# Clone the repository
git clone <repository-url>
cd migration_platform_2

# Run the setup script
build-optimized.bat
```

### **For macOS/Linux Users**
```bash
# Clone the repository
git clone <repository-url>
cd migration_platform_2

# Make script executable and run
chmod +x build-optimized.sh
./build-optimized.sh
```

### **For Git Bash on Windows**
```bash
# Clone the repository
git clone <repository-url>
cd migration_platform_2

# Run the bash script
bash build-optimized.sh
```

---

## **📋 Manual Setup (If Scripts Don't Work)**

### **1. Environment Configuration**
Create a `.env` file in the root directory:

```env
# OpenAI API Key (Required)
OPENAI_API_KEY=your_actual_openai_api_key_here

# LLM Provider
LLM_PROVIDER=openai

# Database Configuration
POSTGRES_DB=projectdb
POSTGRES_USER=projectuser
POSTGRES_PASSWORD=projectpass

# MinIO Object Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Neo4j Graph Database
NEO4J_AUTH=neo4j/password
```

### **2. Get OpenAI API Key**
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Create a new API key
4. Copy the key and paste it in the `.env` file

### **3. Build and Start Services**
```bash
# Enable BuildKit for faster builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build all services
docker-compose build --parallel

# Start the platform
docker-compose up -d
```

---

## **🌍 Access the Platform**

Once the platform is running, you can access:

| Service | URL | Description |
|---------|-----|-------------|
| **Command Center** | http://localhost:3000 | Main UI for project management |
| **Backend API** | http://localhost:8000 | Core API endpoints |
| **Project Service** | http://localhost:8002 | Project management API |
| **Reporting Service** | http://localhost:8003 | Report generation API |
| **MegaParse Service** | http://localhost:5001 | Document parsing service |
| **Neo4j Browser** | http://localhost:7474 | Graph database interface |
| **Weaviate** | http://localhost:8080 | Vector database |
| **MinIO Console** | http://localhost:9001 | Object storage interface |

### **Default Credentials**
- **Neo4j**: Username: `neo4j`, Password: `password`
- **MinIO**: Username: `minioadmin`, Password: `minioadmin`

---

## **🎮 Using the Platform**

### **1. Create Your First Project**
1. Open http://localhost:3000
2. Click "Create New Project"
3. Fill in project details (name, client, description)
4. Click "Create Project"

### **2. Upload Documents**
1. Select your project from the dashboard
2. Go to "File Management & Assessment" tab
3. Drag and drop your infrastructure documents
4. Click "Upload & Start Assessment"

### **3. Monitor Assessment Progress**
1. Watch the real-time progress in the console
2. Assessment typically takes 5-15 minutes depending on document size
3. You'll see AI agents working through discovery, architecture design, and compliance validation

### **4. Explore Results**
1. **Interactive Discovery**: View infrastructure graphs and chat with the knowledge base
2. **Final Report**: Download professional DOCX/PDF reports
3. **Architecture Diagrams**: View generated infrastructure diagrams

---

## **🔧 Troubleshooting**

### **Common Issues**

#### **"OpenAI API key not configured"**
- Edit the `.env` file and add your actual OpenAI API key
- Restart the services: `docker-compose restart`

#### **"Port already in use"**
- Stop other services using the same ports
- Or modify ports in `docker-compose.yml`

#### **"Build failed"**
- Ensure Docker Desktop is running
- Try: `docker system prune -a` to clean up
- Re-run the build script

#### **Services not starting**
- Check Docker Desktop is running
- Verify you have enough RAM (8GB minimum)
- Check logs: `docker-compose logs [service-name]`

### **Useful Commands**

```bash
# Check service status
docker-compose ps

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend

# Restart a specific service
docker-compose restart backend

# Stop all services
docker-compose down

# Stop and remove all data
docker-compose down -v

# Rebuild a specific service
docker-compose build backend
docker-compose up -d backend
```

---

## **📊 Performance Tips**

### **For Better Performance**
1. **Allocate more RAM to Docker** (8GB minimum, 16GB recommended)
2. **Enable WSL2** on Windows for better performance
3. **Use SSD storage** for faster builds and container startup
4. **Close unnecessary applications** during assessment runs

### **For Faster Builds**
1. **Keep Docker running** between builds to leverage cache
2. **Use the provided build scripts** which include optimizations
3. **Don't modify Dockerfiles** unless necessary (breaks cache)

---

## **🆘 Getting Help**

### **Check Service Health**
```bash
# Check if all services are healthy
docker-compose ps

# Check specific service logs
docker-compose logs backend
```

### **Reset Everything**
```bash
# Complete reset (removes all data)
docker-compose down -v
docker system prune -a
./build-optimized.sh  # or build-optimized.bat on Windows
```

### **Contact Support**
If you encounter issues:
1. Check the logs: `docker-compose logs`
2. Verify your `.env` configuration
3. Ensure Docker Desktop has enough resources
4. Try the reset procedure above

---

## **🎉 Success!**

If everything is working correctly, you should see:
- ✅ All services running (`docker-compose ps`)
- ✅ Command Center accessible at http://localhost:3000
- ✅ Ability to create projects and upload documents
- ✅ AI assessment completing successfully

**Welcome to the Nagarro AgentiMigrate Platform!** 🚀
