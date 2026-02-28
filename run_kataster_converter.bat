@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "CLI_SCRIPT=%SCRIPT_DIR%scripts\kataster_converter_cli.py"
set "QFC_SYNC_SCRIPT=%SCRIPT_DIR%scripts\qfieldcloud_sync.py"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "QFC_CONFIG_FILE="

if "%OSGEO4W_ROOT%"=="" set "OSGEO4W_ROOT=C:\OSGeo4W"

if not exist "%CLI_SCRIPT%" (
  echo ERROR: Script not found: %CLI_SCRIPT%
  pause
  exit /b 2
)
if not exist "%QFC_SYNC_SCRIPT%" (
  echo ERROR: Script not found: %QFC_SYNC_SCRIPT%
  pause
  exit /b 2
)

if not exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" (
  echo ERROR: OSGeo4W not found at %OSGEO4W_ROOT%
  echo Set OSGEO4W_ROOT and try again.
  pause
  exit /b 2
)

set "QGIS_PY="
if exist "%OSGEO4W_ROOT%\apps\qgis-ltr\bin\python-qgis-ltr.bat" set "QGIS_PY=%OSGEO4W_ROOT%\apps\qgis-ltr\bin\python-qgis-ltr.bat"
if not defined QGIS_PY if exist "%OSGEO4W_ROOT%\bin\python-qgis.bat" set "QGIS_PY=%OSGEO4W_ROOT%\bin\python-qgis.bat"

if not defined QGIS_PY (
  echo ERROR: Could not locate QGIS Python launcher under %OSGEO4W_ROOT%
  pause
  exit /b 2
)

if not defined QFC_CONFIG_FILE if exist "%USERPROFILE%\QGIS\02_QGIS_Processing\qfieldcloud.env" set "QFC_CONFIG_FILE=%USERPROFILE%\QGIS\02_QGIS_Processing\qfieldcloud.env"
if not defined QFC_CONFIG_FILE (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\QGIS\02_QGIS_Processing") do (
    if exist "%%~fD\qfieldcloud.env" set "QFC_CONFIG_FILE=%%~fD\qfieldcloud.env"
  )
)
if not defined QFC_CONFIG_FILE if exist "%POWERSHELL_EXE%" (
  set "QFC_CFG_PICK=%TEMP%\qfc_cfg_pick_%RANDOM%_%RANDOM%.txt"
  "%POWERSHELL_EXE%" -NoProfile -Command "$cfg = Get-ChildItem -LiteralPath $env:USERPROFILE -Filter qfieldcloud.env -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\QGIS\\02_QGIS_Processing\\qfieldcloud\.env$' } | Select-Object -First 1 -ExpandProperty FullName; if($cfg){ Set-Content -LiteralPath $env:QFC_CFG_PICK -Value $cfg -Encoding Ascii }"
  if exist "!QFC_CFG_PICK!" (
    set /p QFC_CONFIG_FILE=<"!QFC_CFG_PICK!"
    del /q "!QFC_CFG_PICK!" >nul 2>nul
  )
)
if defined QFC_CONFIG_FILE if exist "!QFC_CONFIG_FILE!" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("!QFC_CONFIG_FILE!") do (
    if /I "%%A"=="QFIELDCLOUD_URL" if "!QFIELDCLOUD_URL!"=="" set "QFIELDCLOUD_URL=%%B"
    if /I "%%A"=="QFIELDCLOUD_TOKEN" if "!QFIELDCLOUD_TOKEN!"=="" set "QFIELDCLOUD_TOKEN=%%B"
    if /I "%%A"=="QFIELDCLOUD_USERNAME" if "!QFIELDCLOUD_USERNAME!"=="" set "QFIELDCLOUD_USERNAME=%%B"
    if /I "%%A"=="QFC_ROHDATEN_ROOT" if "!QFC_ROHDATEN_ROOT!"=="" set "QFC_ROHDATEN_ROOT=%%B"
    if /I "%%A"=="QFC_PROCESSING_ROOT" if "!QFC_PROCESSING_ROOT!"=="" set "QFC_PROCESSING_ROOT=%%B"
    if /I "%%A"=="QFC_OUTPUT_ROOT" if "!QFC_OUTPUT_ROOT!"=="" set "QFC_OUTPUT_ROOT=%%B"
    if /I "%%A"=="QFC_SYNC_ROOT" if "!QFC_SYNC_ROOT!"=="" set "QFC_SYNC_ROOT=%%B"
  )
)

