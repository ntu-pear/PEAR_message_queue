@echo off
REM Local E2E Test Runner for PEAR Message Queue (Windows)
REM This script helps run E2E tests locally with Docker containers

echo ===================================
echo PEAR Message Queue - E2E Test Runner
echo ===================================
echo.

REM Configuration
set RABBITMQ_IMAGE=rabbitmq:4.1.1-management
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
echo Step 1: Starting SQL Server...
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
echo Step 2: Creating test databases...
docker exec test-sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "%DB_PASSWORD%" -Q "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'activity_service_test') BEGIN CREATE DATABASE activity_service_test; END IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'scheduler_service_test') BEGIN CREATE DATABASE scheduler_service_test; END" >nul 2>&1
echo [OK] Test databases created

REM Step 3: Start RabbitMQ
echo.
echo Step 3: Starting RabbitMQ...
docker ps --filter "name=test-rabbitmq" --format "{{.Names}}" | findstr /x "test-rabbitmq" >nul 2>&1
if errorlevel 1 (
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
    timeout /t 15 /nobreak >nul
) else (
    echo [WARNING] RabbitMQ container already running
)

REM Step 4: Load RabbitMQ definitions
echo.
echo Step 4: Loading RabbitMQ definitions...
if exist definitions.yaml (
    docker cp definitions.yaml test-rabbitmq:/tmp/definitions.yaml
    docker exec test-rabbitmq rabbitmqctl import_definitions /tmp/definitions.yaml
    echo [OK] RabbitMQ definitions loaded
) else (
    echo [ERROR] definitions.yaml not found in current directory
    goto cleanup
)

REM Step 5: Install Python dependencies
echo.
echo Step 5: Installing Python test dependencies...
if exist tests\requirements.txt (
    pip install -q -r tests\requirements.txt
    echo [OK] Python dependencies installed
) else (
    echo [WARNING] tests\requirements.txt not found, skipping...
)

REM Step 6: Set environment variables
echo.
echo Step 6: Setting environment variables...
set DB_SERVER=localhost
set DB_PORT=1433
set DB_USERNAME=sa
set DB_PASSWORD=%DB_PASSWORD%
set ACTIVITY_DB_NAME=activity_service_test
set SCHEDULER_DB_NAME=scheduler_service_test
set RABBITMQ_HOST=localhost
set RABBITMQ_PORT=5672
set RABBITMQ_VHOST=vhost
set RABBITMQ_USER=admin
set RABBITMQ_PASSWORD=pear2025
echo [OK] Environment variables configured

REM Step 7: Run tests
echo.
echo Step 7: Running E2E tests...
echo =========================================
echo.

if "%~1"=="" (
    REM Run all tests
    pytest tests\e2e\ -v --tb=short --capture=no
) else (
    REM Run specific test file or pattern
    pytest %*
)

set TEST_EXIT_CODE=%ERRORLEVEL%

REM Step 8: Display results
echo.
echo =========================================
if %TEST_EXIT_CODE%==0 (
    echo [OK] All tests passed!
) else (
    echo [ERROR] Some tests failed ^(exit code: %TEST_EXIT_CODE%^)
    
    echo.
    set /p SHOW_LOGS="Display container logs? (y/n): "
    if /i "%SHOW_LOGS%"=="y" (
        echo.
        echo === RabbitMQ Logs ^(last 50 lines^) ===
        docker logs test-rabbitmq --tail 50
        echo.
        echo === SQL Server Logs ^(last 50 lines^) ===
        docker logs test-sqlserver --tail 50
    )
)

:cleanup
echo.
echo Cleaning up containers...
docker stop test-rabbitmq test-sqlserver >nul 2>&1
docker rm test-rabbitmq test-sqlserver >nul 2>&1
echo [OK] Cleanup completed

exit /b %TEST_EXIT_CODE%
