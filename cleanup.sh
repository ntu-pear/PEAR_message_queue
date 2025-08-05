#!/bin/bash

echo "=== Cleaning up old RabbitMQ deployment ==="

# Delete Kubernetes resources
echo "Deleting StatefulSet..."
kubectl delete statefulset rabbitmq-stg --ignore-not-found

echo "Deleting Services..."
kubectl delete service rabbitmq-service-stg rabbitmq-headless-stg --ignore-not-found

echo "Deleting PVCs..."
kubectl delete pvc -l app=rabbitmq-stg --ignore-not-found

echo "Waiting for pods to terminate..."
kubectl wait --for=delete pod -l app=rabbitmq-stg --timeout=120s || true

# Clean up Docker images
echo "Cleaning up Docker images..."
docker rmi rabbitmq_service_dev:latest || true
docker rmi localhost:5000/rabbitmq_service_dev:latest || true
docker rmi host.minikube.internal:5000/rabbitmq_service_dev:latest || true

# Clean up any dangling images
docker image prune -f

echo "✅ Cleanup complete!"
echo ""
echo "Now you can run a fresh deployment:"
echo "./deploy-staging.sh"