@echo off
REM install_plugin.bat - Auto-installer for BEV to QField plugin

echo.
echo ========================================
echo BEV to QField Plugin Installer
echo ========================================
echo.

REM Find QGIS plugins directory
set "APPDATA_DIR=%APPDATA%"
set "PLUGINS_DIR=%APPDATA_DIR%\QGIS\QGIS3\profiles\default\python\plugins"

echo Checking QGIS plugins directory...
echo   Expected location: %PLUGINS_DIR%

if not exist "%PLUGINS_DIR%" (
    echo.
    echo ERROR: QGIS plugins directory not found!
    echo.
    echo Please ensure:
    echo   1. QGIS 3.40 or later is installed
    echo   2. QGIS has been run at least once
    echo   3. Your Windows APPDATA profile is accessible
    echo.
    echo Manual installation:
    echo   Copy the "bev_to_qfield_plugin" folder to:
    echo   %PLUGINS_DIR%\
    echo.
    pause
    exit /b 1
)

echo ✓ Found QGIS plugins directory

REM Get current script directory
set "SCRIPT_DIR=%~dp0"
set "PLUGIN_SOURCE=%SCRIPT_DIR%"

echo.
echo Installing plugin...
echo   From: %PLUGIN_SOURCE%
echo   To:   %PLUGINS_DIR%\bev_to_qfield_plugin

REM Check if already installed
if exist "%PLUGINS_DIR%\bev_to_qfield_plugin" (
    echo.
    echo WARNING: Plugin already installed at destination
    set /p "CONFIRM=Do you want to overwrite? (y/n) [n]: "
    if /i not "%CONFIRM%"=="y" (
        echo Installation cancelled.
        exit /b 0
    )
    echo Removing old installation...
    rmdir /s /q "%PLUGINS_DIR%\bev_to_qfield_plugin"
)

REM Copy plugin
mkdir "%PLUGINS_DIR%\bev_to_qfield_plugin" 2>nul
xcopy "%PLUGIN_SOURCE%\*.*" "%PLUGINS_DIR%\bev_to_qfield_plugin\" /E /I /Y

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo ✓ Installation Successful!
    echo ========================================
    echo.
    echo Next steps:
    echo   1. Restart QGIS completely
    echo   2. Go to: Plugins ^→ Manage and Install Plugins
    echo   3. Search for "BEV to QField"
    echo   4. Enable the plugin
    echo   5. New menu item will appear under: Vector ^→ BEV to QField
    echo.
    echo For help, see: README.md in the plugin directory
    echo.
) else (
    echo.
    echo ========================================
    echo ✗ Installation Failed!
    echo ========================================
    echo.
    echo Please check:
    echo   - You have write permissions to %PLUGINS_DIR%
    echo   - QGIS is not running
    echo   - All files are present in %PLUGIN_SOURCE%
    echo.
)

pause
