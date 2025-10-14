import os
import pytest
import pika
import time
from typing import Generator

# Configuration from environment variables
DB_SERVER = os.getenv('DB_SERVER', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 1433))
DB_USERNAME = os.getenv('DB_USERNAME', 'sa')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Fyppear@test')
ACTIVITY_DB_NAME = os.getenv('ACTIVITY_DB_NAME', 'activity_service_test')
SCHEDULER_DB_NAME = os.getenv('SCHEDULER_DB_NAME', 'scheduler_service_test')

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', 'vhost')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'admin')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'pear2025')

ACTIVITY_SERVICE_URL = os.getenv('ACTIVITY_SERVICE_URL', 'http://localhost:8001')
SCHEDULER_SERVICE_URL = os.getenv('SCHEDULER_SERVICE_URL', 'http://localhost:8002')


@pytest.fixture(scope='session')
def rabbitmq_connection() -> Generator[pika.BlockingConnection, None, None]:
    """
    Create a RabbitMQ connection for the test session.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host=RABBITMQ_VHOST,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    
    # Retry connection
    max_retries = 10
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(parameters)
            print(f"Connected to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            yield connection
            connection.close()
            return
        except pika.exceptions.AMQPConnectionError as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}/{max_retries}: Waiting for RabbitMQ...")
                time.sleep(2)
            else:
                raise Exception(f"Failed to connect to RabbitMQ after {max_retries} attempts") from e


@pytest.fixture(scope='function')
def rabbitmq_channel(rabbitmq_connection):
    """
    Create a RabbitMQ channel for each test.
    Purges test queues before each test to ensure clean state.
    """
    channel = rabbitmq_connection.channel()
    
    # Purge common test queues before each test
    test_queues = [
        'patient.created',
        'patient.updated',
        'patient.deleted',
        'scheduler.patient.created',
        'scheduler.patient.updated',
        'scheduler.patient.deleted',
        'activity.created',
        'scheduler.activity.created'
    ]
    
    for queue in test_queues:
        try:
            channel.queue_purge(queue)
        except Exception:
            # Queue might not exist or be empty, ignore
            pass
    
    yield channel
    channel.close()


def pytest_configure(config):
    """
    Configure pytest with custom markers.
    """
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
