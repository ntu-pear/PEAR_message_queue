# PEAR Message Queue

## Overview

This repository contains the RabbitMQ configuration and deployment files configured with rolling updates.

- **RabbitMQ Version**: 4.1.1 with management plugin
- **Cluster Size**: 3 nodes for high availability
- **Queue Type**: Quorum queues with dead letter exchanges
- **Platform**: Kubernetes (StatefulSet)

## Getting Started

### Prerequisites
1. **Git**: Ensure Git is installed on your system.
3. **NTU VPN**: Install the NTU VPN to access internal resources.
4. **nginx with the stream module**: Refer to documentation on Confluence

### Manual Deployment
```bash
# Make the script executable (Linux/Mac)
chmod +x cleanup.sh
chmod +x deploy-staging.sh

# Remove images, remove existing k8 deployment
./cleanup.sh

# Run deployment
./deploy-staging.sh
```

### Manual Kubernetes Commands
```bash
# Build and push image
docker build --no-cache -t rabbitmq_service_dev:latest .
docker tag rabbitmq_service_dev-stg:latest localhost:5000/rabbitmq_service_dev-stg:latest
docker push localhost:5000/rabbitmq_service_dev-stg:latest

# Deploy to Kubernetes
kubectl apply -f k8s/deployment-stg.yaml

# Check status
kubectl get pods -l app=rabbitmq-stg
kubectl get svc rabbitmq-service-stg
```

## Access Information

- **Management UI**: http://<server-ip>:31672
- **AMQP Port**: <server-ip>:30672
- **Username**: admin
- **Password**: pear2025

## Architecture

### Exchanges
- `patient.updates` - Topic exchange for patient-related events
- `activity.updates` - Topic exchange for activity-related events
- `system.dlx` - Dead letter exchange for failed messages

### Queues
All queues are configured as quorum queues with:
- **TTL**: 5 minutes (300000ms)
- **Delivery Limit**: 3 attempts
- **Dead Letter Exchange**: Routes to appropriate DLQ after max retries

#### Patient Queues (Quorom)
- `patient.created`
- `patient.updated` 
- `patient.deleted`

#### Patient Prescription Queues (Quorom)
- `patient.prescription.created`
- `patient.prescription.updated`
- `patient.prescription.deleted`

### Activity Queues (Quorom)
- `activity.centre_activity.created`


#### TODO: Activity Queues
- `activity.centre_activity.updated`
- `activity.centre_activity.deleted`
- `activity.preferences.changed`
- `activity.recommendations.changed`
- `activity.exclusions.changed`

#### Dead Letter Queues (DLQ using classic queues)
- `dlq.patient`
- `dlq.activity.centre_activity`
- `dlq.activity.preferences`
- `dlq.activity.recommendations`
- `dlq.activity.exclusions`
- `dlq.schedule.generated`
- `dlq.schedule.updated`

## Cluster Configuration

The RabbitMQ cluster is configured with:
- **Peer Discovery**: Kubernetes API-based
- **Partition Handling**: Autoheal
- **Erlang Cookie**: Shared across all nodes
- **Node Names**: FQDN format for Kubernetes

## Monitoring and Troubleshooting

### Check Cluster Status
```bash
kubectl exec rabbitmq-stg-0 -- rabbitmqctl cluster_status
```

### View Logs
```bash
kubectl logs rabbitmq-stg-0
```

### Scale Cluster
```bash
kubectl scale statefulset rabbitmq-stg --replicas=5
```


## Development

### Configuration Files
- `Dockerfile` - Container image definition
- `rabbitmq.conf` - RabbitMQ server configuration
- `definitions.yaml` - Exchange, queue, and binding definitions
- `k8s/deployment-stg.yaml` - Kubernetes manifests

### Environment Variables
- `RABBITMQ_ERLANG_COOKIE`  - Cluster authentication
- `RABBITMQ_NODENAME`       - Node identifier
- `RABBITMQ_VIRTUAL_HOST`   - VHost identifier