echo.
echo Kataster Converter (headless)
echo.
set "SOURCE="
set "SOURCE_BROWSE_ROOT="
if defined QFC_ROHDATEN_ROOT if exist "!QFC_ROHDATEN_ROOT!\" set "SOURCE_BROWSE_ROOT=!QFC_ROHDATEN_ROOT!"
if not defined SOURCE_BROWSE_ROOT if defined QFC_CONFIG_FILE (
  set "SOURCE_BROWSE_ROOT=!QFC_CONFIG_FILE:\02_QGIS_Processing\qfieldcloud.env=\01_BEV_Rohdaten\entzippt!"
  if not exist "!SOURCE_BROWSE_ROOT!\" set "SOURCE_BROWSE_ROOT="
)
if not defined SOURCE_BROWSE_ROOT (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\QGIS\01_BEV_Rohdaten\entzippt") do (
    if not defined SOURCE_BROWSE_ROOT if exist "%%~fD" set "SOURCE_BROWSE_ROOT=%%~fD"
  )
)
if not defined SOURCE_BROWSE_ROOT if exist "%USERPROFILE%\QGIS\01_BEV_Rohdaten\entzippt\" (
  set "SOURCE_BROWSE_ROOT=%USERPROFILE%\QGIS\01_BEV_Rohdaten\entzippt"
)
if defined SOURCE_BROWSE_ROOT set "QFC_BROWSE_HINT=!SOURCE_BROWSE_ROOT!"
if defined SOURCE_BROWSE_ROOT (
  echo Source root: !SOURCE_BROWSE_ROOT!
  echo.
  echo Available source subfolders:
  set /a SRC_COUNT=0
  for /f "delims=" %%D in ('dir /b /ad "!SOURCE_BROWSE_ROOT!" 2^>nul') do (
    set /a SRC_COUNT+=1
    set "SRC_!SRC_COUNT!=!SOURCE_BROWSE_ROOT!\%%D"
    echo   [!SRC_COUNT!] %%D
  )
  if !SRC_COUNT! GTR 0 (
    echo.
    set "USE_DIALOG=0"
    set /p SRC_CHOICE=Choose number ^(D = folder dialog, ENTER = manual path^): 
    if defined SRC_CHOICE (
      for /f "tokens=* delims= " %%Z in ("!SRC_CHOICE!") do set "SRC_CHOICE=%%Z"
      set "SRC_CHOICE=!SRC_CHOICE: =!"
    )
    if defined SRC_CHOICE (
      if /I "!SRC_CHOICE!"=="D" (
        set "USE_DIALOG=1"
      ) else (
        call set "SOURCE=%%SRC_!SRC_CHOICE!%%"
      )
    )
    if not defined SOURCE if defined SRC_CHOICE if /I not "!SRC_CHOICE!"=="D" (
      echo Invalid selection: !SRC_CHOICE!
    )
  )
)

if "!SOURCE!"=="" if "!USE_DIALOG!"=="1" if exist "%POWERSHELL_EXE%" (
  set "SOURCE_PICK_FILE=%TEMP%\kataster_source_pick_%RANDOM%_%RANDOM%.txt"
  "%POWERSHELL_EXE%" -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='Select source folder with shapefiles'; $p=$env:QFC_BROWSE_HINT; if($p -and (Test-Path -LiteralPath $p)){ $d.SelectedPath=$p }; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){ Set-Content -LiteralPath $env:SOURCE_PICK_FILE -Value $d.SelectedPath -Encoding Ascii }"
  if exist "!SOURCE_PICK_FILE!" (
    set /p SOURCE=<"!SOURCE_PICK_FILE!"
    del /q "!SOURCE_PICK_FILE!" >nul 2>nul
  )
)

