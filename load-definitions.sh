#!/bin/bash

# Load RabbitMQ definitions into the cluster
echo "=== Loading RabbitMQ Definitions ==="

# Wait for all pods to be ready
echo "Waiting for RabbitMQ cluster to be ready..."
kubectl wait --for=condition=ready pod -l app=rabbitmq-stg --timeout=300s

if [ $? -ne 0 ]; then
    echo "❌ Timeout waiting for RabbitMQ cluster to be ready"
    exit 1
fi

# Get the first pod name
FIRST_POD=$(kubectl get pods -l app=rabbitmq-stg -o jsonpath='{.items[0].metadata.name}')

if [ -z "$FIRST_POD" ]; then
    echo "❌ No RabbitMQ pods found"
    exit 1
fi

echo "✅ Using pod: $FIRST_POD"

# Wait a bit for the cluster to stabilize
echo "Waiting for cluster to stabilize..."
sleep 30

# Check cluster status
echo "Checking cluster status..."
kubectl exec $FIRST_POD -- rabbitmqctl cluster_status

# Load definitions
echo "Loading definitions from /etc/rabbitmq/definitions.json..."
kubectl exec $FIRST_POD -- rabbitmqctl import_definitions /etc/rabbitmq/definitions.json

if [ $? -eq 0 ]; then
    echo "✅ Definitions loaded successfully!"
else
    echo "❌ Failed to load definitions"
    exit 1
fi

# Verify some queues were created
echo "Verifying queues were created..."
kubectl exec $FIRST_POD -- rabbitmqctl list_queues name messages

echo "✅ RabbitMQ definitions loaded successfully!"