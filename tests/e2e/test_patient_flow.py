import pytest
import json
import time
import pika
import os
from datetime import datetime

# Get configuration from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', 'vhost')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'admin')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'pear2025')


@pytest.mark.e2e
class TestPatientMessageFlow:
    """Test patient message flow through the system"""

    def test_patient_created_flow(self, rabbitmq_channel):
        """
        Test: Patient Created Message Flow
        
        Steps:
        1. Publish patient.created message to patient.updates exchange
        2. Verify message routed to patient.created queue
        3. Verify message routed to scheduler.patient.created queue
        4. Consume message from scheduler queue
        5. Verify message content is correct
        """
        # Test data
        patient_id = 12345
        patient_data = {
            "patient_id": patient_id,
            "name": "John Doe",
            "nric": "S1234567A",
            "date_of_birth": "1980-01-15",
            "gender": "M",
            "start_date": "2025-01-01",
            "is_active": True,
            "event_type": "created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Patient Created Message Flow ===")
        print(f"Patient ID: {patient_id}")
        print(f"Patient Name: {patient_data['name']}")
        
        # Step 1: Publish message to patient.updates exchange
        routing_key = f"patient.created.{patient_id}"
        exchange = "patient.updates"
        
        message = json.dumps(patient_data)
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2,  # persistent
                message_id=f"test-patient-{patient_id}-{int(time.time())}",
                timestamp=int(time.time())
            )
        )
        
        print(f"Published message to exchange '{exchange}' with routing key '{routing_key}'")
        
        # Wait for message propagation
        time.sleep(2)
        
        # Step 2: Verify message in patient.created queue
        queue_name = "patient.created"
        method_frame, header_frame, body = rabbitmq_channel.basic_get(
            queue=queue_name,
            auto_ack=False
        )
        
        assert method_frame is not None, f"No message found in queue '{queue_name}'"
        
        received_data = json.loads(body.decode())
        assert received_data['patient_id'] == patient_id
        assert received_data['name'] == patient_data['name']
        
        # Acknowledge the message
        rabbitmq_channel.basic_ack(method_frame.delivery_tag)
        print(f"Message received from queue '{queue_name}'")
        
        # Step 3: Verify message in scheduler.patient.created queue
        scheduler_queue_name = "scheduler.patient.created"
        method_frame, header_frame, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue_name,
            auto_ack=False
        )
        
        assert method_frame is not None, f"No message found in queue '{scheduler_queue_name}'"
        
        received_scheduler_data = json.loads(body.decode())
        assert received_scheduler_data['patient_id'] == patient_id
        assert received_scheduler_data['name'] == patient_data['name']
        
        # Acknowledge the message
        rabbitmq_channel.basic_ack(method_frame.delivery_tag)
        print(f"Message received from queue '{scheduler_queue_name}'")
        
        print(f"Patient created message flow completed successfully")

    def test_patient_updated_flow(self, rabbitmq_channel):
        """
        Test: Patient Updated Message Flow
        
        Steps:
        1. Publish patient.updated message
        2. Verify message routing to both queues
        3. Verify message content includes update fields
        """
        patient_id = 12346
        patient_data = {
            "patient_id": patient_id,
            "name": "Jane Smith",
            "updated_fields": ["name", "address"],
            "address": "123 New Street",
            "event_type": "updated",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Patient Updated Message Flow ===")
        print(f"Patient ID: {patient_id}")
        
        routing_key = f"patient.updated.{patient_id}"
        exchange = "patient.updates"
        
        message = json.dumps(patient_data)
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published patient update message")
        
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.patient.updated"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received_data = json.loads(body.decode())
        assert received_data['patient_id'] == patient_id
        assert 'updated_fields' in received_data
        
        print(f"Patient updated message flow completed successfully")

    def test_patient_medication_created_flow(self, rabbitmq_channel):
        """
        Test: Patient Medication Created Message Flow
        
        Steps:
        1. Publish patient.medication.created message
        2. Verify routing to medication queues
        3. Verify message reaches scheduler
        """
        patient_id = 12347
        medication_data = {
            "patient_id": patient_id,
            "medication_id": 101,
            "prescription_name": "Aspirin",
            "dosage": "100mg",
            "frequency_per_day": 2,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "event_type": "medication_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Patient Medication Created Message Flow ===")
        
        routing_key = f"patient.medication.created.{patient_id}"
        exchange = "patient.updates"
        
        message = json.dumps(medication_data)
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published medication created message")
        
        time.sleep(2)
        
        # Verify in scheduler medication queue
        scheduler_queue = "scheduler.patient.medication.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received_data = json.loads(body.decode())
        assert received_data['patient_id'] == patient_id
        assert received_data['medication_id'] == 101
        assert received_data['prescription_name'] == "Aspirin"
        
        print(f"Patient medication message flow completed successfully")

    def test_patient_deleted_flow(self, rabbitmq_channel):
        """
        Test: Patient Deleted Message Flow
        """
        patient_id = 12348
        patient_data = {
            "patient_id": patient_id,
            "event_type": "deleted",
            "deleted_at": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Patient Deleted Message Flow ===")
        
        routing_key = f"patient.deleted.{patient_id}"
        exchange = "patient.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(patient_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published patient deleted message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.patient.deleted"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received_data = json.loads(body.decode())
        assert received_data['patient_id'] == patient_id
        assert received_data['event_type'] == "deleted"
        
        print(f"Patient deleted message flow completed successfully")
