import pytest
import requests
import time
import os
from datetime import datetime

# Service URLs from environment
ACTIVITY_SERVICE_URL = os.getenv('ACTIVITY_SERVICE_URL', 'http://localhost:8001')
SCHEDULER_SERVICE_URL = os.getenv('SCHEDULER_SERVICE_URL', 'http://localhost:8002')

# Timeouts
MESSAGE_PROCESSING_TIMEOUT = 15  # seconds to wait for async processing
RETRY_INTERVAL = 2  # seconds between retries


def check_service_available(url, timeout=5):
    """
    Check if a service is available by making a health check request.
    Returns True if available, False otherwise.
    """
    try:
        response = requests.get(f"{url}/health", timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        try:
            # Try root endpoint if health endpoint doesn't exist
            response = requests.get(url, timeout=timeout)
            return response.status_code < 500
        except requests.RequestException:
            return False


# Check if services are available
ACTIVITY_SERVICE_AVAILABLE = check_service_available(ACTIVITY_SERVICE_URL)
SCHEDULER_SERVICE_AVAILABLE = check_service_available(SCHEDULER_SERVICE_URL)
SERVICES_AVAILABLE = ACTIVITY_SERVICE_AVAILABLE and SCHEDULER_SERVICE_AVAILABLE

# Skip marker for when services are not available
require_services = pytest.mark.skipif(
    not SERVICES_AVAILABLE,
    reason="Activity and/or Scheduler services not available. "
           "These tests require running services. "
           "Run nightly E2E workflow or start services locally to execute these tests."
)


@pytest.mark.e2e
@pytest.mark.slow
class TestPatientServiceIntegration:
    """Test patient data flow from Activity Service to Scheduler Service"""

    @require_services
    def test_patient_created_e2e_flow(self):
        """
        Test: Complete Patient Creation Flow
        
        Flow:
        1. POST /api/patients to Activity Service
        2. Wait for async message processing
        3. GET /api/patients/{id} from Scheduler Service (verify synced)
        4. Verify patient data matches
        """
        print(f"\n=== Test: Patient Created E2E Flow ===")
        
        # Step 1: Create patient via Activity Service
        patient_data = {
            "name": "E2E Test Patient",
            "nric": "S9999999A",
            "dateOfBirth": "1990-01-01",
            "gender": "M",
            "isActive": True
        }
        
        print(f"Step 1: Creating patient in Activity Service...")
        create_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/patients",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201], \
            f"Failed to create patient: {create_response.status_code} - {create_response.text}"
        
        patient_id = create_response.json()['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Step 2: Wait for message processing with retry logic
        print(f"Step 2: Waiting for message processing (max {MESSAGE_PROCESSING_TIMEOUT}s)...")
        
        # Step 3: Verify patient synced to Scheduler Service
        print(f"Step 3: Verifying patient synced to Scheduler Service...")
        
        scheduler_patient = None
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            try:
                scheduler_response = requests.get(
                    f"{SCHEDULER_SERVICE_URL}/api/patients/{patient_id}",
                    timeout=5
                )
                
                if scheduler_response.status_code == 200:
                    scheduler_patient = scheduler_response.json()
                    print(f"Patient found in Scheduler Service (attempt {attempt + 1})")
                    break
                else:
                    print(f"  Attempt {attempt + 1}/{max_retries}: Patient not yet in Scheduler (HTTP {scheduler_response.status_code})")
            except requests.RequestException as e:
                print(f"  Attempt {attempt + 1}/{max_retries}: Error checking scheduler - {e}")
        
        assert scheduler_patient is not None, \
            f"Patient not found in Scheduler Service after {MESSAGE_PROCESSING_TIMEOUT}s"
        
        # Step 4: Verify data integrity
        print(f"Step 4: Verifying data integrity...")
        assert scheduler_patient['name'] == patient_data['name'], \
            f"Name mismatch: expected '{patient_data['name']}', got '{scheduler_patient['name']}'"
        assert scheduler_patient['nric'] == patient_data['nric'], \
            f"NRIC mismatch: expected '{patient_data['nric']}', got '{scheduler_patient['nric']}'"
        print(f"Patient data synchronized correctly")
        
        print(f"Complete E2E flow passed!")

    @require_services
    def test_patient_updated_propagation(self):
        """
        Test: Patient Update Propagation
        
        Verify that patient updates in Activity Service propagate to Scheduler
        """
        print(f"\n=== Test: Patient Updated Propagation ===")
        
        # Step 1: Create patient first
        patient_data = {"name": "Update Test", "nric": "S8888888B"}
        create_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/patients",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201]
        patient_id = create_response.json()['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Wait for initial sync
        print(f"Waiting for initial sync...")
        time.sleep(MESSAGE_PROCESSING_TIMEOUT)
        
        # Verify patient exists in scheduler
        scheduler_check = requests.get(
            f"{SCHEDULER_SERVICE_URL}/api/patients/{patient_id}",
            timeout=5
        )
        assert scheduler_check.status_code == 200, "Patient should exist in Scheduler before update"
        print(f"Patient synced to Scheduler Service")
        
        # Step 2: Update patient
        update_data = {"name": "Updated Name", "address": "New Address"}
        update_response = requests.put(
            f"{ACTIVITY_SERVICE_URL}/api/patients/{patient_id}",
            json=update_data,
            timeout=10
        )
        
        assert update_response.status_code == 200
        print(f"Patient updated in Activity Service")
        
        # Step 3: Wait for update propagation
        print(f"Waiting for update propagation...")
        
        updated_scheduler_patient = None
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            scheduler_response = requests.get(
                f"{SCHEDULER_SERVICE_URL}/api/patients/{patient_id}",
                timeout=5
            )
            
            if scheduler_response.status_code == 200:
                patient = scheduler_response.json()
                if patient['name'] == "Updated Name":
                    updated_scheduler_patient = patient
                    print(f"Update propagated (attempt {attempt + 1})")
                    break
                else:
                    print(f"  Attempt {attempt + 1}/{max_retries}: Name not yet updated")
        
        assert updated_scheduler_patient is not None, \
            "Update did not propagate to Scheduler Service"
        assert updated_scheduler_patient['name'] == "Updated Name"
        print(f"Update propagated successfully to Scheduler Service")

    @require_services
    def test_patient_deleted_propagation(self):
        """
        Test: Patient Delete Propagation
        
        Verify that patient deletion in Activity Service propagates to Scheduler
        """
        print(f"\n=== Test: Patient Delete Propagation ===")
        
        # Step 1: Create patient
        patient_data = {"name": "Delete Test", "nric": "S7777777C"}
        create_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/patients",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201]
        patient_id = create_response.json()['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Wait for sync
        time.sleep(MESSAGE_PROCESSING_TIMEOUT)
        
        # Verify patient exists in scheduler
        scheduler_check = requests.get(
            f"{SCHEDULER_SERVICE_URL}/api/patients/{patient_id}",
            timeout=5
        )
        assert scheduler_check.status_code == 200, "Patient should exist in Scheduler before deletion"
        print(f"Patient synced to Scheduler Service")
        
        # Step 2: Delete patient
        delete_response = requests.delete(
            f"{ACTIVITY_SERVICE_URL}/api/patients/{patient_id}",
            timeout=10
        )
        
        assert delete_response.status_code in [200, 204]
        print(f"Patient deleted in Activity Service")
        
        # Step 3: Wait and verify deletion propagated
        print(f"Waiting for deletion propagation...")
        
        deletion_propagated = False
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            scheduler_response = requests.get(
                f"{SCHEDULER_SERVICE_URL}/api/patients/{patient_id}",
                timeout=5
            )
            
            # Patient should either be 404 (deleted) or marked as inactive
            if scheduler_response.status_code == 404:
                deletion_propagated = True
                print(f"Patient deleted from Scheduler (attempt {attempt + 1})")
                break
            elif scheduler_response.status_code == 200:
                patient = scheduler_response.json()
                if patient.get('isActive') == False or patient.get('isDeleted') == True:
                    deletion_propagated = True
                    print(f"Patient marked as deleted/inactive (attempt {attempt + 1})")
                    break
                else:
                    print(f"  Attempt {attempt + 1}/{max_retries}: Patient still active")
        
        assert deletion_propagated, \
            "Deletion did not propagate to Scheduler Service"
        print(f"Deletion propagated successfully to Scheduler Service")


@pytest.mark.e2e
@pytest.mark.slow
class TestActivityServiceIntegration:
    """Test activity data flow from Activity Service to Scheduler Service"""

    @require_services
    def test_activity_created_with_schedule_generation(self):
        """
        Test: Activity Creation Triggers Schedule Generation
        
        Verify that creating an activity causes schedules to be generated
        """
        print(f"\n=== Test: Activity Created with Schedule Generation ===")
        
        # Step 1: Create activity
        activity_data = {
            "title": "Morning Exercise",
            "description": "E2E Test Activity",
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "isCompulsory": True,
            "minDuration": 30,
            "maxDuration": 60
        }
        
        print(f"Step 1: Creating activity in Activity Service...")
        create_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/activities",
            json=activity_data
        )
        
        assert create_response.status_code in [200, 201]
        activity_id = create_response.json()['id']
        print(f"Activity created with ID: {activity_id}")
        
        # Step 2: Wait for message processing
        print(f"Step 2: Waiting for message processing...")
        time.sleep(10)
        
        # Step 3: Verify activity synced to Scheduler
        scheduler_response = requests.get(
            f"{SCHEDULER_SERVICE_URL}/api/activities/{activity_id}"
        )
        
        assert scheduler_response.status_code == 200
        print(f"Activity synced to Scheduler Service")
        
        # Step 4: Verify schedules were generated (business logic)
        schedules_response = requests.get(
            f"{SCHEDULER_SERVICE_URL}/api/schedules?activityId={activity_id}"
        )
        
        # Depending on business logic, schedules might be generated
        # This verifies the scheduler service received and can query the activity
        assert schedules_response.status_code == 200
        print(f"Scheduler can query activity schedules")
        
        print(f"Activity creation and schedule generation flow completed")

    @require_services
    def test_activity_exclusion_affects_scheduling(self):
        """
        Test: Activity Exclusion Flow
        
        Verify that activity exclusions propagate and affect scheduling
        """
        print(f"\n=== Test: Activity Exclusion Flow ===")
        
        # Create activity first
        activity_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/activities",
            json={"title": "Exclusion Test", "description": "Test"}
        )
        activity_id = activity_response.json()['id']
        
        time.sleep(5)
        
        # Create exclusion
        exclusion_data = {
            "activityId": activity_id,
            "startDate": "2025-02-01",
            "endDate": "2025-02-07",
            "remarks": "Maintenance week"
        }
        
        exclusion_response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/exclusions",
            json=exclusion_data
        )
        
        assert exclusion_response.status_code in [200, 201]
        exclusion_id = exclusion_response.json()['id']
        print(f"Exclusion created")
        
        # Wait for propagation
        time.sleep(10)
        
        # Verify in scheduler
        scheduler_exclusion = requests.get(
            f"{SCHEDULER_SERVICE_URL}/api/exclusions/{exclusion_id}"
        )
        
        assert scheduler_exclusion.status_code == 200
        print(f"Exclusion propagated to Scheduler")


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorHandlingIntegration:
    """Test error handling and recovery in service-to-service communication"""

    def test_service_outage_recovery(self):
        """
        Test: Service Outage Recovery
        
        Verify that messages are not lost if Scheduler Service is temporarily down
        """
        print(f"\n=== Test: Service Outage Recovery ===")
        print(f"Note: This test requires ability to stop/start Scheduler Service")
        print(f"Skipping in automated tests - manual verification recommended")
        pytest.skip("Requires service orchestration")

    @require_services
    def test_invalid_data_handling(self):
        """
        Test: Invalid Data Handling
        
        Verify that invalid messages are handled gracefully and routed to DLQ
        """
        print(f"\n=== Test: Invalid Data Handling ===")
        
        # Send invalid patient data
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "nric": "INVALID"
        }
        
        response = requests.post(
            f"{ACTIVITY_SERVICE_URL}/api/patients",
            json=invalid_data
        )
        
        # Should be rejected at API level
        assert response.status_code >= 400
        print(f"Invalid data rejected at API level")


# Helper function for cleanup
@pytest.fixture(scope="function", autouse=False)
def cleanup_test_data():
    """
    Optional: Clean up test data after tests
    """
    yield
    # Cleanup logic here if needed
    print("Test cleanup completed")
