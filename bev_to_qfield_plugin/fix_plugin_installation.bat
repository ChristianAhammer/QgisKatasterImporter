@echo off
REM fix_plugin_installation.bat - Reinstalls the plugin with the fix

setlocal enabledelayedexpansion

REM Define paths
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "PLUGIN_SOURCE=%SCRIPT_DIR%"
set "PLUGINS_ROOT=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins"
set "PLUGIN_DEST=%PLUGINS_ROOT%\bev_to_qfield_plugin"

echo.
echo ========================================
echo BEV to QField Plugin - Fix Installation
echo ========================================
echo.

echo Checking if QGIS plugins directory exists...
if not exist "%PLUGINS_ROOT%" (
    echo ERROR: QGIS plugins directory not found!
    echo Checked: "%PLUGINS_ROOT%"
    echo.
    pause
    exit /b 1
)

echo ✓ Found QGIS plugins directory
echo.

echo Removing old plugin installation...
if exist "!PLUGIN_DEST!" (
    rmdir /s /q "!PLUGIN_DEST!" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo ✓ Old installation removed
    ) else (
        echo WARNING: Could not remove old installation (might be in use)
    )
)

echo.
echo Installing updated plugin...
mkdir "!PLUGIN_DEST!" >nul 2>&1

REM Copy all plugin files
xcopy "!PLUGIN_SOURCE!\*.*" "!PLUGIN_DEST!" /E /I /Y >nul 2>&1

if !ERRORLEVEL! equ 0 (
    echo ✓ Plugin files copied successfully
    echo.
    echo.
    echo ========================================
    echo ✓ Installation Complete!
    echo ========================================
    echo.
    echo IMPORTANT: You MUST restart QGIS completely
    echo (close it completely and reopen)
    echo.
    echo Then reload the plugin:
    echo  1. Plugins ^→ Manage and Install Plugins
    echo  2. Search for "BEV to QField"
    echo  3. Make sure it's checked/enabled
    echo  4. Click "Close"
    echo.
    echo The plugin should now work without errors!
    echo.
) else (
    echo.
    echo ERROR: Failed to copy plugin files!
    echo.
    echo Possible causes:
    echo  - QGIS is still running (close it completely)
    echo  - Permission denied (run as Administrator)
    echo  - Source path error
    echo.
)

pause