if "!SOURCE!"=="" (
  if "!USE_DIALOG!"=="1" echo No folder selected in dialog.
  set /p SOURCE=Source folder path ^(e.g. C:\...\01_BEV_Rohdaten\entzippt\44106^): 
)

if "!SOURCE!"=="" (
  echo ERROR: Source is required.
  pause
  exit /b 2
)
echo.
set "TARGET="
if not defined QFC_OUTPUT_ROOT (
  echo ERROR: QFC_OUTPUT_ROOT is not set in qfieldcloud.env
  pause
  exit /b 2
)
if not exist "!QFC_OUTPUT_ROOT!\" (
  echo ERROR: QFC_OUTPUT_ROOT path does not exist: !QFC_OUTPUT_ROOT!
  pause
  exit /b 2
)
for %%I in ("!SOURCE!") do set "SRC_FOLDER=%%~nxI"
set "TARGET=!QFC_OUTPUT_ROOT!\kataster_!SRC_FOLDER!_qfield.gpkg"
echo Using output root from env: !TARGET!

echo.
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"
set "SUMMARY_TARGET=%TEMP%\kataster_converter_target_%RANDOM%_%RANDOM%.txt"

call "%QGIS_PY%" "%CLI_SCRIPT%" --source "!SOURCE!" --target "!TARGET!" --summary-target-file "%SUMMARY_TARGET%"

set "EXITCODE=%ERRORLEVEL%"
set "TARGET_GPKG="
set "TARGET_QGZ="
set "PROJECT_DIR="
set "PROJECT_STEM="
set "QGIS_BASE="
set "SYNC_ROOT="
set "SYNC_PROJECT_DIR="
set "UPLOAD_DIR="

if exist "%SUMMARY_TARGET%" (
  set /p TARGET_GPKG=<"%SUMMARY_TARGET%"
  del /q "%SUMMARY_TARGET%" >nul 2>nul
)

if not defined TARGET_GPKG if not "!TARGET!"=="" set "TARGET_GPKG=!TARGET!"
if defined TARGET_GPKG (
  for %%I in ("!TARGET_GPKG!") do set "PROJECT_DIR=%%~dpI"
  for %%I in ("!TARGET_GPKG!") do set "PROJECT_STEM=%%~nI"
  for %%I in ("!TARGET_GPKG!") do set "TARGET_QGZ=%%~dpnI.qgz"
)
if defined PROJECT_DIR (
  for %%I in ("!PROJECT_DIR!..") do set "QGIS_BASE=%%~fI"
  if defined QFC_SYNC_ROOT if exist "!QFC_SYNC_ROOT!\" set "SYNC_ROOT=!QFC_SYNC_ROOT!"
  if not defined SYNC_ROOT if exist "!QGIS_BASE!\04_QField_Sync\" set "SYNC_ROOT=!QGIS_BASE!\04_QField_Sync"
  if defined QFC_PROCESSING_ROOT if exist "!QFC_PROCESSING_ROOT!\" set "QFC_CONFIG_FILE=!QFC_PROCESSING_ROOT!\qfieldcloud.env"
  if not defined QFC_CONFIG_FILE if exist "!QGIS_BASE!\02_QGIS_Processing\" set "QFC_CONFIG_FILE=!QGIS_BASE!\02_QGIS_Processing\qfieldcloud.env"
)
if defined SYNC_ROOT if defined PROJECT_STEM (
  set "SYNC_PROJECT_DIR=!SYNC_ROOT!\!PROJECT_STEM!"
)

  if defined QFC_CONFIG_FILE (
  if not exist "!QFC_CONFIG_FILE!" (
    > "!QFC_CONFIG_FILE!" echo # Local QFieldCloud credentials ^(not part of git repo^)
    >> "!QFC_CONFIG_FILE!" echo QFIELDCLOUD_URL=https://app.qfield.cloud/api/v1/
    if defined QFIELDCLOUD_USERNAME >> "!QFC_CONFIG_FILE!" echo QFIELDCLOUD_USERNAME=!QFIELDCLOUD_USERNAME!
    if defined QFIELDCLOUD_TOKEN >> "!QFC_CONFIG_FILE!" echo QFIELDCLOUD_TOKEN=!QFIELDCLOUD_TOKEN!
    if defined QFC_ROHDATEN_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_ROHDATEN_ROOT=!QFC_ROHDATEN_ROOT!
    if defined QFC_PROCESSING_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_PROCESSING_ROOT=!QFC_PROCESSING_ROOT!
    if defined QFC_OUTPUT_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_OUTPUT_ROOT=!QFC_OUTPUT_ROOT!
    if defined QFC_SYNC_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_SYNC_ROOT=!QFC_SYNC_ROOT!
  )
)

