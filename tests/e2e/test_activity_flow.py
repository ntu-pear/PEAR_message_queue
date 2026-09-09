import pytest
import json
import time
import pika
import os
from datetime import datetime, timedelta

# Get configuration from environment variables
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))


@pytest.mark.e2e
class TestActivityMessageFlow:
    """Test activity message flow through the system"""

    def test_activity_created_flow(self, rabbitmq_channel):
        """
        Test: Activity Created Message Flow
        
        Steps:
        1. Publish activity.created message
        2. Verify routing to activity.created queue
        3. Verify routing to scheduler.activity.created queue
        """
        activity_id = 201
        activity_data = {
            "activity_id": activity_id,
            "title": "Morning Exercise",
            "description": "Light stretching and walking",
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "event_type": "created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Created Message Flow ===")
        print(f"Activity ID: {activity_id}")
        print(f"Activity Title: {activity_data['title']}")
        
        routing_key = f"activity.created.{activity_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(activity_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity created message")
        time.sleep(2)
        
        # Verify in activity queue
        queue_name = "activity.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=queue_name,
            auto_ack=False
        )
        
        assert method_frame is not None, f"No message in {queue_name}"
        received = json.loads(body.decode())
        assert received['activity_id'] == activity_id
        rabbitmq_channel.basic_ack(method_frame.delivery_tag)
        print(f"Message received from queue '{queue_name}'")
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['activity_id'] == activity_id
        print(f"Message received from scheduler queue")
        print(f"Activity created message flow completed successfully")

    def test_centre_activity_created_flow(self, rabbitmq_channel):
        """
        Test: Centre Activity Created Message Flow
        
        Centre activities are specific implementations of activities
        with additional constraints (duration, group size, etc.)
        """
        centre_activity_id = 301
        activity_id = 202
        centre_activity_data = {
            "centre_activity_id": centre_activity_id,
            "activity_id": activity_id,
            "is_compulsory": True,
            "is_fixed": False,
            "is_group": True,
            "min_duration": 30,
            "max_duration": 60,
            "min_people_req": 2,
            "event_type": "centre_activity_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Centre Activity Created Message Flow ===")
        print(f"Centre Activity ID: {centre_activity_id}")
        
        routing_key = f"activity.centre_activity.created.{centre_activity_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(centre_activity_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published centre activity created message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.centre_activity.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['centre_activity_id'] == centre_activity_id
        assert received['is_compulsory'] == True
        assert received['is_group'] == True
        
        print(f"Centre activity created message flow completed successfully")

    def test_activity_exclusion_created_flow(self, rabbitmq_channel):
        """
        Test: Activity Exclusion Created Message Flow
        
        Activity exclusions define periods when an activity is not available
        """
        exclusion_id = 401
        activity_id = 203
        exclusion_data = {
            "exclusion_id": exclusion_id,
            "activity_id": activity_id,
            "exclusion_remarks": "Activity room under maintenance",
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "event_type": "exclusion_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Exclusion Created Message Flow ===")
        print(f"Exclusion ID: {exclusion_id}")
        
        routing_key = f"activity.centre_activity_exclusion.created.{exclusion_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(exclusion_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity exclusion created message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.centre_activity_exclusion.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['exclusion_id'] == exclusion_id
        assert received['activity_id'] == activity_id
        
        print(f"Activity exclusion message flow completed successfully")

    def test_activity_preference_created_flow(self, rabbitmq_channel):
        """
        Test: Activity Preference Created Message Flow
        
        Patient preferences for activities (like/dislike)
        """
        preference_id = 501
        patient_id = 12349
        centre_activity_id = 302
        
        preference_data = {
            "preference_id": preference_id,
            "centre_activity_id": centre_activity_id,
            "patient_id": patient_id,
            "is_like": True,
            "event_type": "preference_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Preference Created Message Flow ===")
        print(f"Patient ID: {patient_id}, Preference: {'Like' if preference_data['is_like'] else 'Dislike'}")
        
        routing_key = f"activity.preference.created.{preference_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(preference_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity preference message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.preference.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['preference_id'] == preference_id
        assert received['patient_id'] == patient_id
        
        print(f"Activity preference message flow completed successfully")

    def test_activity_recommendation_created_flow(self, rabbitmq_channel):
        """
        Test: Activity Recommendation Created Message Flow
        
        Doctor recommendations for patient activities
        """
        recommendation_id = 601
        patient_id = 12350
        centre_activity_id = 303
        doctor_id = "DOC001"
        
        recommendation_data = {
            "recommendation_id": recommendation_id,
            "centre_activity_id": centre_activity_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "is_doctor_recommended": True,
            "doctor_remarks": "Recommended for cognitive improvement",
            "event_type": "recommendation_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Recommendation Created Message Flow ===")
        print(f"Patient ID: {patient_id}, Doctor ID: {doctor_id}")
        
        routing_key = f"activity.recommendation.created.{recommendation_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(recommendation_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity recommendation message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.recommendation.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['recommendation_id'] == recommendation_id
        assert received['doctor_id'] == doctor_id
        
        print(f"Activity recommendation message flow completed successfully")

    def test_activity_updated_flow(self, rabbitmq_channel):
        """
        Test: Activity Updated Message Flow
        """
        activity_id = 204
        activity_data = {
            "activity_id": activity_id,
            "title": "Evening Exercise - Updated",
            "updated_fields": ["title", "description"],
            "event_type": "updated",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Updated Message Flow ===")
        
        routing_key = f"activity.updated.{activity_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(activity_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity updated message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.updated"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['activity_id'] == activity_id
        assert 'updated_fields' in received
        
        print(f"Activity updated message flow completed successfully")

    def test_activity_routine_created_flow(self, rabbitmq_channel):
        """
        Test: Activity Routine Created Message Flow
        
        Routines are scheduled recurring activities
        """
        routine_id = 701
        activity_id = 205
        patient_id = 12351
        
        routine_data = {
            "routine_id": routine_id,
            "activity_id": activity_id,
            "patient_id": patient_id,
            "recurrence_pattern": "daily",
            "preferred_time": "09:00",
            "event_type": "routine_created",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"\n=== Test: Activity Routine Created Message Flow ===")
        
        routing_key = f"activity.routine.created.{routine_id}"
        exchange = "activity.updates"
        
        rabbitmq_channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(routine_data),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )
        
        print(f"Published activity routine message")
        time.sleep(2)
        
        # Verify in scheduler queue
        scheduler_queue = "scheduler.activity.routine.created"
        method_frame, _, body = rabbitmq_channel.basic_get(
            queue=scheduler_queue,
            auto_ack=True
        )
        
        assert method_frame is not None
        received = json.loads(body.decode())
        assert received['routine_id'] == routine_id
        assert received['recurrence_pattern'] == "daily"

        print(f"Activity routine message flow completed successfully")


