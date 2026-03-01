@echo off
REM Run MCP black-box QGIS project check
setlocal

if "%~1"=="" (
    echo Usage: run_mcp_blackbox_test.bat ^<path-to-project.qgs^|.qgz^> [additional args]
    echo Example:
    echo   run_mcp_blackbox_test.bat "C:\Users\Christian\Meine Ablage\QGIS\03_QField_Output\kataster_44106_qfield.qgz"
    exit /b 1
)

cd /d "%~dp0"
set "PROJECT=%~1"
shift

set "PYTHON_CMD=python"
if exist "C:\OSGeo4W\bin\python-qgis.bat" (
    set "PYTHON_CMD=C:\OSGeo4W\bin\python-qgis.bat"
)

%PYTHON_CMD% scripts\qgis_mcp_blackbox_check.py --project "%PROJECT%" --prompt-start-server %1 %2 %3 %4 %5 %6 %7 %8 %9
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% equ 0 (
    echo.
    echo ========================================
    echo MCP Black-Box Check: PASSED
    echo ========================================
) else (
    echo.
    echo ========================================
    echo MCP Black-Box Check: FAILED (code: %EXIT_CODE%)
    echo ========================================
)

endlocal & exit /b %EXIT_CODE%
