import pytest
import requests
import time
import os
import pyodbc
from datetime import datetime
from typing import Optional

# Service URLs from environment
PATIENT_SERVICE_URL = os.getenv('PATIENT_SERVICE_URL', 'http://localhost:8003')
SCHEDULER_SERVICE_URL = os.getenv('SCHEDULER_SERVICE_URL', 'http://localhost:8002')

# Database configurations
DB_SERVER = os.getenv('DB_SERVER', 'localhost')
DB_PORT = os.getenv('DB_PORT', '1433')
DB_USERNAME = os.getenv('DB_USERNAME', 'sa')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'Fyppear@test')
PATIENT_DB_NAME = os.getenv('PATIENT_DB_NAME', 'patient_service_test')
SCHEDULER_DB_NAME = os.getenv('SCHEDULER_DB_NAME', 'scheduler_service_test')

# Timeouts
MESSAGE_PROCESSING_TIMEOUT = 20  # seconds to wait for async processing
RETRY_INTERVAL = 2  # seconds between retries


def get_db_connection(database_name: str):
    """Create a database connection"""
    # Try different ODBC driver versions
    drivers = [
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 18 for SQL Server",
        "FreeTDS"
    ]
    
    for driver in drivers:
        try:
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={DB_SERVER},{DB_PORT};"
                f"DATABASE={database_name};"
                f"UID={DB_USERNAME};"
                f"PWD={DB_PASSWORD};"
                f"TrustServerCertificate=yes;"
            )
            return pyodbc.connect(connection_string)
        except pyodbc.Error:
            continue
    
    # If all drivers fail, raise error with helpful message
    raise Exception(f"Could not connect to database. Tried drivers: {drivers}. "
                   f"Available drivers: {pyodbc.drivers()}")


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
PATIENT_SERVICE_AVAILABLE = check_service_available(PATIENT_SERVICE_URL)
SCHEDULER_SERVICE_AVAILABLE = check_service_available(SCHEDULER_SERVICE_URL)
SERVICES_AVAILABLE = PATIENT_SERVICE_AVAILABLE and SCHEDULER_SERVICE_AVAILABLE

# Skip marker for when services are not available
require_services = pytest.mark.skipif(
    not SERVICES_AVAILABLE,
    reason="Patient and/or Scheduler services not available. "
           "These tests require running services. "
           "Run nightly E2E workflow or start services locally to execute these tests."
)