@pytest.mark.e2e
class TestAdhocMessageFlow:
    """
    Test adhoc message flow through the system.

    Adhoc events travel one way: the activity service outbox publishes onto
    activity.updates, and the scheduler queues are the only consumers.
    """

    ADHOC_QUEUES = [
        "scheduler.activity.adhoc.created",
        "scheduler.activity.adhoc.updated",
        "scheduler.activity.adhoc.deleted",
    ]

    def _purge_adhoc_queues(self, channel):
        """Adhoc queues are not in the conftest purge list, so clear them here."""
        for queue in self.ADHOC_QUEUES:
            try:
                channel.queue_purge(queue)
            except Exception:
                pass

    def _envelope(self, payload):
        """
        Match the wrapper RabbitMQClient.publish puts around every message.
        The scheduler consumer reads message["data"], so the shape matters.
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "source_service": "activity-service",
            "data": payload,
        }

    def _publish(self, channel, routing_key, payload):
        channel.basic_publish(
            exchange="activity.updates",
            routing_key=routing_key,
            body=json.dumps(self._envelope(payload)),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2
            )
        )

    def _get_message(self, channel, queue):
        method_frame, _, body = channel.basic_get(queue=queue, auto_ack=True)
        assert method_frame is not None, f"No message arrived on {queue}"
        return json.loads(body.decode())

    def test_adhoc_created_flow(self, rabbitmq_channel):
        """
        Test: Adhoc Created Message Flow

        Steps:
        1. Publish activity.adhoc.created message
        2. Verify routing to scheduler.activity.adhoc.created queue
        """
        self._purge_adhoc_queues(rabbitmq_channel)

        adhoc_id = 801
        payload = {
            "event_type": "ADHOC_CREATED",
            "adhoc_id": adhoc_id,
            "adhoc_data": {
                "id": adhoc_id,
                "patient_id": 12361,
                "old_centre_activity_id": 2,
                "new_centre_activity_id": 3,
                "status": "PENDING",
                "start_date": datetime.utcnow().isoformat(),
                "end_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "is_deleted": False,
            },
            "created_by": "test-user",
            "correlation_id": f"E2E-ADHOC-CREATED-{adhoc_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(f"\n=== Test: Adhoc Created Message Flow ===")
        print(f"Adhoc ID: {adhoc_id}")

        self._publish(rabbitmq_channel, f"activity.adhoc.created.{adhoc_id}", payload)
        print(f"Published adhoc created message")
        time.sleep(2)

        received = self._get_message(rabbitmq_channel, "scheduler.activity.adhoc.created")
        data = received["data"]
        assert data["adhoc_id"] == adhoc_id
        assert data["event_type"] == "ADHOC_CREATED"
        # Fields the scheduler's adhoc mapper treats as required
        assert data["adhoc_data"]["id"] == adhoc_id
        assert data["adhoc_data"]["patient_id"] == 12361
        assert data["adhoc_data"]["old_centre_activity_id"] == 2
        assert data["adhoc_data"]["new_centre_activity_id"] == 3

        print(f"Adhoc created message flow completed successfully")

    def test_adhoc_updated_flow(self, rabbitmq_channel):
        """
        Test: Adhoc Updated Message Flow

        The scheduler applies the new state from adhoc_data.
        """
        self._purge_adhoc_queues(rabbitmq_channel)

        adhoc_id = 802
        payload = {
            "event_type": "ADHOC_UPDATED",
            "adhoc_id": adhoc_id,
            "adhoc_data": {
                "id": adhoc_id,
                "patient_id": 12362,
                "old_centre_activity_id": 2,
                "new_centre_activity_id": 3,
                "status": "APPROVED",
                "is_deleted": False,
            },
            "old_data": {"status": "PENDING"},
            "changes": {"status": {"old": "PENDING", "new": "APPROVED"}},
            "modified_by": "test-user",
            "correlation_id": f"E2E-ADHOC-UPDATED-{adhoc_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(f"\n=== Test: Adhoc Updated Message Flow ===")

        self._publish(rabbitmq_channel, f"activity.adhoc.updated.{adhoc_id}", payload)
        print(f"Published adhoc updated message")
        time.sleep(2)

        received = self._get_message(rabbitmq_channel, "scheduler.activity.adhoc.updated")
        data = received["data"]
        assert data["adhoc_id"] == adhoc_id
        assert data["adhoc_data"]["status"] == "APPROVED"
        assert data["changes"]["status"]["new"] == "APPROVED"

        print(f"Adhoc updated message flow completed successfully")

    def test_adhoc_deleted_flow(self, rabbitmq_channel):
        """
        Test: Adhoc Deleted Message Flow

        The scheduler's delete handler reads the timestamp without a fallback,
        so it must survive the round trip.
        """
        self._purge_adhoc_queues(rabbitmq_channel)

        adhoc_id = 803
        payload = {
            "event_type": "ADHOC_DELETED",
            "adhoc_id": adhoc_id,
            "adhoc_data": {
                "id": adhoc_id,
                "patient_id": 12363,
                "old_centre_activity_id": 2,
                "new_centre_activity_id": 3,
                "status": "APPROVED",
                "is_deleted": True,
            },
            "deleted_by": "test-user",
            "correlation_id": f"E2E-ADHOC-DELETED-{adhoc_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(f"\n=== Test: Adhoc Deleted Message Flow ===")

        self._publish(rabbitmq_channel, f"activity.adhoc.deleted.{adhoc_id}", payload)
        print(f"Published adhoc deleted message")
        time.sleep(2)

        received = self._get_message(rabbitmq_channel, "scheduler.activity.adhoc.deleted")
        data = received["data"]
        assert data["adhoc_id"] == adhoc_id
        assert data["adhoc_data"]["is_deleted"] is True
        assert data["timestamp"]

        print(f"Adhoc deleted message flow completed successfully")

    def test_adhoc_routing_keys_do_not_cross_queues(self, rabbitmq_channel):
        """
        Test: Adhoc Binding Isolation

        A created event must not land in the updated or deleted queues.
        Guards against copy-paste errors in the three adhoc bindings.
        """
        self._purge_adhoc_queues(rabbitmq_channel)

        adhoc_id = 804
        payload = {
            "event_type": "ADHOC_CREATED",
            "adhoc_id": adhoc_id,
            "adhoc_data": {
                "id": adhoc_id,
                "patient_id": 12364,
                "old_centre_activity_id": 2,
                "new_centre_activity_id": 3,
            },
            "correlation_id": f"E2E-ADHOC-ISOLATION-{adhoc_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(f"\n=== Test: Adhoc Binding Isolation ===")

        self._publish(rabbitmq_channel, f"activity.adhoc.created.{adhoc_id}", payload)
        time.sleep(2)

        wrong_queues = [
            "scheduler.activity.adhoc.updated",
            "scheduler.activity.adhoc.deleted",
        ]
        for queue in wrong_queues:
            method_frame, _, _ = rabbitmq_channel.basic_get(queue=queue, auto_ack=True)
            assert method_frame is None, f"Created event leaked into {queue}"
            print(f"  No leak into {queue}")

        # And it did reach the queue it belongs to
        received = self._get_message(rabbitmq_channel, "scheduler.activity.adhoc.created")
        assert received["data"]["adhoc_id"] == adhoc_id

        print(f"Adhoc binding isolation verified")
