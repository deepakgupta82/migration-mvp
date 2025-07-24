# 🪟 Nagarro AgentiMigrate Platform - Windows Setup Guide (Rancher Desktop)

## **🎯 Super Quick Start (Recommended)**

### **One-Command Setup**
```powershell
# Open PowerShell as Administrator (recommended)
git clone <repository-url>
cd migration_platform_2
.\start-platform.ps1
```

**That's it!** The script will:
- ✅ Check if Rancher Desktop is installed and running
- ✅ Verify Docker is available through Rancher Desktop
- ✅ Run initial setup if needed
- ✅ Create .env file with configuration
- ✅ Guide you through OpenAI API key setup
- ✅ Build and start the entire platform
- ✅ Open the Command Center at http://localhost:3000

---

## **📋 Prerequisites for Windows**

### **Required Software**
1. **Rancher Desktop for Windows**
   - Download: https://rancherdesktop.io/
   - ⚠️ **Important**: Select 'dockerd (moby)' as container runtime during setup
   - Allocate at least 8GB RAM to containers (16GB recommended)
   - **Why Rancher Desktop?** Enterprise-friendly alternative to Docker Desktop

2. **Git for Windows**
   - Download: https://git-scm.com/download/win
   - Or install via: `winget install Git.Git`

3. **OpenAI API Key**
   - Get one from: https://platform.openai.com/api-keys
   - You'll need this for the AI agents to work

### **System Requirements**
- **Windows 10/11** (64-bit)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space
- **CPU**: Multi-core processor recommended

---

## **🔧 Step-by-Step Setup**

### **Step 1: Install Rancher Desktop**
1. Download Rancher Desktop from https://rancherdesktop.io/
2. Run the installer
3. **Important**: During setup, select 'dockerd (moby)' as container runtime
4. Restart your computer if required
5. Start Rancher Desktop and wait for it to fully load (2-3 minutes)

### **Step 2: Configure Rancher Desktop**
1. Open Rancher Desktop
2. Go to Settings (gear icon)
3. **Container Engine**:
   - Ensure 'dockerd (moby)' is selected (not containerd)
4. **Resources**:
   - Set Memory to at least 8GB (16GB recommended)
   - Set CPUs to at least 4 cores
5. **Kubernetes**: You can disable this if not needed (saves resources)
6. Click "Apply" and wait for restart

### **Step 3: Clone the Repository**
```powershell
# Open PowerShell
git clone <repository-url>
cd migration_platform_2
```

### **Step 4: Run Setup**
```powershell
# Option 1: Automated setup (recommended)
.\start-platform.ps1

# Option 2: Manual setup
.\setup.ps1
# Then edit .env file to add your OpenAI API key
# Then run: .\build-optimized.bat
```

### **Step 5: Configure OpenAI API Key**
1. Get your API key from https://platform.openai.com/api-keys
2. Edit the `.env` file (created by setup)
3. Replace `your_openai_api_key_here` with your actual API key
4. Save the file

### **Step 6: Start the Platform**
```powershell
# If you used start-platform.ps1, it's already running
# Otherwise, run:
.\build-optimized.bat
```

---

## **🌍 Access the Platform**

Once running, access these URLs:

| Service | URL | Description |
|---------|-----|-------------|
| **Command Center** | http://localhost:3000 | Main UI |
| **Backend API** | http://localhost:8000/docs | API Documentation |
| **Neo4j Browser** | http://localhost:7474 | Graph Database |
| **MinIO Console** | http://localhost:9001 | Object Storage |

**Default Credentials:**
- Neo4j: `neo4j` / `password`
- MinIO: `minioadmin` / `minioadmin`

---

## **🔧 Windows-Specific Management**

### **PowerShell Scripts**
```powershell
# Start platform (with setup if needed)
.\start-platform.ps1

# Manual setup only
.\setup.ps1

# Build and run platform
.\run-mvp.ps1

# Stop platform
.\run-mvp.ps1 -StopOnly

# Reset everything (removes all data)
.\run-mvp.ps1 -Reset

# Health check
.\health-check.bat
```

### **Command Prompt Scripts**
```cmd
# Build and run platform
build-optimized.bat

# Health check
health-check.bat

# Stop platform
stop-platform.bat
```

### **Docker Commands**
```powershell
# Check service status
docker compose ps

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend

# Stop all services
docker compose down

# Restart a service
docker compose restart backend
```

---

## **🚨 Troubleshooting Windows Issues**

### **"Rancher Desktop not running"**
1. Start Rancher Desktop from Start Menu
2. Wait for the Rancher icon to appear in system tray (2-3 minutes)
3. Ensure 'dockerd (moby)' is selected in Settings
4. Run the setup script again

### **"Execution Policy" Error**
```powershell
# Run this in PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **"Port already in use"**
```powershell
# Check what's using port 3000
netstat -ano | findstr :3000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### **"Build failed" or "Out of space"**
```powershell
# Clean Docker cache
docker system prune -a

# Free up space
docker volume prune

# Restart Docker Desktop
```

### **"Services not starting"**
1. Check Docker Desktop has enough RAM (8GB minimum)
2. Restart Docker Desktop
3. Run: `docker compose down` then `.\build-optimized.bat`

### **"OpenAI API errors"**
1. Verify your API key is correct in `.env` file
2. Check you have credits in your OpenAI account
3. Restart the backend: `docker compose restart backend`

---

## **⚡ Performance Tips for Windows**

### **Rancher Desktop Optimization**
1. **Select dockerd (moby)**: Much faster than containerd for Docker Compose
2. **Allocate RAM**: 16GB to containers if you have 32GB+ system RAM
3. **Use SSD**: Store container data on SSD for faster builds
4. **Disable Kubernetes**: If not needed, disable to save resources
5. **Close Apps**: Close unnecessary applications during builds

### **Windows-Specific Settings**
1. **Disable Windows Defender** real-time scanning for project folder (temporarily)
2. **Use PowerShell** instead of Command Prompt for better performance
3. **Run as Administrator** for better file system performance

### **Build Optimization**
```powershell
# Enable BuildKit for faster builds (automatic in our scripts)
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
```

---

## **🆘 Getting Help**

### **Check Everything is Working**
```powershell
# Run comprehensive health check
.\health-check.bat

# Check Docker status
docker --version
docker compose version
docker ps
```

### **Reset Everything**
```powershell
# Complete reset (removes all data)
.\run-mvp.ps1 -Reset

# Then start fresh
.\start-platform.ps1
```

### **Common Windows Commands**
```powershell
# Check Windows version
winver

# Check available RAM
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory

# Check disk space
Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID, FreeSpace, Size
```

---

## **🎉 Success!**

If everything is working, you should see:
- ✅ Docker Desktop running with whale icon in system tray
- ✅ All services showing "Up" in `docker compose ps`
- ✅ Command Center accessible at http://localhost:3000
- ✅ Ability to create projects and upload documents

**Welcome to the Nagarro AgentiMigrate Platform on Windows!** 🚀
