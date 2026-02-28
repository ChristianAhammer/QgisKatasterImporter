@echo off
REM Test QGIS integration script runner
setlocal enabledelayedexpansion

REM Set OSGeo4W environment
set OSGEO4W_ROOT=C:\OSGeo4W
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

REM Change to script directory
cd /d "%~dp0"

REM Run the test
python test_qgis_integration.py

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

REM Display result
if %EXIT_CODE% equ 0 (
    echo.
    echo ========================================
    echo QGIS Integration Tests: PASSED
    echo ========================================
) else (
    echo.
    echo ========================================
    echo QGIS Integration Tests: FAILED (code: %EXIT_CODE%)
    echo ========================================
    exit /b %EXIT_CODE%
)

endlocal
