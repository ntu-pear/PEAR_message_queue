#!/bin/bash

# PEAR RabbitMQ Staging Deployment Script
echo "=== PEAR RabbitMQ Staging Deployment ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if docker is available
if ! command -v docker &> /dev/null; then
    print_error "docker is not installed or not in PATH"
    exit 1
fi

print_status "Starting RabbitMQ deployment..."

# Build Docker image
print_status "Building Docker image..."
docker build --no-cache -f Dockerfile -t rabbitmq_service_dev .
if [ $? -ne 0 ]; then
    print_error "Failed to build Docker image"
    exit 1
fi

# Tag and push to local registry
print_status "Tagging and pushing to local registry..."
docker tag rabbitmq_service_dev:latest localhost:5000/rabbitmq_service_dev:latest
docker push localhost:5000/rabbitmq_service_dev:latest
if [ $? -ne 0 ]; then
    print_error "Failed to push Docker image to local registry"
    exit 1
fi

# Apply Kubernetes manifests
print_status "Applying Kubernetes manifests..."
kubectl apply -f k8s/deployment-stg.yaml
if [ $? -ne 0 ]; then
    print_error "Failed to apply Kubernetes manifests"
    exit 1
fi

# Wait for StatefulSet to be ready
print_status "Waiting for RabbitMQ cluster to be ready..."
kubectl wait --for=condition=ready pod -l app=rabbitmq-stg --timeout=300s
if [ $? -ne 0 ]; then
    print_warning "Timeout waiting for pods to be ready, but deployment may still be in progress"
else
    print_status "RabbitMQ cluster is ready!"
fi

# Load definitions
print_status "Loading RabbitMQ definitions..."
chmod +x load-definitions.sh
./load-definitions.sh
if [ $? -ne 0 ]; then
    print_warning "Failed to load definitions automatically. You can run './load-definitions.sh' manually later."
fi

# Show deployment status
print_status "Deployment status:"
kubectl get pods -l app=rabbitmq-stg
kubectl get services -l app=rabbitmq-stg

print_status "Checking cluster status..."
sleep 10
FIRST_POD=$(kubectl get pods -l app=rabbitmq-stg -o jsonpath='{.items[0].metadata.name}')
if [ ! -z "$FIRST_POD" ]; then
    kubectl exec $FIRST_POD -- rabbitmqctl cluster_status 2>/dev/null || print_warning "Cluster may still be forming..."
fi

echo ""
print_status "=== Deployment Complete ==="
print_status "RabbitMQ Management UI: http://<server-ip>:31672"
print_status "RabbitMQ AMQP Port: <server-ip>:30672"
print_status "Default credentials: admin/pear2025"
echo ""