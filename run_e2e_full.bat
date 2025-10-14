@echo off
REM Full E2E Test Runner with Services for PEAR Message Queue (Windows)
REM This script runs complete E2E tests including Activity and Scheduler services

echo ==============================================
echo PEAR Message Queue - Full E2E Test Runner
echo with Activity ^& Scheduler Services
echo ==============================================
echo.

REM Configuration - Update these with your registry IPs
set RABBITMQ_IMAGE=192.168.188.184:5000/rabbitmq_service_dev:latest
set ACTIVITY_SERVICE_IMAGE=192.168.188.186:5000/activity_service_dev:latest
set SCHEDULER_SERVICE_IMAGE=192.168.188.173:5000/pear_schedule:latest
set SQLSERVER_IMAGE=mcr.microsoft.com/mssql/server:2022-latest
set DB_PASSWORD=Fyppear@test

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker and try again.
    exit /b 1
)
echo [OK] Docker is running

REM Step 1: Start SQL Server
echo.
echo [INFO] Step 1/7: Starting SQL Server...
docker ps --filter "name=test-sqlserver" --format "{{.Names}}" | findstr /x "test-sqlserver" >nul 2>&1
if errorlevel 1 (
    docker run -d ^
        --name test-sqlserver ^
        -e "ACCEPT_EULA=Y" ^
        -e "SA_PASSWORD=%DB_PASSWORD%" ^
        -e "MSSQL_PID=Developer" ^
        -p 1433:1433 ^
        %SQLSERVER_IMAGE%
    
    echo [OK] SQL Server container started
    echo Waiting for SQL Server to be ready...
    timeout /t 15 /nobreak >nul
) else (
    echo [WARNING] SQL Server container already running
)

REM Step 2: Create test databases
echo.
echo [INFO] Step 2/7: Creating test databases...
docker exec test-sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "%DB_PASSWORD%" -Q "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'activity_service_test') BEGIN CREATE DATABASE activity_service_test; END IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'scheduler_service_test') BEGIN CREATE DATABASE scheduler_service_test; END" >nul 2>&1
echo [OK] Test databases created ^(activity_service_test, scheduler_service_test^)

REM Step 3: Start RabbitMQ
echo.
echo [INFO] Step 3/7: Starting RabbitMQ...
docker ps --filter "name=test-rabbitmq" --format "{{.Names}}" | findstr /x "test-rabbitmq" >nul 2>&1
if errorlevel 1 (
    REM Try to pull from registry first, fallback to Docker Hub
    docker pull %RABBITMQ_IMAGE% 2>nul || docker pull rabbitmq:4.1.1-management
    
    docker run -d ^
        --name test-rabbitmq ^
        -p 5672:5672 ^
        -p 15672:15672 ^
        -e RABBITMQ_DEFAULT_USER=admin ^
        -e RABBITMQ_DEFAULT_PASS=pear2025 ^
        -e RABBITMQ_DEFAULT_VHOST=vhost ^
        %RABBITMQ_IMAGE%
    
    echo [OK] RabbitMQ container started
    echo Waiting for RabbitMQ to be ready...
    timeout /t 20 /nobreak >nul
) else (
    echo [WARNING] RabbitMQ container already running
)

REM Step 4: Load RabbitMQ definitions
echo.
echo [INFO] Step 4/7: Loading RabbitMQ definitions...
if exist definitions.yaml (
    docker cp definitions.yaml test-rabbitmq:/tmp/definitions.yaml
    docker exec test-rabbitmq rabbitmqctl import_definitions /tmp/definitions.yaml
    timeout /t 3 /nobreak >nul
    echo [OK] RabbitMQ definitions loaded
) else (
    echo [ERROR] definitions.yaml not found in current directory
    goto cleanup
)

REM Step 5: Start Activity Service
echo.
echo [INFO] Step 5/7: Starting Activity Service...
docker ps --filter "name=test-activity-service" --format "{{.Names}}" | findstr /x "test-activity-service" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Pulling Activity Service image...
    docker pull %ACTIVITY_SERVICE_IMAGE%
    
    docker run -d ^
        --name test-activity-service ^
        -p 8001:8000 ^
        -e DB_SERVER=host.docker.internal ^
        -e DB_PORT=1433 ^
        -e DB_DATABASE=activity_service_test ^
        -e DB_USERNAME=sa ^
        -e "DB_PASSWORD=%DB_PASSWORD%" ^
        -e RABBITMQ_HOST=host.docker.internal ^
        -e RABBITMQ_PORT=5672 ^
        -e RABBITMQ_VHOST=vhost ^
        -e RABBITMQ_USER=admin ^
        -e RABBITMQ_PASSWORD=pear2025 ^
        %ACTIVITY_SERVICE_IMAGE%
    
    echo [OK] Activity Service container started
    echo Waiting for Activity Service to be ready...
    timeout /t 15 /nobreak >nul
) else (
    echo [WARNING] Activity Service already running
)

