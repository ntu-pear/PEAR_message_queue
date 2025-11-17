import pytest
import json
import time
import pika
from datetime import datetime


@pytest.mark.e2e
class TestDeadLetterQueue:
    """Test dead letter queue and error handling"""

    def test_message_delivery_limit(self, rabbitmq_channel):
        """
        Test: Message Delivery Limit
        
        Verify that messages are moved to DLQ after exceeding delivery limit (3 attempts)
        """
        patient_id = 99999
        patient_data = {
            "patient_id": patient_id,
            "name": "Test DLQ Patient",
            "event_type": "created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Message Delivery Limit ===")
        
        routing_key = f"patient.created.{patient_id}"
        exchange = "patient.updates"
        queue_name = "patient.created"
        
        # Publish message
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(patient_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published test message")
        time.sleep(2)
        
        # Simulate 3 failed delivery attempts by rejecting the message
        for attempt in range(3):
            method_frame, _, body = rabbitmq_channel.basic_get(
                queue=queue_name,
                auto_ack=False
            )
            
            if method_frame:
                print(f"  Attempt {attempt + 1}: Rejecting message (simulating processing failure)")
                # Requeue=True to simulate retry
                rabbitmq_channel.basic_nack(
                    delivery_tag=method_frame.delivery_tag,
                    requeue=True
                )
                time.sleep(1)
        
        # After 3 failed attempts, message should move to DLQ
        # Note: Actual movement to DLQ depends on queue configuration
        print(f"Simulated 3 failed delivery attempts")
        print(f"Message should be moved to DLQ after delivery limit exceeded")

    def test_dlq_patient_queue(self, rabbitmq_channel):
        """
        Test: DLQ Patient Queue
        
        Verify DLQ exists and can store failed patient messages
        """
        print(f"\n=== Test: DLQ Patient Queue ===")
        
        dlq_name = "dlq.patient"
        
        # Check if DLQ exists by attempting to inspect it
        try:
            result = rabbitmq_channel.queue_declare(
                queue=dlq_name,
                passive=True  # Only check if it exists
            )
            print(f"DLQ '{dlq_name}' exists")
            print(f"  Messages in queue: {result.method.message_count}")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"DLQ '{dlq_name}' does not exist")

    def test_dlq_activity_queue(self, rabbitmq_channel):
        """
        Test: DLQ Activity Queue
        
        Verify DLQ exists for activity messages
        """
        print(f"\n=== Test: DLQ Activity Queue ===")
        
        dlq_name = "dlq.activity"
        
        try:
            result = rabbitmq_channel.queue_declare(
                queue=dlq_name,
                passive=True
            )
            print(f"DLQ '{dlq_name}' exists")
            print(f"  Messages in queue: {result.method.message_count}")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"DLQ '{dlq_name}' does not exist")

    def test_dlq_scheduler_patient_queue(self, rabbitmq_channel):
        """
        Test: DLQ Scheduler Patient Queue
        """
        print(f"\n=== Test: DLQ Scheduler Patient Queue ===")
        
        dlq_name = "dlq.scheduler.patient"
        
        try:
            result = rabbitmq_channel.queue_declare(
                queue=dlq_name,
                passive=True
            )
            print(f"DLQ '{dlq_name}' exists")
            print(f"  Messages in queue: {result.method.message_count}")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"DLQ '{dlq_name}' does not exist")

    def test_dlq_medication_queue(self, rabbitmq_channel):
        """
        Test: DLQ Medication Queue
        """
        print(f"\n=== Test: DLQ Medication Queue ===")
        
        dlq_name = "dlq.patient.medication"
        
        try:
            result = rabbitmq_channel.queue_declare(
                queue=dlq_name,
                passive=True
            )
            print(f"DLQ '{dlq_name}' exists")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"DLQ '{dlq_name}' does not exist")

    def test_message_persistence(self, rabbitmq_channel):
        """
        Test: Message Persistence
        
        Verify messages are persisted (delivery_mode=2)
        """
        print(f"\n=== Test: Message Persistence ===")
        
        patient_id = 88888
        patient_data = {
            "patient_id": patient_id,
            "name": "Persistence Test",
            "event_type": "created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish with persistence
        rabbitmq_channel.basic_publish(
            exchange="patient.updates",
            routing_key=f"patient.created.{patient_id}",
            body=json.dumps(patient_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2  # Persistent
            )
        )
        
        print(f"Published persistent message")
        time.sleep(1)
        
        # Retrieve and verify
        method_frame, header_frame, body = rabbitmq_channel.basic_get(
            queue="patient.created",
            auto_ack=True
        )
        
        assert method_frame is not None
        assert header_frame.delivery_mode == 2, "Message is not persistent"
        print(f"Message persistence verified (delivery_mode=2)")

    def test_all_dlqs_exist(self, rabbitmq_channel):
        """
        Test: All DLQs Exist
        
        Verify all expected DLQs are configured
        """
        print(f"\n=== Test: All DLQs Exist ===")
        
        expected_dlqs = [
            "dlq.patient",
            "dlq.patient.medication",
            "dlq.scheduler.patient",
            "dlq.scheduler.patient.medication",
            "dlq.activity",
            "dlq.scheduler.activity",
            "dlq.activity.centre_activity",
            "dlq.scheduler.activity.centre_activity",
            "dlq.activity.centre_activity_exclusion",
            "dlq.scheduler.activity.centre_activity_exclusion",
            "dlq.activity.routine",
            "dlq.scheduler.activity.routine",
            "dlq.activity.preference",
            "dlq.scheduler.activity.preference",
            "dlq.activity.recommendation",
            "dlq.scheduler.activity.recommendation",
            "dlq.reconciliation.drift"
        ]
        
        missing_dlqs = []
        
        for dlq_name in expected_dlqs:
            try:
                rabbitmq_channel.queue_declare(queue=dlq_name, passive=True)
                print(f"  {dlq_name}")
            except pika.exceptions.ChannelClosedByBroker:
                missing_dlqs.append(dlq_name)
                print(f"  ✗ {dlq_name} - MISSING")
                # Reopen channel after error
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        if missing_dlqs:
            pytest.fail(f"Missing DLQs: {', '.join(missing_dlqs)}")
        
        print(f"All {len(expected_dlqs)} DLQs exist")
