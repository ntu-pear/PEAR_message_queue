# PEAR Message Queue

## Overview

This repository contains the RabbitMQ configuration and deployment files configured with rolling updates.

- **RabbitMQ Version**: 4.1.1 with management plugin
- **Cluster Size**: 3 nodes for high availability
- **Queue Type**: Quorum queues with dead letter exchanges
- **Platform**: Kubernetes (StatefulSet)

## Table of Contents

- [Getting Started](#getting-started)
- [Architecture](#architecture)
- [CI/CD Pipeline](#cicd-pipeline)
- [Testing](#testing)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Development](#development)

## Getting Started

### Prerequisites
1. **Git**: Ensure Git is installed on your system
2. **NTU VPN**: Install the NTU VPN to access internal resources
3. **nginx with the stream module**: Refer to documentation on Confluence
4. **Python 3.11+**: For running E2E tests locally
5. **Docker**: For local testing with containers

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd PEAR_message_queue

# For deployment
./deploy-staging.sh

# For local testing
./run_tests.sh  # Linux/Mac
# or
run_tests.bat  # Windows
```

## Architecture

### System Overview

The PEAR message queue system connects the Activity Service and Scheduler Service through RabbitMQ, enabling asynchronous communication and data synchronization.

```
┌─────────────────┐      ┌──────────────┐      ┌──────────────────┐
│ Activity Service│─────▶│   RabbitMQ   │─────▶│ Scheduler Service│
└─────────────────┘      └──────────────┘      └──────────────────┘
        │                       │                        │
        ▼                       ▼                        ▼
┌─────────────────┐      ┌──────────────┐      ┌──────────────────┐
│ Activity DB     │      │  Message     │      │ Scheduler DB     │
│ (SQL Server)    │      │  Queues      │      │ (SQL Server)     │
└─────────────────┘      └──────────────┘      └──────────────────┘
```

### Exchanges

All exchanges are **topic exchanges** for flexible routing:

- **`patient.updates`** - Patient-related events
  - Routing pattern: `patient.{action}.{patient_id}`
  - Actions: created, updated, deleted, medication.created, medication.updated, medication.deleted

- **`activity.updates`** - Activity-related events
  - Routing pattern: `activity.{entity}.{action}.{id}`
  - Entities: activity, centre_activity, exclusion, routine, preference, recommendation

- **`reconciliation.events`** - Data reconciliation events
  - Routing pattern: `drift.detected.{entity_type}`

- **`system.dlx`** - Dead letter exchange (direct type)
  - Routes failed messages to appropriate DLQs

### Queues

All queues are configured as **quorum queues** with:
- **TTL**: 5 minutes (300000ms)
- **Delivery Limit**: 3 attempts
- **Dead Letter Exchange**: Routes to appropriate DLQ after max retries
- **Durability**: All messages are persistent

#### Patient Queues

**Activity Service Queues:**
- `patient.created`
- `patient.updated` 
- `patient.deleted`
- `patient.medication.created`
- `patient.medication.updated`
- `patient.medication.deleted`

**Scheduler Service Queues:**
- `scheduler.patient.created`
- `scheduler.patient.updated`
- `scheduler.patient.deleted`
- `scheduler.patient.medication.created`
- `scheduler.patient.medication.updated`
- `scheduler.patient.medication.deleted`

#### Activity Queues

**Activity Service Queues:**
- `activity.created` / `activity.updated` / `activity.deleted`
- `activity.centre_activity.created` / `updated` / `deleted`
- `activity.centre_activity_exclusion.created` / `updated` / `deleted`
- `activity.routine.created` / `updated` / `deleted`
- `activity.preference.created` / `updated` / `deleted`
- `activity.recommendation.created` / `updated` / `deleted`

**Scheduler Service Queues:**
- Mirror all above queues with `scheduler.` prefix

#### Dead Letter Queues (DLQ)

DLQs use **classic queue type** for better inspection:
- `dlq.patient` / `dlq.scheduler.patient`
- `dlq.patient.medication` / `dlq.scheduler.patient.medication`
- `dlq.activity` / `dlq.scheduler.activity`
- `dlq.activity.centre_activity` / `dlq.scheduler.activity.centre_activity`
- `dlq.activity.centre_activity_exclusion` / `dlq.scheduler.activity.centre_activity_exclusion`
- `dlq.activity.routine` / `dlq.scheduler.activity.routine`
- `dlq.activity.preference` / `dlq.scheduler.activity.preference`
- `dlq.activity.recommendation` / `dlq.scheduler.activity.recommendation`
- `dlq.reconciliation.drift`

### Message Flow Example

```
1. Activity Service creates/updates activity
   ↓
2. Publish message to "activity.updates" exchange
   ↓
3. Message routed to:
   - activity.created queue (for Activity Service consumers)
   - scheduler.activity.created queue (for Scheduler Service)
   ↓
4. Scheduler Service consumes message
   ↓
5. Update scheduler database with activity info
   ↓
6. Generate/update schedules accordingly
```

## CI/CD Pipeline

### Continuous Integration (CI)

The CI pipeline runs automatically on:
- Push to `main`, `staging`, or `test/**` branches
- Pull requests to `main` or `staging`
- Manual workflow dispatch

**Pipeline Steps:**

1. **Setup Phase**
   - Start SQL Server container
   - Create test databases (Activity & Scheduler)
   - Initialize database schemas
   - Start RabbitMQ container
   - Load RabbitMQ definitions
   - Pull and start service containers

2. **Test Execution**
   - Run E2E tests with pytest
   - Generate test reports
   - Collect logs on failure

3. **Cleanup**
   - Stop all containers
   - Upload test artifacts

**Configuration:** `.github/workflows/ci.yml`

### Continuous Deployment (CD)

Deployment to staging/production environments using Kubernetes.

**Configuration:** `.github/workflows/cd.yml`

## Testing

### E2E Test Suite

Comprehensive end-to-end tests covering:

1. **Patient Message Flow** (`test_patient_flow.py`)
   - Patient CRUD operations
   - Medication management
   - Message routing verification

2. **Activity Message Flow** (`test_activity_flow.py`)
   - Activity CRUD operations
   - Centre activities
   - Exclusions, preferences, recommendations
   - Routines

3. **Dead Letter Queue** (`test_dlq.py`)
   - Delivery limit verification
   - DLQ routing
   - Message persistence

4. **Infrastructure** (`test_infrastructure.py`)
   - Exchange configuration
   - Queue configuration
   - Connection management

### Running Tests Locally

**Linux/Mac:**
```bash
# Make script executable
chmod +x run_tests.sh

# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/e2e/test_patient_flow.py

# Run with specific pytest options
./run_tests.sh tests/e2e/ -v -k "test_patient_created"
```

**Windows:**
```cmd
# Run all tests
run_tests.bat

# Run specific test
run_tests.bat tests\e2e\test_patient_flow.py
```

### Manual Testing

```bash
# Install dependencies
pip install -r tests/requirements.txt

# Start containers
docker run -d --name test-rabbitmq -p 5672:5672 -p 15672:15672 \
    -e RABBITMQ_DEFAULT_USER=admin \
    -e RABBITMQ_DEFAULT_PASS=pear2025 \
    rabbitmq:4.1.1-management

docker run -d --name test-sqlserver -p 1433:1433 \
    -e 'ACCEPT_EULA=Y' \
    -e 'SA_PASSWORD=Fyppear@test' \
    mcr.microsoft.com/mssql/server:2022-latest

# Load definitions
docker cp definitions.yaml test-rabbitmq:/tmp/definitions.yaml
docker exec test-rabbitmq rabbitmqctl import_definitions /tmp/definitions.yaml

# Run tests
pytest tests/e2e/ -v

# Cleanup
docker stop test-rabbitmq test-sqlserver
docker rm test-rabbitmq test-sqlserver
```

### Test Reports

Test results and artifacts are available in GitHub Actions:
- Test execution logs
- Coverage reports (if enabled)
- Container logs on failure

## Deployment

### Manual Deployment

```bash
# Make scripts executable (Linux/Mac)
chmod +x cleanup.sh deploy-staging.sh

# Remove existing deployment
./cleanup.sh

# Deploy to staging
./deploy-staging.sh
```

### Kubernetes Deployment

```bash
# Build and push image
docker build --no-cache -t rabbitmq_service_dev:latest .
docker tag rabbitmq_service_dev:latest 192.168.188.184:5000/rabbitmq_service_dev:latest
docker push 192.168.188.184:5000/rabbitmq_service_dev:latest

# Deploy to Kubernetes
kubectl apply -f k8s/deployment-stg.yaml

# Verify deployment
kubectl get pods -l app=rabbitmq-stg
kubectl get svc rabbitmq-service-stg

# Check cluster status
kubectl exec rabbitmq-stg-0 -- rabbitmqctl cluster_status
```

### Access Information

**Staging Environment:**
- **Management UI**: http://192.168.188.184:31672
- **AMQP Port**: 192.168.188.184:30672
- **Username**: admin
- **Password**: pear2025

**Production Environment:**
- Details available in confluence documentation

## Monitoring

### Cluster Health

```bash
# Check cluster status
kubectl exec rabbitmq-stg-0 -- rabbitmqctl cluster_status

# Check node status
kubectl exec rabbitmq-stg-0 -- rabbitmqctl node_health_check

# List queues
kubectl exec rabbitmq-stg-0 -- rabbitmqctl list_queues name messages consumers

# List connections
kubectl exec rabbitmq-stg-0 -- rabbitmqctl list_connections
```

### View Logs

```bash
# View pod logs
kubectl logs rabbitmq-stg-0 --tail=100

# Stream logs
kubectl logs -f rabbitmq-stg-0

# View logs from all pods
kubectl logs -l app=rabbitmq-stg
```

### Management UI

Access the RabbitMQ Management UI at http://<server-ip>:31672

Features:
- Queue statistics and messages
- Connection and channel monitoring
- Exchange and binding visualization
- Message publishing and consuming
- User and permission management

### Metrics and Alerts

- **Prometheus**: Metrics endpoint available on management plugin
- **Grafana**: Dashboards for visualization
- **Alerting**: Configure alerts for queue depths, connection issues, etc.

## Development

### Project Structure

```
PEAR_message_queue/
├── .github/
│   └── workflows/
│       ├── ci.yml           # CI pipeline configuration
│       └── cd.yml           # CD pipeline configuration
├── k8s/
│   ├── deployment-stg.yaml  # Staging deployment
│   └── deployment-prod.yaml # Production deployment
├── tests/
│   ├── e2e/
│   │   ├── conftest.py
│   │   ├── test_patient_flow.py
│   │   ├── test_activity_flow.py
│   │   ├── test_dlq.py
│   │   ├── test_infrastructure.py
│   │   └── README.md
│   └── requirements.txt
├── definitions.yaml         # RabbitMQ configuration
├── rabbitmq.conf           # RabbitMQ server config
├── Dockerfile              # Container image
├── pytest.ini              # Pytest configuration
├── run_tests.sh            # Test runner (Linux/Mac)
├── run_tests.bat           # Test runner (Windows)
├── cleanup.sh              # Cleanup script
├── deploy-staging.sh       # Deployment script
└── README.md              # This file
```

### Configuration Files

**`definitions.yaml`**
- Exchanges, queues, and bindings configuration
- User permissions
- Virtual host setup
- Dead letter exchange configuration

**`rabbitmq.conf`**
- Server configuration
- Cluster settings
- Performance tuning
- Plugin configuration

**`Dockerfile`**
- Base image: RabbitMQ 4.1.1 management
- Custom configuration loading
- Health checks

### Environment Variables

**Kubernetes Deployment:**
- `RABBITMQ_ERLANG_COOKIE` - Cluster authentication
- `RABBITMQ_NODENAME` - Node identifier (FQDN)
- `RABBITMQ_VIRTUAL_HOST` - VHost identifier

**Testing:**
- `DB_SERVER`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
- `ACTIVITY_SERVICE_URL`, `SCHEDULER_SERVICE_URL`

### Adding New Message Types

1. **Update `definitions.yaml`:**
   ```yaml
   queues:
     - name: "new_entity.created"
       vhost: "vhost"
       durable: true
       arguments:
         x-queue-type: "quorum"
         x-message-ttl: 300000
         x-dead-letter-exchange: "system.dlx"
   
   bindings:
     - source: "entity.updates"
       destination: "new_entity.created"
       routing_key: "entity.created.*"
   ```

2. **Add E2E test:**
   ```python
   def test_new_entity_flow(self, rabbitmq_channel):
       # Test implementation
       pass
   ```

3. **Update documentation**

4. **Deploy changes**

### Troubleshooting

**Common Issues:**

1. **Connection Refused**
   - Verify RabbitMQ is running
   - Check network connectivity
   - Verify credentials

2. **Queue Not Found**
   - Ensure definitions are loaded
   - Check queue name spelling
   - Verify vhost

3. **Messages Not Routing**
   - Verify exchange exists
   - Check routing key pattern
   - Inspect bindings

4. **DLQ Not Receiving Messages**
   - Verify x-dead-letter-exchange configuration
   - Check delivery-limit setting
   - Inspect DLQ bindings

### Contributing

1. Create feature branch from `staging`
2. Implement changes with tests
3. Run tests locally: `./run_tests.sh`
4. Create pull request to `staging`
5. CI pipeline will run automatically
6. After review and approval, merge to `staging`
7. Deploy to staging environment
8. After validation, merge to `main` for production

### Support

For questions or issues:
- Check existing GitHub issues
- Review Confluence documentation
- Contact PEAR development team

## License

Internal use only - NTU PEAR Project

---

**Last Updated**: October 2025  
**Maintained By**: PEAR Development Team
