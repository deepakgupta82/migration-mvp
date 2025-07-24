#!/bin/bash
# =====================================================================================
# AgentiMigrate Platform - Database Initialization Runner
# Coordinates all database initialization in proper sequence
# =====================================================================================

set -e  # Exit on any error

# Color functions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration from environment variables
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-projectdb}
POSTGRES_USER=${POSTGRES_USER:-projectuser}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-projectpass}

NEO4J_HOST=${NEO4J_HOST:-neo4j}
NEO4J_PORT=${NEO4J_PORT:-7687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}

WEAVIATE_URL=${WEAVIATE_URL:-http://weaviate:8080}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-minio:9000}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin}

# Wait for service to be ready
wait_for_service() {
    local service_name=$1
    local host=$2
    local port=$3
    local max_attempts=${4:-30}
    local delay=${5:-5}
    
    log_info "Waiting for $service_name to be ready at $host:$port..."
    
    for i in $(seq 1 $max_attempts); do
        if timeout 5 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
            log_success "$service_name is ready!"
            return 0
        fi
        
        log_info "Attempt $i/$max_attempts: $service_name not ready, waiting ${delay}s..."
        sleep $delay
    done
    
    log_error "$service_name did not become ready within timeout"
    return 1
}

# Wait for HTTP service to be ready
wait_for_http_service() {
    local service_name=$1
    local url=$2
    local max_attempts=${3:-30}
    local delay=${4:-5}
    
    log_info "Waiting for $service_name to be ready at $url..."
    
    for i in $(seq 1 $max_attempts); do
        if curl -s -f "$url" >/dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi
        
        log_info "Attempt $i/$max_attempts: $service_name not ready, waiting ${delay}s..."
        sleep $delay
    done
    
    log_error "$service_name did not become ready within timeout"
    return 1
}

# Initialize PostgreSQL database
init_postgres() {
    log_info "Initializing PostgreSQL database..."
    
    # Wait for PostgreSQL to be ready
    if ! wait_for_service "PostgreSQL" "$POSTGRES_HOST" "$POSTGRES_PORT"; then
        return 1
    fi
    
    # Additional wait for PostgreSQL to fully initialize
    sleep 10
    
    # Check if database exists and is accessible
    log_info "Testing PostgreSQL connection..."
    if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
        log_error "Cannot connect to PostgreSQL database"
        return 1
    fi
    
    # Run initialization script
    log_info "Running PostgreSQL initialization script..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /app/init-postgres.sql; then
        log_success "PostgreSQL initialization completed successfully"
        return 0
    else
        log_error "PostgreSQL initialization failed"
        return 1
    fi
}

# Initialize Neo4j graph database
init_neo4j() {
    log_info "Initializing Neo4j graph database..."
    
    # Wait for Neo4j to be ready
    if ! wait_for_service "Neo4j" "$NEO4J_HOST" "$NEO4J_PORT"; then
        return 1
    fi
    
    # Additional wait for Neo4j to fully initialize
    sleep 15
    
    # Test Neo4j connection using cypher-shell
    log_info "Testing Neo4j connection..."
    local neo4j_uri="neo4j://$NEO4J_HOST:$NEO4J_PORT"
    
    # Try to connect and run a simple query
    if echo "RETURN 1;" | cypher-shell -a "$neo4j_uri" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" >/dev/null 2>&1; then
        log_info "Neo4j connection successful"
    else
        log_warning "Cannot connect to Neo4j with cypher-shell, trying alternative method..."
        
        # Alternative: Use Python neo4j driver
        python3 -c "
import sys
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('$neo4j_uri', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
    with driver.session() as session:
        result = session.run('RETURN 1')
        print('Neo4j connection successful via Python driver')
    driver.close()
except Exception as e:
    print(f'Neo4j connection failed: {e}')
    sys.exit(1)
"
        if [ $? -ne 0 ]; then
            log_error "Cannot connect to Neo4j database"
            return 1
        fi
    fi
    
    # Run initialization script
    log_info "Running Neo4j initialization script..."
    if cypher-shell -a "$neo4j_uri" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -f /app/init-neo4j.cypher; then
        log_success "Neo4j initialization completed successfully"
        return 0
    else
        log_warning "cypher-shell failed, trying Python approach..."
        
        # Alternative: Use Python to run Cypher script
        python3 -c "
import sys
from neo4j import GraphDatabase

# Read the Cypher script
with open('/app/init-neo4j.cypher', 'r') as f:
    cypher_script = f.read()

# Split script into individual statements
statements = [stmt.strip() for stmt in cypher_script.split(';') if stmt.strip() and not stmt.strip().startswith('//')]

try:
    driver = GraphDatabase.driver('$neo4j_uri', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
    with driver.session() as session:
        for i, statement in enumerate(statements):
            if statement:
                try:
                    session.run(statement)
                    print(f'Executed statement {i+1}/{len(statements)}')
                except Exception as e:
                    print(f'Warning: Statement {i+1} failed: {e}')
    driver.close()
    print('Neo4j initialization completed via Python driver')
except Exception as e:
    print(f'Neo4j initialization failed: {e}')
    sys.exit(1)
"
        if [ $? -eq 0 ]; then
            log_success "Neo4j initialization completed successfully via Python"
            return 0
        else
            log_error "Neo4j initialization failed"
            return 1
        fi
    fi
}

# Initialize Weaviate vector database
init_weaviate() {
    log_info "Initializing Weaviate vector database..."
    
    # Wait for Weaviate to be ready
    if ! wait_for_http_service "Weaviate" "$WEAVIATE_URL/v1/.well-known/ready"; then
        return 1
    fi
    
    # Run Weaviate initialization script
    log_info "Running Weaviate initialization script..."
    if python3 /app/init-weaviate.py; then
        log_success "Weaviate initialization completed successfully"
        return 0
    else
        log_error "Weaviate initialization failed"
        return 1
    fi
}

# Initialize MinIO object storage
init_minio() {
    log_info "Initializing MinIO object storage..."
    
    # Wait for MinIO to be ready
    if ! wait_for_http_service "MinIO" "http://$MINIO_ENDPOINT/minio/health/ready"; then
        # Try alternative health check
        if ! wait_for_service "MinIO" "${MINIO_ENDPOINT%:*}" "${MINIO_ENDPOINT#*:}"; then
            return 1
        fi
    fi
    
    # Additional wait for MinIO to fully initialize
    sleep 5
    
    # Run MinIO initialization script
    log_info "Running MinIO initialization script..."
    if python3 /app/init-minio.py; then
        log_success "MinIO initialization completed successfully"
        return 0
    else
        log_error "MinIO initialization failed"
        return 1
    fi
}

# Main initialization function
main() {
    log_info "Starting AgentiMigrate Platform database initialization..."
    log_info "Timestamp: $(date)"
    
    # Track initialization results
    local postgres_success=false
    local neo4j_success=false
    local weaviate_success=false
    local minio_success=false
    
    # Initialize databases in sequence
    log_info "=== Phase 1: PostgreSQL Database ==="
    if init_postgres; then
        postgres_success=true
    else
        log_warning "PostgreSQL initialization failed, continuing with other services..."
    fi
    
    log_info "=== Phase 2: Neo4j Graph Database ==="
    if init_neo4j; then
        neo4j_success=true
    else
        log_warning "Neo4j initialization failed, continuing with other services..."
    fi
    
    log_info "=== Phase 3: Weaviate Vector Database ==="
    if init_weaviate; then
        weaviate_success=true
    else
        log_warning "Weaviate initialization failed, continuing with other services..."
    fi
    
    log_info "=== Phase 4: MinIO Object Storage ==="
    if init_minio; then
        minio_success=true
    else
        log_warning "MinIO initialization failed, continuing..."
    fi
    
    # Summary
    log_info "=== Initialization Summary ==="
    echo "PostgreSQL: $([ "$postgres_success" = true ] && echo "✅ SUCCESS" || echo "❌ FAILED")"
    echo "Neo4j:      $([ "$neo4j_success" = true ] && echo "✅ SUCCESS" || echo "❌ FAILED")"
    echo "Weaviate:   $([ "$weaviate_success" = true ] && echo "✅ SUCCESS" || echo "❌ FAILED")"
    echo "MinIO:      $([ "$minio_success" = true ] && echo "✅ SUCCESS" || echo "❌ FAILED")"
    
    # Determine overall success
    if [ "$postgres_success" = true ] && [ "$neo4j_success" = true ] && [ "$weaviate_success" = true ] && [ "$minio_success" = true ]; then
        log_success "🎉 All database initialization completed successfully!"
        log_info "Platform is ready for use with sample data"
        return 0
    else
        log_warning "⚠️  Some database initializations failed"
        log_info "Platform may have limited functionality"
        return 1
    fi
}

# Install cypher-shell if not available
install_cypher_shell() {
    if ! command -v cypher-shell &> /dev/null; then
        log_info "Installing cypher-shell..."
        
        # Download and install cypher-shell
        wget -O cypher-shell.deb https://dist.neo4j.org/cypher-shell/cypher-shell_5.15.0_all.deb
        dpkg -i cypher-shell.deb || apt-get install -f -y
        rm cypher-shell.deb
        
        if command -v cypher-shell &> /dev/null; then
            log_success "cypher-shell installed successfully"
        else
            log_warning "cypher-shell installation failed, will use Python driver"
        fi
    fi
}

# Pre-initialization setup
log_info "Setting up initialization environment..."
install_cypher_shell

# Run main initialization
main
exit_code=$?

log_info "Database initialization completed with exit code: $exit_code"
exit $exit_code