def get_patient_from_scheduler_db(patient_id: int) -> Optional[dict]:
    """Query the REF_PATIENT table directly in Scheduler database"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection(SCHEDULER_DB_NAME)
        cursor = conn.cursor()
        
        query = """
            SELECT PatientID, Name, PreferredName, UpdateBit, StartDate, EndDate, 
                   IsActive, IsDeleted, CreatedDateTime, UpdatedDateTime, 
                   CreatedById, ModifiedById
            FROM REF_PATIENT
            WHERE PatientID = ?
        """
        
        cursor.execute(query, patient_id)
        row = cursor.fetchone()
        
        if row:
            result = {
                'PatientID': row.PatientID,
                'Name': row.Name,
                'PreferredName': row.PreferredName,
                'UpdateBit': row.UpdateBit,
                'StartDate': row.StartDate,
                'EndDate': row.EndDate,
                'IsActive': row.IsActive,
                'IsDeleted': row.IsDeleted,
                'CreatedDateTime': row.CreatedDateTime,
                'UpdatedDateTime': row.UpdatedDateTime,
                'CreatedById': row.CreatedById,
                'ModifiedById': row.ModifiedById
            }
        else:
            result = None
        
        return result
        
    except Exception as e:
        print(f"Error querying scheduler database: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@pytest.mark.e2e
@pytest.mark.slow
class TestPatientServiceIntegration:
    """Test patient data flow from Patient Service to Scheduler Service via message queue"""

    @require_services
    def test_patient_create_propagation(self):
        """
        Test: Complete Patient Creation Flow
        
        Flow:
        1. POST /api/patients/add to Patient Service
        2. Patient Service publishes message to queue
        3. Scheduler Service consumes message and creates entry in REF_PATIENT
        4. Verify data in REF_PATIENT table matches
        """
        print(f"\n=== Test: Patient Create Propagation ===")
        
        # Step 1: Create patient via Patient Service
        patient_data = {
            "name": "E2E Test Patient Create",
            "nric": "S1234567A",
            "dateOfBirth": "1990-01-01T00:00:00",
            "gender": "M",
            "isActive": "1",
            "startDate": "2025-01-01T00:00:00",
            "isRespiteCare": "0",
            "updateBit": "1",
            "autoGame": "0",
            "preferredName": "Test Create"
        }
        
        print(f"Step 1: Creating patient in Patient Service...")
        create_response = requests.post(
            f"{PATIENT_SERVICE_URL}/api/patients/add?require_auth=false",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201], \
            f"Failed to create patient: {create_response.status_code} - {create_response.text}"
        
        response_data = create_response.json()
        patient_id = response_data['data']['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Step 2: Wait for message processing with retry logic
        print(f"Step 2: Waiting for message processing (max {MESSAGE_PROCESSING_TIMEOUT}s)...")
        
        scheduler_patient = None
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            # Query the REF_PATIENT table directly
            scheduler_patient = get_patient_from_scheduler_db(patient_id)
            
            if scheduler_patient:
                print(f"Patient found in REF_PATIENT table (attempt {attempt + 1})")
                break
            else:
                print(f"  Attempt {attempt + 1}/{max_retries}: Patient not yet in REF_PATIENT")
        
        # Step 3: Verify patient synced to Scheduler database
        assert scheduler_patient is not None, \
            f"Patient not found in REF_PATIENT table after {MESSAGE_PROCESSING_TIMEOUT}s"
        
        # Step 4: Verify data integrity
        print(f"Step 3: Verifying data integrity...")
        assert scheduler_patient['Name'] == patient_data['name'], \
            f"Name mismatch: expected '{patient_data['name']}', got '{scheduler_patient['Name']}'"
        assert scheduler_patient['PreferredName'] == patient_data['preferredName'], \
            f"PreferredName mismatch: expected '{patient_data['preferredName']}', got '{scheduler_patient['PreferredName']}'"
        assert scheduler_patient['IsActive'] == patient_data['isActive'], \
            f"IsActive mismatch: expected '{patient_data['isActive']}', got '{scheduler_patient['IsActive']}'"
        assert scheduler_patient['IsDeleted'] == "0", \
            f"IsDeleted should be '0', got '{scheduler_patient['IsDeleted']}'"
        
        print(f"Patient data synchronized correctly to REF_PATIENT table")
        print(f"Complete E2E create flow passed!")

    @require_services
    def test_patient_update_propagation(self):
        """
        Test: Patient Update Propagation
        
        Verify that patient updates in Patient Service propagate to REF_PATIENT table
        """
        print(f"\n=== Test: Patient Update Propagation ===")
        
        # Step 1: Create patient first
        patient_data = {
            "name": "E2E Test Update Original",
            "nric": "S2345678B",
            "dateOfBirth": "1985-05-15T00:00:00",
            "gender": "F",
            "isActive": "1",
            "startDate": "2025-01-01T00:00:00",
            "isRespiteCare": "0",
            "updateBit": "1",
            "autoGame": "0",
            "preferredName": "Original Name"
        }
        
        create_response = requests.post(
            f"{PATIENT_SERVICE_URL}/api/patients/add?require_auth=false",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201]
        patient_id = create_response.json()['data']['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Wait for initial sync
        print(f"Waiting for initial sync...")
        time.sleep(MESSAGE_PROCESSING_TIMEOUT)
        
        # Verify patient exists in REF_PATIENT
        scheduler_patient = get_patient_from_scheduler_db(patient_id)
        assert scheduler_patient is not None, "Patient should exist in REF_PATIENT before update"
        print(f"Patient synced to REF_PATIENT table")
        
        # Step 2: Update patient
        update_data = {
            "name": "E2E Test Update Modified",
            "preferredName": "Updated Name",
            "isActive": "1"
        }
        
        update_response = requests.put(
            f"{PATIENT_SERVICE_URL}/api/patients/update/{patient_id}?require_auth=false",
            json=update_data,
            timeout=10
        )
        
        assert update_response.status_code == 200, \
            f"Failed to update patient: {update_response.status_code} - {update_response.text}"
        print(f"Patient updated in Patient Service")
        
        # Step 3: Wait for update propagation
        print(f"Waiting for update propagation...")
        
        updated_scheduler_patient = None
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            patient = get_patient_from_scheduler_db(patient_id)
            
            if patient and patient['Name'] == "E2E Test Update Modified":
                updated_scheduler_patient = patient
                print(f"Update propagated to REF_PATIENT (attempt {attempt + 1})")
                break
            else:
                print(f"  Attempt {attempt + 1}/{max_retries}: Name not yet updated in REF_PATIENT")
        
        assert updated_scheduler_patient is not None, \
            "Update did not propagate to REF_PATIENT table"
        assert updated_scheduler_patient['Name'] == "E2E Test Update Modified"
        assert updated_scheduler_patient['PreferredName'] == "Updated Name"
        print(f"Update propagated successfully to REF_PATIENT table")

    @require_services
    def test_patient_delete_propagation(self):
        """
        Test: Patient Delete Propagation
        
        Verify that patient deletion (soft delete) in Patient Service propagates to REF_PATIENT table
        """
        print(f"\n=== Test: Patient Delete Propagation ===")
        
        # Step 1: Create patient
        patient_data = {
            "name": "E2E Test Delete",
            "nric": "S3456789C",
            "dateOfBirth": "1992-08-20T00:00:00",
            "gender": "M",
            "isActive": "1",
            "startDate": "2025-01-01T00:00:00",
            "isRespiteCare": "0",
            "updateBit": "1",
            "autoGame": "0",
            "preferredName": "Delete Test"
        }
        
        create_response = requests.post(
            f"{PATIENT_SERVICE_URL}/api/patients/add?require_auth=false",
            json=patient_data,
            timeout=10
        )
        
        assert create_response.status_code in [200, 201]
        patient_id = create_response.json()['data']['id']
        print(f"Patient created with ID: {patient_id}")
        
        # Wait for sync
        time.sleep(MESSAGE_PROCESSING_TIMEOUT)
        
        # Verify patient exists in REF_PATIENT
        scheduler_patient = get_patient_from_scheduler_db(patient_id)
        assert scheduler_patient is not None, "Patient should exist in REF_PATIENT before deletion"
        assert scheduler_patient['IsDeleted'] == "0", "Patient should not be deleted initially"
        print(f"Patient synced to REF_PATIENT table")
        
        # Step 2: Delete patient (soft delete)
        delete_response = requests.delete(
            f"{PATIENT_SERVICE_URL}/api/patients/delete/{patient_id}?require_auth=false",
            timeout=10
        )
        
        assert delete_response.status_code in [200, 204], \
            f"Failed to delete patient: {delete_response.status_code} - {delete_response.text}"
        print(f"Patient deleted in Patient Service")
        
        # Step 3: Wait and verify deletion propagated
        print(f"Waiting for deletion propagation...")
        
        deletion_propagated = False
        max_retries = MESSAGE_PROCESSING_TIMEOUT // RETRY_INTERVAL
        
        for attempt in range(max_retries):
            time.sleep(RETRY_INTERVAL)
            
            patient = get_patient_from_scheduler_db(patient_id)
            
            # Check if IsDeleted flag is set to "1"
            if patient and patient['IsDeleted'] == "1":
                deletion_propagated = True
                print(f"Soft delete propagated to REF_PATIENT (attempt {attempt + 1})")
                break
            else:
                status = patient['IsDeleted'] if patient else "not found"
                print(f"  Attempt {attempt + 1}/{max_retries}: IsDeleted={status}, waiting...")
        
        assert deletion_propagated, \
            "Deletion did not propagate to REF_PATIENT table"
        print(f"Deletion propagated successfully to REF_PATIENT table")

    @require_services
    def test_multiple_patients_bulk_sync(self):
        """
        Test: Multiple patients created in sequence sync correctly
        
        Verify that creating multiple patients in quick succession all sync to REF_PATIENT
        """
        print(f"\n=== Test: Multiple Patients Bulk Sync ===")
        
        patient_ids = []
        num_patients = 3
        
        # Create multiple patients
        for i in range(num_patients):
            patient_data = {
                "name": f"E2E Bulk Test Patient {i+1}",
                "nric": f"S456789{i}D",
                "dateOfBirth": "1988-03-10T00:00:00",
                "gender": "F" if i % 2 == 0 else "M",
                "isActive": "1",
                "startDate": "2025-01-01T00:00:00",
                "isRespiteCare": "0",
                "updateBit": "1",
                "autoGame": "0",
                "preferredName": f"Bulk {i+1}"
            }
            
            response = requests.post(
                f"{PATIENT_SERVICE_URL}/api/patients/add?require_auth=false",
                json=patient_data,
                timeout=10
            )
            
            assert response.status_code in [200, 201]
            patient_id = response.json()['data']['id']
            patient_ids.append(patient_id)
            print(f"Created patient {i+1}/{num_patients} with ID: {patient_id}")
        
        # Wait for all to sync
        print(f"Waiting for all patients to sync...")
        time.sleep(MESSAGE_PROCESSING_TIMEOUT)
        
        # Verify all patients are in REF_PATIENT
        synced_count = 0
        for patient_id in patient_ids:
            max_retries = 5
            for attempt in range(max_retries):
                patient = get_patient_from_scheduler_db(patient_id)
                if patient:
                    synced_count += 1
                    print(f"Patient {patient_id} synced to REF_PATIENT")
                    break
                time.sleep(2)
        
        assert synced_count == num_patients, \
            f"Only {synced_count}/{num_patients} patients synced to REF_PATIENT"
        
        print(f"All {num_patients} patients successfully synced to REF_PATIENT table")


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorHandlingIntegration:
    """Test error handling in patient sync operations"""

    @require_services
    def test_invalid_patient_data_handling(self):
        """
        Test: Invalid Patient Data Handling
        
        Verify that invalid patient data is rejected at API level
        """
        print(f"\n=== Test: Invalid Patient Data Handling ===")
        
        # Missing required fields
        invalid_data = {
            "name": "",  # Empty name should be invalid
            "nric": "INVALID"
        }
        
        response = requests.post(
            f"{PATIENT_SERVICE_URL}/api/patients/add?require_auth=false",
            json=invalid_data,
            timeout=10
        )
        
        # Should be rejected at API level (400 or 422)
        assert response.status_code >= 400, \
            f"Expected error status, got {response.status_code}"
        print(f"Invalid data rejected at API level with status {response.status_code}")

    @require_services
    def test_update_nonexistent_patient(self):
        """
        Test: Update Non-existent Patient
        
        Verify proper error handling when updating a patient that doesn't exist
        """
        print(f"\n=== Test: Update Non-existent Patient ===")
        
        nonexistent_id = 999999
        update_data = {
            "name": "Should Not Work"
        }
        
        response = requests.put(
            f"{PATIENT_SERVICE_URL}/api/patients/update/{nonexistent_id}?require_auth=false",
            json=update_data,
            timeout=10
        )
        
        # Should return 404
        assert response.status_code == 404, \
            f"Expected 404, got {response.status_code}"
        print(f"Non-existent patient update properly rejected with 404")


# Helper function for cleanup
@pytest.fixture(scope="function", autouse=False)
def cleanup_test_data():
    """
    Optional: Clean up test data after tests
    """
    yield
    print("Test cleanup completed")
