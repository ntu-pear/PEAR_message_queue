"""End-to-end routine propagation tests.

The flow under test is:

    Activity Service API -> activity.updates -> Scheduler Service consumer
    -> REF_ACTIVITY_ROUTINE

Routine creation validates the patient through Patient Service, so the test
environment must also expose a patient service with at least one patient. A
specific patient can be selected with ``ROUTINE_TEST_PATIENT_ID``; otherwise
the first patient returned by the Patient Service test endpoint is used.
"""

import os
import time
import uuid
from datetime import date, timedelta
from typing import Any, Callable, Dict, Optional

import pyodbc
import pytest
import requests


ACTIVITY_SERVICE_URL = os.getenv("ACTIVITY_SERVICE_URL", "http://localhost:8001").rstrip("/")
PATIENT_SERVICE_URL = os.getenv("PATIENT_SERVICE_URL", "http://localhost:8003").rstrip("/")
SCHEDULER_SERVICE_URL = os.getenv("SCHEDULER_SERVICE_URL", "http://localhost:8002").rstrip("/")

DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_USERNAME = os.getenv("DB_USERNAME", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD")
SCHEDULER_DB_NAME = os.getenv("SCHEDULER_DB_NAME", "scheduler_service_test")

MESSAGE_PROCESSING_TIMEOUT = int(os.getenv("MESSAGE_PROCESSING_TIMEOUT", "20"))
RETRY_INTERVAL = int(os.getenv("RETRY_INTERVAL", "2"))


def _service_is_available(url: str) -> bool:
    """Return whether a service responds successfully to a health probe."""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass

    try:
        response = requests.get(url, timeout=5)
        return response.status_code < 500
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def routine_services() -> Dict[str, str]:
    """Require the services needed for the full routine propagation flow."""
    service_urls = {
        "Activity Service": ACTIVITY_SERVICE_URL,
        "Patient Service": PATIENT_SERVICE_URL,
        "Scheduler Service": SCHEDULER_SERVICE_URL,
    }
    unavailable = [
        name for name, url in service_urls.items()
        if not _service_is_available(url)
    ]
    if unavailable:
        pytest.skip(
            "Routine propagation tests require running services; unavailable: "
            + ", ".join(unavailable)
        )
    return service_urls


def _db_connection(database_name: str):
    """Open a SQL Server connection using the drivers used by the E2E runner."""
    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD must be set for routine integration tests")

    drivers = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "FreeTDS",
    )
    last_error: Optional[Exception] = None
    for driver in drivers:
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={DB_SERVER},{DB_PORT};"
            f"DATABASE={database_name};"
            f"UID={DB_USERNAME};"
            f"PWD={DB_PASSWORD};"
            "TrustServerCertificate=yes;"
        )
        try:
            return pyodbc.connect(connection_string)
        except pyodbc.Error as error:
            last_error = error

    raise RuntimeError(
        f"Could not connect to {database_name}; tried {drivers}. "
        f"Available drivers: {pyodbc.drivers()}"
    ) from last_error


def _scheduler_query(query: str, *parameters: Any) -> Optional[Dict[str, Any]]:
    """Run a single-row scheduler query and return a name-keyed result."""
    connection = None
    cursor = None
    try:
        connection = _db_connection(SCHEDULER_DB_NAME)
        cursor = connection.cursor()
        cursor.execute(query, *parameters)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _scheduler_patient(patient_id: int) -> Optional[Dict[str, Any]]:
    return _scheduler_query(
        """
        SELECT TOP 1 PatientID, IsDeleted
        FROM REF_PATIENT
        WHERE PatientID = ?
        """,
        patient_id,
    )


def _scheduler_activity(activity_id: int) -> Optional[Dict[str, Any]]:
    return _scheduler_query(
        """
        SELECT TOP 1 ActivityID, IsDeleted
        FROM REF_ACTIVITY
        WHERE ActivityID = ?
        """,
        activity_id,
    )


def _scheduler_routine(routine_id: int) -> Optional[Dict[str, Any]]:
    return _scheduler_query(
        """
        SELECT TOP 1 RoutineID, PatientID, ActivityID, IsDeleted,
               IncludeInSchedule, CreatedDateTime, UpdatedDateTime,
               CreatedById, ModifiedById
        FROM REF_ACTIVITY_ROUTINE
        WHERE RoutineID = ?
        """,
        routine_id,
    )


