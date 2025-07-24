#!/bin/bash

# =====================================================================================
# Nagarro AgentiMigrate Platform - Health Check Script
# =====================================================================================

echo "🏥 Nagarro AgentiMigrate Platform - Health Check"
echo "================================================"

# Use docker compose or docker-compose based on availability
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "🔍 Checking $service... "
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        echo -e "${GREEN}✅ Healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ Unhealthy${NC}"
        return 1
    fi
}

# Function to check container status
check_container() {
    local container=$1
    echo -n "📦 Checking container $container... "
    
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container.*Up"; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not running${NC}"
        return 1
    fi
}

echo "📊 Container Status:"
echo "==================="

# Check all containers
containers=("frontend_service" "backend_service" "project_service" "reporting_service" "megaparse_service" "postgres_service" "neo4j_service" "weaviate_service" "minio_service")

all_containers_healthy=true
for container in "${containers[@]}"; do
    if ! check_container "$container"; then
        all_containers_healthy=false
    fi
done

echo ""
echo "🌐 Service Health Checks:"
echo "========================="

# Check service endpoints
services_healthy=true

# Frontend
if ! check_service "Frontend" "http://localhost:3000" "200"; then
    services_healthy=false
fi

# Backend API
if ! check_service "Backend API" "http://localhost:8000/docs" "200"; then
    services_healthy=false
fi

# Project Service
if ! check_service "Project Service" "http://localhost:8002/docs" "200"; then
    services_healthy=false
fi

# Reporting Service
if ! check_service "Reporting Service" "http://localhost:8003/docs" "200"; then
    services_healthy=false
fi

# MegaParse Service
if ! check_service "MegaParse Service" "http://localhost:5001" "200"; then
    services_healthy=false
fi

# Neo4j
if ! check_service "Neo4j Browser" "http://localhost:7474" "200"; then
    services_healthy=false
fi

# Weaviate
if ! check_service "Weaviate" "http://localhost:8080/v1/.well-known/ready" "200"; then
    services_healthy=false
fi

# MinIO
if ! check_service "MinIO Console" "http://localhost:9001" "200"; then
    services_healthy=false
fi

echo ""
echo "💾 Data Persistence Check:"
echo "=========================="

# Check if data directories exist
echo -n "📁 Checking minio_data directory... "
if [ -d "minio_data" ]; then
    echo -e "${GREEN}✅ Exists${NC}"
else
    echo -e "${YELLOW}⚠️  Missing${NC}"
fi

echo -n "📁 Checking postgres data volume... "
if docker volume ls | grep -q "postgres_data"; then
    echo -e "${GREEN}✅ Exists${NC}"
else
    echo -e "${YELLOW}⚠️  Missing${NC}"
fi

echo ""
echo "🔧 Configuration Check:"
echo "======================="

# Check .env file
echo -n "📝 Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ Exists${NC}"
    
    # Check if OpenAI API key is configured
    echo -n "🔑 Checking OpenAI API key... "
    if grep -q "your_openai_api_key_here" .env 2>/dev/null; then
        echo -e "${RED}❌ Not configured${NC}"
        echo "   Please edit .env and add your OpenAI API key"
    else
        echo -e "${GREEN}✅ Configured${NC}"
    fi
else
    echo -e "${RED}❌ Missing${NC}"
    echo "   Run build-optimized.sh to create .env file"
fi

echo ""
echo "📈 Resource Usage:"
echo "=================="

# Docker system info
echo "🐳 Docker system usage:"
docker system df

echo ""
echo "📋 Summary:"
echo "==========="

if $all_containers_healthy && $services_healthy; then
    echo -e "${GREEN}🎉 All systems operational!${NC}"
    echo ""
    echo -e "${BLUE}🌍 Access URLs:${NC}"
    echo "   • Frontend: http://localhost:3000"
    echo "   • Backend API: http://localhost:8000"
    echo "   • Neo4j Browser: http://localhost:7474"
    echo "   • MinIO Console: http://localhost:9001"
    exit 0
else
    echo -e "${RED}⚠️  Some issues detected${NC}"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check logs: $DOCKER_COMPOSE logs"
    echo "2. Restart services: $DOCKER_COMPOSE restart"
    echo "3. Rebuild if needed: $DOCKER_COMPOSE build"
    echo "4. Full reset: $DOCKER_COMPOSE down -v && ./build-optimized.sh"
    exit 1
fi