REM Step 6: Start Scheduler Service
echo.
echo [INFO] Step 6/7: Starting Scheduler Service...
docker ps --filter "name=test-scheduler-service" --format "{{.Names}}" | findstr /x "test-scheduler-service" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Pulling Scheduler Service image...
    docker pull %SCHEDULER_SERVICE_IMAGE%
    
    docker run -d ^
        --name test-scheduler-service ^
        -p 8002:8000 ^
        -e DB_SERVER=host.docker.internal ^
        -e DB_PORT=1433 ^
        -e DB_DATABASE=scheduler_service_test ^
        -e DB_USERNAME=sa ^
        -e "DB_PASSWORD=%DB_PASSWORD%" ^
        -e RABBITMQ_HOST=host.docker.internal ^
        -e RABBITMQ_PORT=5672 ^
        -e RABBITMQ_VHOST=vhost ^
        -e RABBITMQ_USER=admin ^
        -e RABBITMQ_PASSWORD=pear2025 ^
        %SCHEDULER_SERVICE_IMAGE%
    
    echo [OK] Scheduler Service container started
    echo Waiting for Scheduler Service to be ready...
    timeout /t 15 /nobreak >nul
) else (
    echo [WARNING] Scheduler Service already running
)

REM Verify all services
echo.
echo [INFO] Verifying all services...
for /f "tokens=*" %%i in ('docker ps --filter name^=test-sqlserver --format "{{.Status}}"') do echo   SQL Server:        %%i
for /f "tokens=*" %%i in ('docker ps --filter name^=test-rabbitmq --format "{{.Status}}"') do echo   RabbitMQ:          %%i
for /f "tokens=*" %%i in ('docker ps --filter name^=test-activity-service --format "{{.Status}}"') do echo   Activity Service:  %%i
for /f "tokens=*" %%i in ('docker ps --filter name^=test-scheduler-service --format "{{.Status}}"') do echo   Scheduler Service: %%i

REM Step 7: Install Python dependencies
echo.
echo [INFO] Step 7/7: Installing Python test dependencies...
if exist tests\requirements.txt (
    pip install -q -r tests\requirements.txt
    echo [OK] Python dependencies installed
) else (
    echo [WARNING] tests\requirements.txt not found, skipping...
)

REM Set environment variables
set DB_SERVER=localhost
set DB_PORT=1433
set DB_USERNAME=sa
set ACTIVITY_DB_NAME=activity_service_test
set SCHEDULER_DB_NAME=scheduler_service_test
set RABBITMQ_HOST=localhost
set RABBITMQ_PORT=5672
set RABBITMQ_VHOST=vhost
set RABBITMQ_USER=admin
set RABBITMQ_PASSWORD=pear2025
set ACTIVITY_SERVICE_URL=http://localhost:8001
set SCHEDULER_SERVICE_URL=http://localhost:8002
echo [OK] Environment variables configured

REM Run tests
echo.
echo ==============================================
echo [INFO] Running FULL E2E Tests ^(Infrastructure + Service Integration^)
echo ==============================================
echo.

if "%~1"=="" (
    REM Run ALL tests including service integration
    pytest tests\e2e\ -v --tb=short --capture=no
) else (
    REM Run specific test file or pattern
    pytest %*
)

set TEST_EXIT_CODE=%ERRORLEVEL%

REM Display results
echo.
echo ==============================================
if %TEST_EXIT_CODE%==0 (
    echo [OK] All tests passed! ✨
) else (
    echo [ERROR] Some tests failed ^(exit code: %TEST_EXIT_CODE%^)
    
    echo.
    set /p SHOW_LOGS="Display container logs? (y/n): "
    if /i "%SHOW_LOGS%"=="y" (
        echo.
        echo === RabbitMQ Logs ^(last 50 lines^) ===
        docker logs test-rabbitmq --tail 50
        echo.
        echo === Activity Service Logs ^(last 50 lines^) ===
        docker logs test-activity-service --tail 50
        echo.
        echo === Scheduler Service Logs ^(last 50 lines^) ===
        docker logs test-scheduler-service --tail 50
        echo.
        echo === SQL Server Logs ^(last 50 lines^) ===
        docker logs test-sqlserver --tail 50
    )
)

:cleanup
echo.
echo Cleaning up containers...
docker stop test-rabbitmq test-sqlserver test-activity-service test-scheduler-service >nul 2>&1
docker rm test-rabbitmq test-sqlserver test-activity-service test-scheduler-service >nul 2>&1
echo [OK] Cleanup completed

exit /b %TEST_EXIT_CODE%