def _wait_for(
    description: str,
    fetch: Callable[[], Optional[Dict[str, Any]]],
    condition: Callable[[Optional[Dict[str, Any]]], bool],
) -> Dict[str, Any]:
    """Poll for an asynchronously propagated row until it satisfies a condition."""
    deadline = time.monotonic() + MESSAGE_PROCESSING_TIMEOUT
    last_row: Optional[Dict[str, Any]] = None
    last_error: Optional[Exception] = None

    while time.monotonic() < deadline:
        try:
            last_row = fetch()
            if condition(last_row):
                assert last_row is not None
                return last_row
        except (pyodbc.Error, RuntimeError) as error:
            last_error = error
        time.sleep(RETRY_INTERVAL)

    detail = f"last row={last_row!r}"
    if last_error is not None:
        detail += f", last database error={last_error}"
    pytest.fail(f"{description} after {MESSAGE_PROCESSING_TIMEOUT}s ({detail})")


def _request_headers() -> Dict[str, str]:
    """Return the optional bearer token used by protected staging setups."""
    token = os.getenv("ROUTINE_TEST_AUTH_TOKEN") or os.getenv("ACTIVITY_SERVICE_TOKEN")
    if not token:
        return {}
    if token.lower().startswith("bearer "):
        return {"Authorization": token}
    return {"Authorization": f"Bearer {token}"}


