#!/bin/bash

# Full E2E Test Runner with Services for PEAR Message Queue
# This script runs complete E2E tests including Activity and Scheduler services

set -e  # Exit on error

echo "=============================================="
echo "PEAR Message Queue - Full E2E Test Runner"
echo "with Activity & Scheduler Services"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these with your registry IPs
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-192.168.188.184:5000/rabbitmq_service_dev:latest}"
ACTIVITY_SERVICE_IMAGE="${ACTIVITY_SERVICE_IMAGE:-192.168.188.186:5000/activity_service_dev:latest}"
SCHEDULER_SERVICE_IMAGE="${SCHEDULER_SERVICE_IMAGE:-192.168.188.173:5000/pear_schedule:latest}"
SQLSERVER_IMAGE="mcr.microsoft.com/mssql/server:2022-latest"
DB_PASSWORD="Fyppear@test"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^$1$"
}

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up containers..."
    docker stop test-rabbitmq test-sqlserver test-activity-service test-scheduler-service 2>/dev/null || true
    docker rm test-rabbitmq test-sqlserver test-activity-service test-scheduler-service 2>/dev/null || true
    print_status "Cleanup completed"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

print_status "Docker is running"

# Step 1: Start SQL Server
echo ""
print_info "Step 1/7: Starting SQL Server..."
if container_running "test-sqlserver"; then
    print_warning "SQL Server container already running"
else
    docker run -d \
        --name test-sqlserver \
        -e 'ACCEPT_EULA=Y' \
        -e "SA_PASSWORD=${DB_PASSWORD}" \
        -e 'MSSQL_PID=Developer' \
        -p 1433:1433 \
        ${SQLSERVER_IMAGE}
    
    print_status "SQL Server container started"
    
    echo "Waiting for SQL Server to be ready..."
    sleep 15
    
    for i in {1..30}; do
        if docker exec test-sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "${DB_PASSWORD}" -Q "SELECT 1" > /dev/null 2>&1; then
            print_status "SQL Server is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
fi

# Step 2: Create test databases
echo ""
print_info "Step 2/7: Creating test databases..."
docker exec test-sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "${DB_PASSWORD}" -Q "
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'activity_service_test')
BEGIN
    CREATE DATABASE activity_service_test;
END

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'scheduler_service_test')
BEGIN
    CREATE DATABASE scheduler_service_test;
END
" > /dev/null 2>&1

print_status "Test databases created (activity_service_test, scheduler_service_test)"

# Step 3: Start RabbitMQ
echo ""
print_info "Step 3/7: Starting RabbitMQ..."
if container_running "test-rabbitmq"; then
    print_warning "RabbitMQ container already running"
else
    # Try to pull from registry first, fallback to Docker Hub
    docker pull ${RABBITMQ_IMAGE} 2>/dev/null || docker pull rabbitmq:4.1.1-management
    
    docker run -d \
        --name test-rabbitmq \
        -p 5672:5672 \
        -p 15672:15672 \
        -e RABBITMQ_DEFAULT_USER=admin \
        -e RABBITMQ_DEFAULT_PASS=pear2025 \
        -e RABBITMQ_DEFAULT_VHOST=vhost \
        ${RABBITMQ_IMAGE}
    
    print_status "RabbitMQ container started"
    
    echo "Waiting for RabbitMQ to be ready..."
    sleep 15
    
    for i in {1..60}; do
        if curl -s -u admin:pear2025 http://localhost:15672/api/health/checks/alarms > /dev/null 2>&1; then
            print_status "RabbitMQ is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
fi

# Step 4: Load RabbitMQ definitions
echo ""
print_info "Step 4/7: Loading RabbitMQ definitions..."
if [ -f "definitions.yaml" ]; then
    docker cp definitions.yaml test-rabbitmq:/tmp/definitions.yaml
    docker exec test-rabbitmq rabbitmqctl import_definitions /tmp/definitions.yaml
    sleep 3
    print_status "RabbitMQ definitions loaded"
else
    print_error "definitions.yaml not found in current directory"
    exit 1
fi

# Step 5: Start Activity Service
echo ""
print_info "Step 5/7: Starting Activity Service..."
if container_running "test-activity-service"; then
    print_warning "Activity Service already running"