echo.
if "%EXITCODE%"=="0" (
  echo Finished successfully.
) else (
  echo Finished with errors. Exit code: %EXITCODE%
  echo Cloud sync skipped because conversion reported errors.
  goto :final
)

if defined SYNC_PROJECT_DIR (
  echo.
  echo Updating local QField sync project folder...
  if not exist "!SYNC_PROJECT_DIR!" mkdir "!SYNC_PROJECT_DIR!"
  if exist "!TARGET_GPKG!" (
    copy /y "!TARGET_GPKG!" "!SYNC_PROJECT_DIR!\!PROJECT_STEM!.gpkg" >nul
    echo Local sync GPKG updated: !SYNC_PROJECT_DIR!\!PROJECT_STEM!.gpkg
  ) else (
    echo WARNING: Converted GPKG not found for sync copy: !TARGET_GPKG!
  )
  if exist "!TARGET_QGZ!" (
    copy /y "!TARGET_QGZ!" "!SYNC_PROJECT_DIR!\!PROJECT_STEM!.qgz" >nul
    echo Local sync project file updated: !SYNC_PROJECT_DIR!\!PROJECT_STEM!.qgz
  ) else (
    echo WARNING: Converted QGZ not found for sync copy: !TARGET_QGZ!
  )
  set "UPLOAD_DIR=!SYNC_PROJECT_DIR!"
)

if not defined UPLOAD_DIR if defined PROJECT_DIR (
  set "UPLOAD_DIR=!PROJECT_DIR!"
)

echo.
echo Auto-upload to QFieldCloud is enabled.

if not defined UPLOAD_DIR (
  echo ERROR: Could not detect project folder for upload.
  set "EXITCODE=1"
  goto :final
)

if "%QFIELDCLOUD_URL%"=="" set "QFIELDCLOUD_URL=https://app.qfield.cloud/api/v1/"
set "USE_TOKEN=1"

if defined QFC_CONFIG_FILE if exist "!QFC_CONFIG_FILE!" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("!QFC_CONFIG_FILE!") do (
    if /I "%%A"=="QFIELDCLOUD_URL" if "!QFIELDCLOUD_URL!"=="https://app.qfield.cloud/api/v1/" set "QFIELDCLOUD_URL=%%B"
    if /I "%%A"=="QFIELDCLOUD_TOKEN" if "!QFIELDCLOUD_TOKEN!"=="" set "QFIELDCLOUD_TOKEN=%%B"
    if /I "%%A"=="QFIELDCLOUD_USERNAME" if "!QFIELDCLOUD_USERNAME!"=="" set "QFIELDCLOUD_USERNAME=%%B"
    if /I "%%A"=="QFC_ROHDATEN_ROOT" if "!QFC_ROHDATEN_ROOT!"=="" set "QFC_ROHDATEN_ROOT=%%B"
    if /I "%%A"=="QFC_PROCESSING_ROOT" if "!QFC_PROCESSING_ROOT!"=="" set "QFC_PROCESSING_ROOT=%%B"
    if /I "%%A"=="QFC_OUTPUT_ROOT" if "!QFC_OUTPUT_ROOT!"=="" set "QFC_OUTPUT_ROOT=%%B"
    if /I "%%A"=="QFC_SYNC_ROOT" if "!QFC_SYNC_ROOT!"=="" set "QFC_SYNC_ROOT=%%B"
  )
  echo Loaded QFieldCloud config: !QFC_CONFIG_FILE!
)

