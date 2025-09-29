# 🚀 Platform Startup Optimization Guide

## ⚡ **Quick Start (Optimized Workflow)**

### **First Time Setup**
```powershell
# 1. Build images once (8-15 minutes)
.\build-images.ps1

# 2. Start platform fast (2-3 minutes)
.\start-platform-fast.ps1
```

### **Daily Development**
```powershell
# Fast startup using pre-built images (2-3 minutes)
.\start-platform-fast.ps1

# Stop platform
.\start-platform-fast.ps1 -StopOnly

# Restart platform
.\start-platform-fast.ps1 -Restart
```

---

## 📊 **Performance Comparison**

| Method | First Run | Subsequent Runs | Image Size | Use Case |
|--------|-----------|-----------------|------------|----------|
| **Old Method** | 20+ minutes | 20+ minutes | 6GB+ | ❌ Slow |
| **Optimized Full** | 12 minutes | 2-3 minutes | 4GB | ✅ Production |
| **Optimized Minimal** | 5 minutes | 2-3 minutes | 1GB | ✅ Development |

---

## 🛠️ **Available Scripts**

### **Build Scripts**
```powershell
# Build all images (full AI/ML stack)
.\build-images.ps1

# Build minimal images (no heavy ML dependencies)
.\build-images.ps1 -Minimal

# Build specific components
.\build-images.ps1 -Frontend
.\build-images.ps1 -Backend
.\build-images.ps1 -Services

# Force rebuild all images
.\build-images.ps1 -Force

# Check what images are built
.\check-images.ps1
```

### **Startup Scripts**
```powershell
# Fast startup (uses pre-built images)
.\start-platform-fast.ps1

# Minimal mode (no AI/ML features)
.\start-platform-fast.ps1 -Profile minimal

# Core mode (basic AI features)
.\start-platform-fast.ps1 -Profile core

# Full mode (all features)
.\start-platform-fast.ps1 -Profile full

# Development mode (with volume mounts)
.\start-platform-fast.ps1 -DevMode

# Traditional startup (builds every time)
.\run-mpv.ps1
```

### **Management Scripts**
```powershell
# Stop platform
.\start-platform-fast.ps1 -StopOnly

# Restart platform
.\start-platform-fast.ps1 -Restart

# Health check
.\start-platform-fast.ps1 -HealthCheck

# Check image status
.\check-images.ps1
```

---

## 🎯 **Startup Profiles**

### **Minimal Profile** (Fastest - 1-2 minutes)
- ✅ Frontend UI
- ✅ Basic backend API
- ✅ Project management
- ❌ No AI/ML features
- ❌ No document processing
- **Use for**: UI development, basic testing

### **Core Profile** (Fast - 2-3 minutes)
- ✅ Frontend UI
- ✅ Full backend with AI
- ✅ Project management
- ✅ Report generation
- ❌ No document processing
- **Use for**: Most development work

### **Full Profile** (Complete - 3-4 minutes)
- ✅ All features enabled
- ✅ Document processing
- ✅ Complete AI/ML stack
- **Use for**: Production, full testing

---

## 🔧 **Development Workflow**

### **Initial Setup**
```powershell
# 1. Clone repository
git clone <repository-url>
cd migration_platform_2

# 2. Build images once
.\build-images.ps1 -Minimal  # For development
# OR
.\build-images.ps1           # For full features

# 3. Start platform
.\start-platform-fast.ps1 -Profile minimal  # For development
# OR
.\start-platform-fast.ps1                   # For full features
```

### **Daily Development**
```powershell
# Start with development mode (hot reloading)
.\start-platform-fast.ps1 -DevMode -Profile minimal

# Make code changes...

# Restart if needed
.\start-platform-fast.ps1 -Restart

# Stop when done
.\start-platform-fast.ps1 -StopOnly
```

### **When to Rebuild**
```powershell
# Rebuild when dependencies change
.\build-images.ps1 -Force

# Rebuild specific service
.\build-images.ps1 -Backend
```

---

## 🐳 **Docker Image Management**

### **Check Image Status**
```powershell
# See what's built and sizes
.\check-images.ps1

# List all platform images
docker images | findstr migration_platform
```

### **Cleanup**
```powershell
# Remove unused images
docker image prune -f

# Remove all platform images (forces rebuild)
docker images | findstr migration_platform | ForEach-Object { docker rmi $_.Split()[2] }
```

---

## 🚨 **Troubleshooting**

### **"Missing required images" Error**
```powershell
# Build the missing images
.\build-images.ps1

# Or check what's missing
.\check-images.ps1
```

### **"Build failed" Error**
```powershell
# Clean Docker cache and rebuild
docker system prune -a
.\build-images.ps1 -Force
```

### **Services not starting**
```powershell
# Check service status
.\start-platform-fast.ps1 -HealthCheck

# View logs
docker compose logs -f [service-name]
```

### **Out of disk space**
```powershell
# Clean up Docker
docker system prune -a --volumes

# Use minimal profile
.\build-images.ps1 -Minimal
.\start-platform-fast.ps1 -Profile minimal
```

---

## 💡 **Pro Tips**

1. **Use minimal profile for development** - Much faster and lighter
2. **Build images once per day** - Only rebuild when dependencies change
3. **Use development mode** - Enables hot reloading for faster iteration
4. **Check image status regularly** - Know what's built and what needs rebuilding
5. **Clean up regularly** - Remove unused Docker images to save space

---

## 📈 **Expected Results**

After implementing these optimizations:

- ✅ **Startup time**: 20 minutes → 2-3 minutes (85% improvement)
- ✅ **Image size**: 6GB → 1-2GB (70% reduction for minimal)
- ✅ **Development experience**: Much faster iteration cycles
- ✅ **Resource usage**: Significantly reduced during development
- ✅ **Team productivity**: Faster onboarding and daily workflows
