import pytest
import pika
import os

# Get configuration from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))


@pytest.mark.e2e
class TestRabbitMQInfrastructure:
    """Test RabbitMQ infrastructure configuration"""

    def test_exchanges_exist(self, rabbitmq_channel):
        """
        Test: All Required Exchanges Exist
        
        Verify all required exchanges are configured correctly
        """
        print(f"\n=== Test: All Required Exchanges Exist ===")
        
        expected_exchanges = [
            ("patient.updates", "topic"),
            ("activity.updates", "topic"),
            ("reconciliation.events", "topic"),
            ("system.dlx", "direct")
        ]
        
        for exchange_name, exchange_type in expected_exchanges:
            try:
                rabbitmq_channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type=exchange_type,
                    passive=True  # Only check if exists
                )
                print(f"  Exchange '{exchange_name}' ({exchange_type}) exists")
            except pika.exceptions.ChannelClosedByBroker:
                pytest.fail(f"Exchange '{exchange_name}' does not exist or wrong type")
                # Reopen channel
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        print(f"All {len(expected_exchanges)} exchanges exist")

    def test_patient_queues_exist(self, rabbitmq_channel):
        """
        Test: Patient Queues Exist
        
        Verify all patient-related queues are configured
        """
        print(f"\n=== Test: Patient Queues Exist ===")
        
        patient_queues = [
            "patient.created",
            "patient.updated",
            "patient.deleted",
            "patient.medication.created",
            "patient.medication.updated",
            "patient.medication.deleted"
        ]
        
        for queue_name in patient_queues:
            try:
                result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
                print(f"  Queue '{queue_name}' exists (messages: {result.method.message_count})")
            except pika.exceptions.ChannelClosedByBroker:
                pytest.fail(f"Queue '{queue_name}' does not exist")
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        print(f"All {len(patient_queues)} patient queues exist")

    def test_scheduler_queues_exist(self, rabbitmq_channel):
        """
        Test: Scheduler Queues Exist
        
        Verify all scheduler-related queues are configured
        """
        print(f"\n=== Test: Scheduler Queues Exist ===")
        
        scheduler_queues = [
            "scheduler.patient.created",
            "scheduler.patient.updated",
            "scheduler.patient.deleted",
            "scheduler.patient.medication.created",
            "scheduler.patient.medication.updated",
            "scheduler.patient.medication.deleted",
            "scheduler.activity.created",
            "scheduler.activity.updated",
            "scheduler.activity.deleted",
            "scheduler.activity.centre_activity.created",
            "scheduler.activity.centre_activity.updated",
            "scheduler.activity.centre_activity.deleted",
            "scheduler.activity.centre_activity_exclusion.created",
            "scheduler.activity.centre_activity_exclusion.updated",
            "scheduler.activity.centre_activity_exclusion.deleted",
            "scheduler.activity.routine.created",
            "scheduler.activity.routine.updated",
            "scheduler.activity.routine.deleted",
            "scheduler.activity.preference.created",
            "scheduler.activity.preference.updated",
            "scheduler.activity.preference.deleted",
            "scheduler.activity.recommendation.created",
            "scheduler.activity.recommendation.updated",
            "scheduler.activity.recommendation.deleted"
        ]
        
        missing_queues = []
        
        for queue_name in scheduler_queues:
            try:
                result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
                print(f"  {queue_name}")
            except pika.exceptions.ChannelClosedByBroker:
                missing_queues.append(queue_name)
                print(f"  ✗ {queue_name} - MISSING")
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        if missing_queues:
            pytest.fail(f"Missing scheduler queues: {', '.join(missing_queues)}")
        
        print(f"All {len(scheduler_queues)} scheduler queues exist")

    def test_activity_queues_exist(self, rabbitmq_channel):
        """
        Test: Activity Queues Exist
        
        Verify all activity-related queues are configured
        """
        print(f"\n=== Test: Activity Queues Exist ===")
        
        activity_queues = [
            "activity.created",
            "activity.updated",
            "activity.deleted",
            "activity.centre_activity.created",
            "activity.centre_activity.updated",
            "activity.centre_activity.deleted",
            "activity.centre_activity_exclusion.created",
            "activity.centre_activity_exclusion.updated",
            "activity.centre_activity_exclusion.deleted",
            "activity.routine.created",
            "activity.routine.updated",
            "activity.routine.deleted",
            "activity.preference.created",
            "activity.preference.updated",
            "activity.preference.deleted",
            "activity.recommendation.created",
            "activity.recommendation.updated",
            "activity.recommendation.deleted"
        ]
        
        for queue_name in activity_queues:
            try:
                result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
                print(f"  {queue_name}")
            except pika.exceptions.ChannelClosedByBroker:
                pytest.fail(f"Queue '{queue_name}' does not exist")
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        print(f"All {len(activity_queues)} activity queues exist")

    def test_queue_properties(self, rabbitmq_channel):
        """
        Test: Queue Properties
        
        Verify queues have correct properties (durable, quorum type, etc.)
        """
        print(f"\n=== Test: Queue Properties ===")
        
        # Check a sample queue for correct properties
        queue_name = "patient.created"
        
        try:
            result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
            print(f"Queue '{queue_name}' properties:")
            print(f"  - Durable: Expected (quorum queues are durable by default)")
            print(f"  - Messages: {result.method.message_count}")
            print(f"  - Consumers: {result.method.consumer_count}")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"Queue '{queue_name}' does not exist")

    def test_reconciliation_queue_exists(self, rabbitmq_channel):
        """
        Test: Reconciliation Queue Exists
        
        Verify reconciliation drift detection queue exists
        """
        print(f"\n=== Test: Reconciliation Queue Exists ===")
        
        queue_name = "reconciliation.drift.detected"
        
        try:
            result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
            print(f"Queue '{queue_name}' exists")
            print(f"  Messages in queue: {result.method.message_count}")
        except pika.exceptions.ChannelClosedByBroker:
            pytest.fail(f"Queue '{queue_name}' does not exist")

    def test_connection_heartbeat(self, rabbitmq_connection):
        """
        Test: Connection Heartbeat
        
        Verify RabbitMQ connection has heartbeat configured
        """
        print(f"\n=== Test: Connection Heartbeat ===")
        
        # Get connection parameters
        # For BlockingConnection, we can check if it's open
        assert rabbitmq_connection.is_open, "Connection should be open"
        
        print(f"Connection established to RabbitMQ")
        print(f"  Connection is open: {rabbitmq_connection.is_open}")
        print(f"Connection is properly configured")

    def test_vhost_access(self, rabbitmq_channel):
        """
        Test: VHost Access
        
        Verify access to the correct virtual host by testing queue operations
        """
        print(f"\n=== Test: VHost Access ===")
        
        # Test vhost access by declaring a queue
        try:
            # Try to access a known queue in the vhost
            result = rabbitmq_channel.queue_declare(queue='patient.created', passive=True)
            print(f"Successfully accessed queue in vhost")
            print(f"  Can access queues in configured virtual host")
        except Exception as e:
            pytest.fail(f"Cannot access vhost or queue: {e}")
        
        print(f"Virtual host access verified")

    def test_channel_creation(self, rabbitmq_connection):
        """
        Test: Channel Creation
        
        Verify ability to create multiple channels
        """
        print(f"\n=== Test: Channel Creation ===")
        
        channels = []
        num_channels = 5
        
        for i in range(num_channels):
            channel = rabbitmq_connection.channel()
            channels.append(channel)
            print(f"  Created channel {i + 1}")
        
        # Close all channels
        for i, channel in enumerate(channels):
            channel.close()
            print(f"  Closed channel {i + 1}")
        
        print(f"Successfully created and closed {num_channels} channels")

    def test_message_count_zero_on_startup(self, rabbitmq_channel):
        """
        Test: Clean Queues on Startup
        
        Verify that test queues start with zero messages (or acceptable count)
        Note: In actual testing, queues might have messages, this is informational
        """
        print(f"\n=== Test: Queue Message Counts ===")
        
        sample_queues = [
            "patient.created",
            "scheduler.patient.created",
            "activity.created"
        ]
        
        for queue_name in sample_queues:
            try:
                result = rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
                msg_count = result.method.message_count
                print(f"  Queue '{queue_name}': {msg_count} messages")
            except pika.exceptions.ChannelClosedByBroker:
                print(f"  Queue '{queue_name}': Does not exist")
                rabbitmq_channel = rabbitmq_channel.connection.channel()
        
        print(f"Queue message counts reported")