def _response_payload(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _response_id(response: requests.Response, resource_name: str) -> int:
    payload = _response_payload(response)
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    raw_id = data.get("id") if isinstance(data, dict) else None
    if raw_id is None and isinstance(data, dict):
        raw_id = data.get("routine_id") or data.get("RoutineID")
    assert raw_id is not None, (
        f"{resource_name} response did not contain an id: {payload!r}"
    )
    return int(raw_id)


def _resolve_patient_id() -> int:
    configured_id = os.getenv("ROUTINE_TEST_PATIENT_ID")
    if configured_id:
        try:
            return int(configured_id)
        except ValueError as error:
            pytest.fail(f"ROUTINE_TEST_PATIENT_ID must be an integer: {error}")

    try:
        response = requests.get(
            f"{PATIENT_SERVICE_URL}/api/v1/patients/",
            params={
                "require_auth": "false",
                "mask": "true",
                "pageNo": 0,
                "pageSize": 1,
            },
            timeout=10,
        )
    except requests.RequestException as error:
        pytest.skip(f"Could not query Patient Service for a routine fixture: {error}")

    if response.status_code != 200:
        pytest.skip(
            "Patient Service did not expose an unauthenticated test patient list "
            f"({response.status_code}): {response.text}"
        )

    payload = _response_payload(response)
    if isinstance(payload, dict):
        patients = payload.get("data", [])
    else:
        patients = payload
    if not patients:
        pytest.skip(
            "No patient fixture is available. Set ROUTINE_TEST_PATIENT_ID to an "
            "existing patient in the integration environment."
        )

    patient = patients[0]
    patient_id = patient.get("id") or patient.get("PatientID")
    if patient_id is None:
        pytest.skip(f"Patient Service response has no patient id: {payload!r}")
    return int(patient_id)


def _create_activity() -> int:
    suffix = uuid.uuid4().hex[:12]
    response = requests.post(
        f"{ACTIVITY_SERVICE_URL}/api/v1/activities/",
        json={
            "title": f"E2E Routine Activity {suffix}",
            "description": "Activity created for routine service propagation testing",
        },
        headers=_request_headers(),
        timeout=10,
    )
    assert response.status_code in (200, 201), (
        f"Failed to create Activity Service fixture: "
        f"{response.status_code} - {response.text}"
    )
    activity_id = _response_id(response, "Activity")

    _wait_for(
        f"Activity {activity_id} to propagate to Scheduler Service",
        lambda: _scheduler_activity(activity_id),
        lambda row: row is not None and str(row["IsDeleted"]) in ("0", "False"),
    )
    return activity_id


def _create_routine() -> Dict[str, Any]:
    patient_id = _resolve_patient_id()
    _wait_for(
        f"Patient {patient_id} to be available in Scheduler Service",
        lambda: _scheduler_patient(patient_id),
        lambda row: row is not None and str(row["IsDeleted"]) in ("0", "False"),
    )
    activity_id = _create_activity()
    start_date = date.today() + timedelta(days=1)
    end_date = start_date + timedelta(days=14)
    routine_data = {
        "name": f"E2E Routine {uuid.uuid4().hex[:12]}",
        "activity_id": activity_id,
        "patient_id": patient_id,
        "day_of_week": 1,
        "start_time": "09:00:00",
        "end_time": "10:00:00",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    response = requests.post(
        f"{ACTIVITY_SERVICE_URL}/api/v1/routines/",
        json=routine_data,
        headers=_request_headers(),
        timeout=10,
    )
    assert response.status_code in (200, 201), (
        f"Failed to create routine in Activity Service: "
        f"{response.status_code} - {response.text}"
    )
    routine_id = _response_id(response, "Routine")
    return {
        "id": routine_id,
        "activity_id": activity_id,
        "patient_id": patient_id,
        "data": routine_data,
    }


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
class TestRoutineServiceIntegration:
    """Test routine CRUD propagation from Activity Service to Scheduler Service."""

    def test_routine_create_propagation(self, routine_services, rabbitmq_channel):
        """A created routine is persisted by Scheduler with its source identifiers."""
        routine = _create_routine()

        scheduler_routine = _wait_for(
            f"routine {routine['id']} creation to propagate",
            lambda: _scheduler_routine(routine["id"]),
            lambda row: row is not None and str(row["IsDeleted"]) in ("0", "False"),
        )

        assert scheduler_routine["RoutineID"] == routine["id"]
        assert scheduler_routine["PatientID"] == routine["patient_id"]
        assert scheduler_routine["ActivityID"] == routine["activity_id"]
        assert str(scheduler_routine["IsDeleted"]) in ("0", "False")
        assert str(scheduler_routine["IncludeInSchedule"]) == "1"
        assert scheduler_routine["CreatedDateTime"] is not None
        assert scheduler_routine["UpdatedDateTime"] is not None

    def test_routine_update_propagation(self, routine_services, rabbitmq_channel):
        """An updated routine reaches Scheduler and advances its audit timestamp."""
        routine = _create_routine()
        original = _wait_for(
            f"routine {routine['id']} creation to propagate before update",
            lambda: _scheduler_routine(routine["id"]),
            lambda row: row is not None and str(row["IsDeleted"]) in ("0", "False"),
        )

        updated_data = dict(routine["data"])
        updated_data["id"] = routine["id"]
        updated_data["name"] = f"{updated_data['name']} Updated"
        response = requests.put(
            f"{ACTIVITY_SERVICE_URL}/api/v1/routines/",
            json=updated_data,
            headers=_request_headers(),
            timeout=10,
        )
        assert response.status_code == 200, (
            f"Failed to update routine in Activity Service: "
            f"{response.status_code} - {response.text}"
        )

        scheduler_routine = _wait_for(
            f"routine {routine['id']} update to propagate",
            lambda: _scheduler_routine(routine["id"]),
            lambda row: (
                row is not None
                and str(row["IsDeleted"]) in ("0", "False")
                and row["UpdatedDateTime"] != original["UpdatedDateTime"]
            ),
        )

        assert scheduler_routine["RoutineID"] == routine["id"]
        assert scheduler_routine["PatientID"] == routine["patient_id"]
        assert scheduler_routine["ActivityID"] == routine["activity_id"]

    def test_routine_delete_propagation(self, routine_services, rabbitmq_channel):
        """A deleted routine is soft-deleted in Scheduler."""
        routine = _create_routine()
        _wait_for(
            f"routine {routine['id']} creation to propagate before delete",
            lambda: _scheduler_routine(routine["id"]),
            lambda row: row is not None and str(row["IsDeleted"]) in ("0", "False"),
        )

        response = requests.delete(
            f"{ACTIVITY_SERVICE_URL}/api/v1/routines/{routine['id']}",
            headers=_request_headers(),
            timeout=10,
        )
        assert response.status_code in (200, 204), (
            f"Failed to delete routine in Activity Service: "
            f"{response.status_code} - {response.text}"
        )

        scheduler_routine = _wait_for(
            f"routine {routine['id']} deletion to propagate",
            lambda: _scheduler_routine(routine["id"]),
            lambda row: row is not None and str(row["IsDeleted"]) in ("1", "True"),
        )

        assert scheduler_routine["RoutineID"] == routine["id"]
        assert scheduler_routine["PatientID"] == routine["patient_id"]
        assert scheduler_routine["ActivityID"] == routine["activity_id"]
