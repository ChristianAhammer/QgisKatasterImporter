@echo off
REM Start QGIS + MCP server (if needed) and run MCP black-box integration check
setlocal EnableExtensions

if "%~1"=="" (
    echo Usage: run_mcp_integration_test.bat ^<path-to-project.qgs^|.qgz^> [additional black-box args]
    echo Example:
    echo   run_mcp_integration_test.bat "C:\Users\Christian\Meine Ablage\bev-qfield-workbench-data\03_QField_Output\kataster_51235_qfield\kataster_51235_qfield.qgz"
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PROJECT=%~1"
shift

if exist "%PROJECT%" goto project_ok
echo ERROR: Project file not found:
echo   %PROJECT%
exit /b 2

:project_ok

if "%OSGEO4W_ROOT%"=="" set "OSGEO4W_ROOT=C:\OSGeo4W"

set "QGIS_EXE="
if exist "%OSGEO4W_ROOT%\bin\qgis-ltr-bin.exe" set "QGIS_EXE=%OSGEO4W_ROOT%\bin\qgis-ltr-bin.exe"
if not defined QGIS_EXE if exist "%OSGEO4W_ROOT%\bin\qgis-bin.exe" set "QGIS_EXE=%OSGEO4W_ROOT%\bin\qgis-bin.exe"

set "QGIS_PY="
if exist "%OSGEO4W_ROOT%\bin\python-qgis.bat" set "QGIS_PY=%OSGEO4W_ROOT%\bin\python-qgis.bat"
if not defined QGIS_PY if exist "%OSGEO4W_ROOT%\apps\qgis-ltr\bin\python-qgis-ltr.bat" set "QGIS_PY=%OSGEO4W_ROOT%\apps\qgis-ltr\bin\python-qgis-ltr.bat"

if not defined QGIS_EXE (
    echo ERROR: QGIS executable not found under %OSGEO4W_ROOT%
    exit /b 2
)
if not defined QGIS_PY (
    echo ERROR: QGIS Python launcher not found under %OSGEO4W_ROOT%
    exit /b 2
)

set "AUTOSTART_SCRIPT=%SCRIPT_DIR%scripts\qgis_mcp_autostart.py"
if not exist "%AUTOSTART_SCRIPT%" (
    echo ERROR: Autostart script not found:
    echo   %AUTOSTART_SCRIPT%
    exit /b 2
)

set "MCP_PORT=9876"
set "WAIT_SECONDS=90"
if not "%QFC_MCP_WAIT_SECONDS%"=="" set "WAIT_SECONDS=%QFC_MCP_WAIT_SECONDS%"
set "STARTED_QGIS=0"
set "QGIS_PID="
set "CLOSE_STARTED_QGIS=1"
if not "%QFC_MCP_KEEP_QGIS%"=="" set "CLOSE_STARTED_QGIS=0"

call :probe_port %MCP_PORT%
if errorlevel 1 (
    echo MCP server on port %MCP_PORT% is not reachable.
    echo Starting QGIS with MCP autostart script...
    set "QGIS_PID_FILE=%TEMP%\qfc_mcp_qgis_pid_%RANDOM%_%RANDOM%.txt"
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; $p=Start-Process -FilePath '%QGIS_EXE%' -ArgumentList '--code','%AUTOSTART_SCRIPT%' -PassThru; Set-Content -LiteralPath '%QGIS_PID_FILE%' -Value $p.Id -Encoding Ascii" >nul 2>nul
    if exist "%QGIS_PID_FILE%" (
        set /p QGIS_PID=<"%QGIS_PID_FILE%"
        del /q "%QGIS_PID_FILE%" >nul 2>nul
    )
    if defined QGIS_PID (
        set "STARTED_QGIS=1"
        echo Started QGIS process PID: %QGIS_PID%
    )

    echo Waiting up to %WAIT_SECONDS%s for MCP server...
    call :wait_for_port %MCP_PORT% %WAIT_SECONDS%
    if errorlevel 1 (
        echo ERROR: MCP server did not become reachable on port %MCP_PORT%.
        echo Ensure QGIS is open and plugin qgis_mcp_plugin is enabled.
        exit /b 3
    )
) else (
    echo MCP server already reachable on port %MCP_PORT%.
)

echo.
echo Running MCP black-box integration check...
"%QGIS_PY%" "%SCRIPT_DIR%scripts\qgis_mcp_blackbox_check.py" --project "%PROJECT%" %1 %2 %3 %4 %5 %6 %7 %8 %9
set "EXIT_CODE=%ERRORLEVEL%"

if "%STARTED_QGIS%"=="1" if "%CLOSE_STARTED_QGIS%"=="1" (
    if defined QGIS_PID (
        echo Closing QGIS process PID %QGIS_PID%...
        powershell -NoProfile -Command "Stop-Process -Id %QGIS_PID% -ErrorAction SilentlyContinue" >nul 2>nul
    )
)

if %EXIT_CODE% equ 0 (
    echo.
    echo ========================================
    echo MCP Integration Test: PASSED
    echo ========================================
) else (
    echo.
    echo ========================================
    echo MCP Integration Test: FAILED (code: %EXIT_CODE%)
    echo ========================================
)

endlocal & exit /b %EXIT_CODE%

:probe_port
set "PORT=%~1"
powershell -NoProfile -Command "$ok=$false; try { $c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PORT%); $c.Close(); $ok=$true } catch {}; if($ok){exit 0}else{exit 1}" >nul 2>nul
exit /b %ERRORLEVEL%

:wait_for_port
set "PORT=%~1"
set "SECS=%~2"
powershell -NoProfile -Command "$port=%PORT%; $deadline=(Get-Date).AddSeconds(%SECS%); $ok=$false; while((Get-Date) -lt $deadline){ try{ $c=New-Object Net.Sockets.TcpClient('127.0.0.1',$port); $c.Close(); $ok=$true; break } catch {}; Start-Sleep -Milliseconds 500 }; if($ok){exit 0}else{exit 1}" >nul 2>nul
exit /b %ERRORLEVEL%
