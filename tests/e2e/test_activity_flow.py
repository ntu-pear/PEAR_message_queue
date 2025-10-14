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
