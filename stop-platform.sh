#!/bin/bash

# =====================================================================================
# Nagarro AgentiMigrate Platform - Stop Script
# =====================================================================================

echo "🛑 Stopping Nagarro AgentiMigrate Platform"
echo "=========================================="

# Use docker compose or docker-compose based on availability
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Function to stop with options
stop_platform() {
    local option=$1
    
    case $option in
        "soft")
            echo "🔄 Soft stop (containers only)..."
            $DOCKER_COMPOSE stop
            ;;
        "hard")
            echo "🛑 Hard stop (remove containers)..."
            $DOCKER_COMPOSE down --remove-orphans
            ;;
        "reset")
            echo "💥 Full reset (remove containers and volumes)..."
            $DOCKER_COMPOSE down -v --remove-orphans
            echo "🧹 Cleaning up Docker system..."
            docker system prune -f
            ;;
        *)
            echo "🛑 Standard stop (remove containers)..."
            $DOCKER_COMPOSE down --remove-orphans
            ;;
    esac
}

# Check command line arguments
if [ $# -eq 0 ]; then
    echo "Select stop option:"
    echo "1) Soft stop (containers only)"
    echo "2) Standard stop (remove containers)"
    echo "3) Hard reset (remove containers and data)"
    echo ""
    read -p "Enter choice (1-3): " choice
    
    case $choice in
        1)
            stop_platform "soft"
            ;;
        2)
            stop_platform "hard"
            ;;
        3)
            echo "⚠️  WARNING: This will remove all data including projects and uploads!"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_platform "reset"
            else
                echo "❌ Reset cancelled"
                exit 0
            fi
            ;;
        *)
            echo "❌ Invalid choice"
            exit 1
            ;;
    esac
else
    case $1 in
        "--soft")
            stop_platform "soft"
            ;;
        "--hard")
            stop_platform "hard"
            ;;
        "--reset")
            echo "⚠️  WARNING: This will remove all data!"
            read -p "Are you sure? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_platform "reset"
            else
                echo "❌ Reset cancelled"
                exit 0
            fi
            ;;
        "--help")
            echo "Usage: $0 [option]"
            echo ""
            echo "Options:"
            echo "  --soft    Stop containers only (data preserved)"
            echo "  --hard    Remove containers (data preserved)"
            echo "  --reset   Remove containers and all data"
            echo "  --help    Show this help message"
            echo ""
            echo "If no option is provided, interactive mode will be used."
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
fi

echo ""
echo "✅ Platform stopped successfully!"
echo ""
echo "📋 Next steps:"
echo "  🚀 To restart: ./build-optimized.sh"
echo "  🏥 To check status: ./health-check.sh"
echo "  📊 To view Docker usage: docker system df"
