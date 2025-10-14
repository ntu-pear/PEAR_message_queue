#!/bin/bash

# Local E2E Test Runner for PEAR Message Queue
# This script helps run E2E tests locally with Docker containers

set -e  # Exit on error

echo "==================================="
echo "PEAR Message Queue - E2E Test Runner"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RABBITMQ_IMAGE="${RABBITMQ_IMAGE:-rabbitmq:4.1.1-management}"
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

# Function to check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^$1$"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^$1$"
}

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up containers..."
    docker stop test-rabbitmq test-sqlserver 2>/dev/null || true
    docker rm test-rabbitmq test-sqlserver 2>/dev/null || true
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
echo "Step 1: Starting SQL Server..."
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
    
    # Wait for SQL Server to be ready
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
echo "Step 2: Creating test databases..."
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

print_status "Test databases created"

# Step 3: Start RabbitMQ
echo ""
echo "Step 3: Starting RabbitMQ..."
if container_running "test-rabbitmq"; then
    print_warning "RabbitMQ container already running"
else
    docker run -d \
        --name test-rabbitmq \
        -p 5672:5672 \
        -p 15672:15672 \
        -e RABBITMQ_DEFAULT_USER=admin \
        -e RABBITMQ_DEFAULT_PASS=pear2025 \
        -e RABBITMQ_DEFAULT_VHOST=vhost \
        ${RABBITMQ_IMAGE}
    
    print_status "RabbitMQ container started"
    
    # Wait for RabbitMQ to be ready
    echo "Waiting for RabbitMQ to be ready..."
    sleep 10
    
    for i in {1..30}; do
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
echo "Step 4: Loading RabbitMQ definitions..."
if [ -f "definitions.yaml" ]; then
    docker cp definitions.yaml test-rabbitmq:/tmp/definitions.yaml
    docker exec test-rabbitmq rabbitmqctl import_definitions /tmp/definitions.yaml
    print_status "RabbitMQ definitions loaded"
else
    print_error "definitions.yaml not found in current directory"
    exit 1
fi

# Step 5: Install Python dependencies
echo ""
echo "Step 5: Installing Python test dependencies..."
if [ -f "tests/requirements.txt" ]; then
    pip install -q -r tests/requirements.txt
    print_status "Python dependencies installed"
else
    print_warning "tests/requirements.txt not found, skipping..."
fi

# Step 6: Set environment variables
echo ""
echo "Step 6: Setting environment variables..."
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

print_status "Environment variables configured"

# Step 7: Run tests
echo ""
echo "Step 7: Running E2E tests..."
echo "========================================="
echo ""

if [ $# -eq 0 ]; then
    # Run all tests
    pytest tests/e2e/ -v --tb=short --capture=no
else
    # Run specific test file or pattern
    pytest "$@"
fi

TEST_EXIT_CODE=$?

# Step 8: Display results
echo ""
echo "========================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_status "All tests passed!"
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
        echo "=== SQL Server Logs (last 50 lines) ==="
        docker logs test-sqlserver --tail 50
    fi
fi

exit $TEST_EXIT_CODE