else
    print_info "Pulling Activity Service image..."
    docker pull ${ACTIVITY_SERVICE_IMAGE}
    
    docker run -d \
        --name test-activity-service \
        -p 8001:8000 \
        -e DB_SERVER=host.docker.internal \
        -e DB_PORT=1433 \
        -e DB_DATABASE=activity_service_test \
        -e DB_USERNAME=sa \
        -e DB_PASSWORD="${DB_PASSWORD}" \
        -e RABBITMQ_HOST=host.docker.internal \
        -e RABBITMQ_PORT=5672 \
        -e RABBITMQ_VHOST=vhost \
        -e RABBITMQ_USER=admin \
        -e RABBITMQ_PASSWORD=pear2025 \
        ${ACTIVITY_SERVICE_IMAGE}
    
    print_status "Activity Service container started"
    
    echo "Waiting for Activity Service to be ready..."
    sleep 15
    
    for i in {1..30}; do
        if curl -s http://localhost:8001/health > /dev/null 2>&1 || curl -s http://localhost:8001/ > /dev/null 2>&1; then
            print_status "Activity Service is ready on port 8001"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
fi

# Step 6: Start Scheduler Service
echo ""
print_info "Step 6/7: Starting Scheduler Service..."
if container_running "test-scheduler-service"; then
    print_warning "Scheduler Service already running"
else
    print_info "Pulling Scheduler Service image..."
    docker pull ${SCHEDULER_SERVICE_IMAGE}
    
    docker run -d \
        --name test-scheduler-service \
        -p 8002:8000 \
        -e DB_SERVER=host.docker.internal \
        -e DB_PORT=1433 \
        -e DB_DATABASE=scheduler_service_test \
        -e DB_USERNAME=sa \
        -e DB_PASSWORD="${DB_PASSWORD}" \
        -e RABBITMQ_HOST=host.docker.internal \
        -e RABBITMQ_PORT=5672 \
        -e RABBITMQ_VHOST=vhost \
        -e RABBITMQ_USER=admin \
        -e RABBITMQ_PASSWORD=pear2025 \
        ${SCHEDULER_SERVICE_IMAGE}
    
    print_status "Scheduler Service container started"
    
    echo "Waiting for Scheduler Service to be ready..."
    sleep 15
    
    for i in {1..30}; do
        if curl -s http://localhost:8002/health > /dev/null 2>&1 || curl -s http://localhost:8002/ > /dev/null 2>&1; then
            print_status "Scheduler Service is ready on port 8002"
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""
fi

# Verify all services
echo ""
print_info "Verifying all services..."
echo "  SQL Server:        $(docker ps --filter name=test-sqlserver --format '{{.Status}}')"
echo "  RabbitMQ:          $(docker ps --filter name=test-rabbitmq --format '{{.Status}}')"
echo "  Activity Service:  $(docker ps --filter name=test-activity-service --format '{{.Status}}')"
echo "  Scheduler Service: $(docker ps --filter name=test-scheduler-service --format '{{.Status}}')"

# Step 7: Install Python dependencies
echo ""
print_info "Step 7/7: Installing Python test dependencies..."
if [ -f "tests/requirements.txt" ]; then
    pip install -q -r tests/requirements.txt
    print_status "Python dependencies installed"
else
    print_warning "tests/requirements.txt not found, skipping..."
fi

# Set environment variables
export DB_SERVER=localhost
export DB_PORT=1433
export DB_USERNAME=sa
export DB_PASSWORD="${DB_PASSWORD}"
export ACTIVITY_DB_NAME=activity_service_test
export SCHEDULER_DB_NAME=scheduler_service_test
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_VHOST=vhost
export RABBITMQ_USER=admin
export RABBITMQ_PASSWORD=pear2025
export ACTIVITY_SERVICE_URL=http://localhost:8001
export SCHEDULER_SERVICE_URL=http://localhost:8002

print_status "Environment variables configured"

# Run tests
echo ""
echo "=============================================="
print_info "Running FULL E2E Tests (Infrastructure + Service Integration)"
echo "=============================================="
echo ""

if [ $# -eq 0 ]; then
    # Run ALL tests including service integration
    pytest tests/e2e/ -v --tb=short --capture=no
else
    # Run specific test file or pattern
    pytest "$@"
fi

TEST_EXIT_CODE=$?

# Display results
echo ""
echo "=============================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_status "All tests passed! ✨"
else
    print_error "Some tests failed (exit code: $TEST_EXIT_CODE)"
fi

# Optional: Display container logs on failure
if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo ""
    read -p "Display container logs? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "=== RabbitMQ Logs (last 50 lines) ==="
        docker logs test-rabbitmq --tail 50
        echo ""
        echo "=== Activity Service Logs (last 50 lines) ==="
        docker logs test-activity-service --tail 50
        echo ""
        echo "=== Scheduler Service Logs (last 50 lines) ==="
        docker logs test-scheduler-service --tail 50
        echo ""
        echo "=== SQL Server Logs (last 50 lines) ==="
        docker logs test-sqlserver --tail 50
    fi
fi

exit $TEST_EXIT_CODE
