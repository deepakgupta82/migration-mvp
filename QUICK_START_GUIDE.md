# 🚀 AgentiMigrate Platform - Quick Start Guide

## **One-Command Local Setup**

### **Prerequisites**
- ✅ Windows 10/11 with PowerShell
- ✅ 8GB+ RAM, 10GB+ free disk space  
- ✅ Docker Desktop or Rancher Desktop installed and running
- ✅ LLM API key (Gemini, OpenAI, or Anthropic)

### **Setup Steps**

1. **Clone and navigate to the repository**
   ```powershell
   git clone <repository-url>
   cd migration_platform_2
   ```

2. **Run the unified setup script**
   ```powershell
   .\setup-platform.ps1
   ```

3. **Configure your API key when prompted**
   - Enter your Gemini API key when asked
   - Or manually edit `.env` file if needed

4. **Wait for setup to complete** (10-20 minutes first time)
   - Script will build all Docker images
   - Start all services automatically
   - Perform health checks

5. **Access the platform**
   - 🌐 **Dashboard**: http://localhost:3000/platform-dashboard.html
   - 📚 **Backend API**: http://localhost:8000/docs
   - 📋 **Project Service**: http://localhost:8002/docs
   - 📊 **Reporting Service**: http://localhost:8003/docs

## **Management Commands**

```powershell
# Check platform status
.\setup-platform.ps1 -StatusOnly

# Stop the platform
.\setup-platform.ps1 -StopOnly

# Reset everything (deletes all data)
.\setup-platform.ps1 -Reset

# Skip prerequisites check
.\setup-platform.ps1 -SkipPrerequisites

# Verbose logging
.\setup-platform.ps1 -Verbose
```

## **Service Access Points**

| Service | URL | Credentials |
|---------|-----|-------------|
| **Platform Dashboard** | http://localhost:3000/platform-dashboard.html | None |
| **Backend API** | http://localhost:8000/docs | None |
| **Project Service** | http://localhost:8002/docs | None |
| **Reporting Service** | http://localhost:8003/docs | None |
| **MegaParse Service** | http://localhost:5001 | None |
| **Neo4j Browser** | http://localhost:7474 | neo4j / password |
| **Weaviate Console** | http://localhost:8080 | None |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

## **API Key Configuration**

### **Get Your API Keys**
- **Google/Gemini**: https://aistudio.google.com/app/apikey
- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/

### **Configure in .env file**
```env
# Choose your preferred provider
LLM_PROVIDER=google

# Add your API key
GOOGLE_API_KEY=your_actual_api_key_here
```

## **Troubleshooting**

### **Common Issues**

1. **Docker not running**
   ```
   Error: Docker daemon not accessible
   Solution: Start Docker Desktop or Rancher Desktop
   ```

2. **Port conflicts**
   ```
   Error: Port already in use
   Solution: Stop other services or use .\setup-platform.ps1 -Reset
   ```

3. **Build failures**
   ```
   Error: Docker build failed
   Solution: Check logs in logs/ directory, ensure stable internet connection
   ```

4. **API key not working**
   ```
   Error: LLM API calls failing
   Solution: Verify API key in .env file, check API key permissions
   ```

### **Log Files**
- **Setup logs**: `logs/platform_setup_YYYY-MM-DD_HH-mm-ss.log`
- **Master log**: `logs/platform_master.log`
- **Service logs**: `docker compose logs [service-name]`

### **Reset Platform**
If you encounter persistent issues:
```powershell
.\setup-platform.ps1 -Reset
# Then run setup again
.\setup-platform.ps1
```

## **Next Steps**

1. **Explore the API Documentation**
   - Visit http://localhost:8000/docs
   - Try the interactive API endpoints

2. **Upload Documents**
   - Use the MegaParse service to process documents
   - Documents are stored in MinIO object storage

3. **Create Projects**
   - Use the Project Service API to create migration projects
   - Assign assessments to projects

4. **Generate Reports**
   - Use the Reporting Service to create migration assessment reports
   - Reports are generated using AI analysis

## **Architecture Overview**

The platform uses modern enterprise architecture:
- **CQRS Pattern**: Command Query Responsibility Segregation
- **Domain-Driven Design**: Clean separation of business logic
- **Microservices**: Independent, scalable services
- **Event-Driven**: Asynchronous processing with message queues
- **Cloud-Ready**: Designed for serverless deployment

## **Support**

- **Documentation**: Check README.md for detailed information
- **Logs**: Review log files in `logs/` directory
- **Issues**: Check Docker container logs with `docker compose logs`
- **Reset**: Use `.\setup-platform.ps1 -Reset` for clean restart