set "PROJECT_ID="
if defined PROJECT_STEM (
  if defined QFIELDCLOUD_USERNAME (
    set "PROJECT_ID=a/!QFIELDCLOUD_USERNAME!/!PROJECT_STEM!"
  ) else (
    set "PROJECT_ID=!PROJECT_STEM!"
  )
)
if "!PROJECT_ID!"=="" (
  set /p PROJECT_ID=QFieldCloud project identifier ^(e.g. a/christianahammer/kataster_44106_qfield^): 
)
if "!PROJECT_ID!"=="" (
  echo ERROR: project identifier is required for cloud sync.
  set "EXITCODE=1"
  goto :final
)
set "PROJECT_ID=!PROJECT_ID:https://app.qfield.cloud/=!"
set "PROJECT_ID=!PROJECT_ID:http://app.qfield.cloud/=!"
if "!PROJECT_ID:~0,1!"=="/" set "PROJECT_ID=!PROJECT_ID:~1!"
if "!PROJECT_ID:~-1!"=="/" set "PROJECT_ID=!PROJECT_ID:~0,-1!"
echo Using QFieldCloud project identifier: !PROJECT_ID!

call "%QGIS_PY%" -m qfieldcloud_sdk.cli --help >nul 2>nul
if errorlevel 1 (
  echo qfieldcloud-sdk is not installed in QGIS Python.
  set /p INSTALL_QFC=Install now via pip? ^(y/N^): 
  if /I "!INSTALL_QFC!"=="y" (
    call "%QGIS_PY%" -m pip install --upgrade qfieldcloud-sdk
  )
)

call "%QGIS_PY%" -m qfieldcloud_sdk.cli --help >nul 2>nul
if errorlevel 1 (
  echo ERROR: qfieldcloud-sdk CLI is unavailable.
  set "EXITCODE=1"
  goto :final
)

if "!QFIELDCLOUD_TOKEN!"=="" (
  echo.
  set /p LOGIN_MODE=No token set. Login with username/email instead? ^(Y/n^): 
  if /I not "!LOGIN_MODE!"=="n" if /I not "!LOGIN_MODE!"=="no" (
    set /p QFIELDCLOUD_USERNAME=QFieldCloud username or email: 
    if "!QFIELDCLOUD_USERNAME!"=="" (
      echo ERROR: username or email is required.
      set "EXITCODE=1"
      goto :final
    )
    set "USE_TOKEN=0"
  )
)

if "!QFIELDCLOUD_TOKEN!"=="" if "!USE_TOKEN!"=="1" (
  set /p QFIELDCLOUD_TOKEN=QFieldCloud token ^(input hidden not supported in .bat^): 
  if "!QFIELDCLOUD_TOKEN!"=="" (
    echo ERROR: token is required for cloud sync.
    set "EXITCODE=1"
    goto :final
  )
)

set "CLOUD_SUMMARY=%TEMP%\qfieldcloud_sync_%RANDOM%_%RANDOM%.json"

echo.
echo Starting verified QFieldCloud sync...
echo Project identifier: !PROJECT_ID!
echo Upload source folder: !UPLOAD_DIR!

if "!USE_TOKEN!"=="1" (
  call "%QGIS_PY%" "%QFC_SYNC_SCRIPT%" --url "%QFIELDCLOUD_URL%" --project-id "!PROJECT_ID!" --project-path "!UPLOAD_DIR!" --token "!QFIELDCLOUD_TOKEN!" --auto-create --wait-timeout 600 --summary-json "%CLOUD_SUMMARY%"
) else (
  call "%QGIS_PY%" "%QFC_SYNC_SCRIPT%" --url "%QFIELDCLOUD_URL%" --project-id "!PROJECT_ID!" --project-path "!UPLOAD_DIR!" --username "!QFIELDCLOUD_USERNAME!" --auto-create --wait-timeout 600 --summary-json "%CLOUD_SUMMARY%"
)
if errorlevel 1 (
  echo ERROR: cloud sync failed. See summary file:
  echo %CLOUD_SUMMARY%
  if exist "%CLOUD_SUMMARY%" type "%CLOUD_SUMMARY%"
  set "EXITCODE=1"
  goto :final
)
echo QFieldCloud sync completed successfully.
echo Summary file:
echo %CLOUD_SUMMARY%

:final
echo.
pause
exit /b %EXITCODE%
