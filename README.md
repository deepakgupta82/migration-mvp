# 🚀 Nagarro AgentiMigrate Platform

**Enterprise-Grade Cloud Migration Assessment Platform powered by AI Agents**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![AI Powered](https://img.shields.io/badge/AI-Powered-green?logo=openai)](https://openai.com/)
[![Enterprise](https://img.shields.io/badge/Enterprise-Ready-orange)](https://www.nagarro.com/)

---

## **🎯 Quick Start**

### **One-Command Setup**

**Windows (PowerShell - Recommended):**
```powershell
git clone <repository-url>
cd migration_platform_2
.\start-platform.ps1
```

**Windows (Command Prompt):**
```cmd
git clone <repository-url>
cd migration_platform_2
build-optimized.bat
```

**macOS/Linux:**
```bash
git clone <repository-url>
cd migration_platform_2
chmod +x *.sh
./build-optimized.sh
```

**Access the platform:** http://localhost:3000

📖 **Detailed setup instructions:**
- [QUICK_START.md](QUICK_START.md) - General setup guide
- [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows-specific guide

---

## **🌟 What is AgentiMigrate?**

AgentiMigrate is a sophisticated AI-powered platform that automates cloud migration assessments using a team of specialized AI agents. It transforms complex infrastructure analysis into executive-ready migration strategies.

### **Key Features**

🤖 **AI Agent Team**
- **Infrastructure Analyst**: 12+ years experience in enterprise discovery
- **Cloud Architect**: 50+ enterprise migrations across AWS/Azure/GCP
- **Risk & Compliance Officer**: Regulatory expertise (GDPR, SOX, HIPAA)
- **Program Manager**: 30+ cloud migrations with $10M+ budgets

📊 **Professional Deliverables**
- Executive-ready migration reports (DOCX/PDF)
- Interactive infrastructure dependency graphs
- RAG-powered knowledge base chat
- 3-year TCO analysis and ROI projections

🔍 **Advanced Analysis**
- Cross-modal synthesis (graph + semantic search)
- 6Rs migration framework application
- Adversarial compliance validation
- Wave planning with dependency analysis

---

## **🏗️ Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Command       │    │   AI Agent      │    │   Knowledge     │
│   Center UI     │◄──►│   Framework     │◄──►│   Engine        │
│   (React)       │    │   (CrewAI)      │    │   (RAG + Graph) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Project       │    │   Document      │    │   Report        │
│   Management    │    │   Processing    │    │   Generation    │
│   Service       │    │   (MegaParse)   │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Technology Stack**

**Frontend:**
- React 18 with TypeScript
- Mantine UI component library
- React Router for navigation
- Force-directed graph visualization

**Backend:**
- FastAPI with Python 3.11
- CrewAI for multi-agent orchestration
- Weaviate for vector embeddings
- Neo4j for graph relationships

**AI & ML:**
- OpenAI GPT-4 (configurable LLM)
- RAG (Retrieval Augmented Generation)
- Semantic search and graph queries
- Document parsing and analysis

**Infrastructure:**
- Docker containerization
- PostgreSQL for project data
- MinIO for object storage
- Professional CI/CD ready

---

## **📋 Prerequisites**

### **Required**
- **Rancher Desktop** (latest version) - Download from https://rancherdesktop.io/
- **8GB RAM minimum** (16GB recommended)
- **10GB free disk space**
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))

### **Supported Platforms**
- ✅ Windows 10/11 (Rancher Desktop)
- ✅ macOS (Intel & Apple Silicon)
- ✅ Linux (Ubuntu, CentOS, etc.)
- ✅ WSL2 on Windows

---

## **🚀 Getting Started**

### **🎯 Quick Setup (Recommended)**
```powershell
# Clone the repository
git clone <repository-url>
cd migration_platform_2

# One command to set up everything
.\quick-mvp-setup.ps1
```

### **🔧 Complete Setup (Advanced)**
```powershell
# For full control and detailed logging
.\setup-mvp-complete.ps1
```

### **🐧 macOS/Linux Setup**
```bash
# Clone and start the platform
git clone <repository-url>
cd migration_platform_2
chmod +x build-optimized.sh
./build-optimized.sh
```

### **What the Setup Does:**
- ✅ **Checks prerequisites**: Rancher Desktop, Docker, Git, system requirements
- ✅ **Configures environment**: Creates .env file, validates LLM API keys
- ✅ **Builds Docker images**: All frontend and backend services
- ✅ **Starts infrastructure**: PostgreSQL, Neo4j, Weaviate, MinIO
- ✅ **Deploys applications**: Backend API, Project Service, Reporting Service
- ✅ **Creates frontend**: Professional web interface or simple dashboard
- ✅ **Performs health checks**: Ensures all services are running
- ✅ **Opens browser**: Direct access to the platform

### **Access Points After Setup:**
- **Main Platform:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs

---

## **🎮 Using the Platform**

### **Create Your First Project**
1. Open http://localhost:3000
2. Click "Create New Project"
3. Fill in project details
4. Upload infrastructure documents
5. Start AI assessment

### **Monitor Assessment Progress**
- Real-time progress tracking
- Live console output
- AI agent collaboration logs
- Assessment typically takes 5-15 minutes

### **Explore Results**
- **Interactive Discovery:** Infrastructure graphs and chat
- **Final Reports:** Professional DOCX/PDF downloads
- **Architecture Diagrams:** Generated infrastructure visuals

---

## **🔧 Management Scripts**

### **Platform Management**
```bash
# Start platform
./build-optimized.sh

# Check health
./health-check.sh

# Stop platform
./stop-platform.sh

# View logs
docker-compose logs -f
```

### **Development Commands**
```bash
# Rebuild specific service
docker-compose build backend
docker-compose up -d backend

# Reset everything
./stop-platform.sh --reset
./build-optimized.sh

# Check service status
docker-compose ps
```

---

## **🌍 Service URLs**

| Service | URL | Description |
|---------|-----|-------------|
| **Command Center** | http://localhost:3000 | Main UI |
| **Backend API** | http://localhost:8000 | Core API |
| **Project Service** | http://localhost:8002 | Project management |
| **Reporting Service** | http://localhost:8003 | Report generation |
| **MegaParse** | http://localhost:5001 | Document parsing |
| **Neo4j Browser** | http://localhost:7474 | Graph database |
| **Weaviate** | http://localhost:8080 | Vector database |
| **MinIO Console** | http://localhost:9001 | Object storage |

### **Default Credentials**
- **Neo4j:** `neo4j` / `password`
- **MinIO:** `minioadmin` / `minioadmin`

---

## **🔍 Troubleshooting**

### **Common Issues**

**"OpenAI API key not configured"**
```bash
# Edit .env file and add your API key
nano .env
# Restart services
docker-compose restart
```

**"Port already in use"**
```bash
# Check what's using the port
netstat -tulpn | grep :3000
# Stop conflicting services or change ports in docker-compose.yml
```

**"Build failed"**
```bash
# Clean Docker cache
docker system prune -a
# Rebuild
./build-optimized.sh
```

**Services not starting**
```bash
# Check Docker Desktop is running
# Verify RAM allocation (8GB minimum)
# Check logs
docker-compose logs [service-name]
```

### **Reset Everything**
```bash
./stop-platform.sh --reset
./build-optimized.sh
```

---

## **📊 Performance Optimization**

### **Docker Settings**
- **RAM:** 8GB minimum, 16GB recommended
- **CPU:** 4+ cores recommended
- **Storage:** SSD preferred for faster builds

### **Build Optimizations**
- ✅ Cache mounts for package managers
- ✅ Multi-stage builds for smaller images
- ✅ Layer optimization
- ✅ BuildKit for advanced caching
- ✅ Parallel builds where possible

---

## **🏢 Enterprise Features**

### **Security**
- Non-root containers
- Health checks
- Environment variable configuration
- Data encryption in transit

### **Scalability**
- Microservices architecture
- Horizontal scaling ready
- Load balancer compatible
- Cloud deployment ready

### **Compliance**
- GDPR compliance validation
- SOX, HIPAA, PCI-DSS support
- Audit trail capabilities
- Data residency controls

---

## **📚 Documentation**

- **[Quick Start Guide](QUICK_START.md)** - Get up and running fast
- **[Architecture Overview](overview_and_mvp.md)** - Detailed technical documentation
- **[Changelog](CHANGELOG.md)** - Version history and updates
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when running)

---

## **🤝 Support**

### **Getting Help**
1. Check the [Quick Start Guide](QUICK_START.md)
2. Run health check: `./health-check.sh`
3. Check logs: `docker-compose logs`
4. Reset platform: `./stop-platform.sh --reset`

### **System Requirements**
- Ensure Docker Desktop has sufficient resources
- Verify OpenAI API key is valid
- Check firewall settings for port access

---

## **🎉 Success Indicators**

✅ **Platform is working correctly when:**
- All services show "Up" status: `docker-compose ps`
- Command Center loads at http://localhost:3000
- You can create projects and upload documents
- AI assessment completes successfully
- Reports are generated and downloadable

---

## **🚀 Welcome to AgentiMigrate!**

Transform your cloud migration assessments with the power of AI. From infrastructure discovery to executive-ready reports, AgentiMigrate delivers enterprise-grade migration planning at the speed of automation.

**Ready to migrate to the cloud? Let's get started!** 🌟
