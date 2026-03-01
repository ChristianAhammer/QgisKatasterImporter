@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "CLI_SCRIPT=%SCRIPT_DIR%scripts\kataster_converter_cli.py"
set "QFC_SYNC_SCRIPT=%SCRIPT_DIR%scripts\qfieldcloud_sync.py"
set "KG_LOOKUP_SCRIPT=%SCRIPT_DIR%scripts\kg_mapping_lookup.py"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "QFC_CONFIG_FILE="
set "QFC_WORKROOT_NAME=bev-qfield-workbench-data"
set "QFC_LEGACY_WORKROOT_NAME=QGIS"
set "KG_MAP_CACHE="
set "KG_MAP_FILE="
set "KG_MAP_COUNT="
set "KG_MAP_EXTRACTED_FROM="
set "KG_MAP_ERROR="

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
if not exist "%KG_LOOKUP_SCRIPT%" (
  echo WARNING: KG lookup helper not found: %KG_LOOKUP_SCRIPT%
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

if not defined QFC_CONFIG_FILE if exist "%USERPROFILE%\%QFC_WORKROOT_NAME%\02_QGIS_Processing\qfieldcloud.env" set "QFC_CONFIG_FILE=%USERPROFILE%\%QFC_WORKROOT_NAME%\02_QGIS_Processing\qfieldcloud.env"
if not defined QFC_CONFIG_FILE if exist "%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\02_QGIS_Processing\qfieldcloud.env" set "QFC_CONFIG_FILE=%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\02_QGIS_Processing\qfieldcloud.env"
if not defined QFC_CONFIG_FILE (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_WORKROOT_NAME%\02_QGIS_Processing") do (
    if exist "%%~fD\qfieldcloud.env" set "QFC_CONFIG_FILE=%%~fD\qfieldcloud.env"
  )
)
if not defined QFC_CONFIG_FILE (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_LEGACY_WORKROOT_NAME%\02_QGIS_Processing") do (
    if exist "%%~fD\qfieldcloud.env" set "QFC_CONFIG_FILE=%%~fD\qfieldcloud.env"
  )
)
if not defined QFC_CONFIG_FILE if exist "%POWERSHELL_EXE%" (
  set "QFC_CFG_PICK=%TEMP%\qfc_cfg_pick_%RANDOM%_%RANDOM%.txt"
  "%POWERSHELL_EXE%" -NoProfile -Command "$cfg = Get-ChildItem -LiteralPath $env:USERPROFILE -Filter qfieldcloud.env -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '\\(?:bev-qfield-workbench-data|QGIS)\\02_QGIS_Processing\\qfieldcloud\.env$' } | Select-Object -First 1 -ExpandProperty FullName; if($cfg){ Set-Content -LiteralPath $env:QFC_CFG_PICK -Value $cfg -Encoding Ascii }"
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
    if /I "%%A"=="QFC_RAWDATA_ROOT" if "!QFC_RAWDATA_ROOT!"=="" set "QFC_RAWDATA_ROOT=%%B"
    if /I "%%A"=="QFC_ROHDATEN_ROOT" if "!QFC_ROHDATEN_ROOT!"=="" set "QFC_ROHDATEN_ROOT=%%B"
    if /I "%%A"=="QFC_PROCESSING_ROOT" if "!QFC_PROCESSING_ROOT!"=="" set "QFC_PROCESSING_ROOT=%%B"
    if /I "%%A"=="QFC_OUTPUT_ROOT" if "!QFC_OUTPUT_ROOT!"=="" set "QFC_OUTPUT_ROOT=%%B"
    if /I "%%A"=="QFC_SYNC_ROOT" if "!QFC_SYNC_ROOT!"=="" set "QFC_SYNC_ROOT=%%B"
    if /I "%%A"=="QFC_KG_MAPPING_FILE" if "!QFC_KG_MAPPING_FILE!"=="" set "QFC_KG_MAPPING_FILE=%%B"
  )
)

echo.
echo Kataster Converter (headless)
echo.
set "SOURCE="
set "SOURCE_BROWSE_ROOT="
set "RAWDATA_ROOT="
if defined QFC_RAWDATA_ROOT if exist "!QFC_RAWDATA_ROOT!\" (
  set "RAWDATA_ROOT=!QFC_RAWDATA_ROOT!"
)
if not defined RAWDATA_ROOT if defined QFC_ROHDATEN_ROOT if exist "!QFC_ROHDATEN_ROOT!\" (
  set "RAWDATA_ROOT=!QFC_ROHDATEN_ROOT!"
  for %%I in ("!RAWDATA_ROOT!") do set "RAWDATA_LEAF=%%~nxI"
  if /I "!RAWDATA_LEAF!"=="entzippt" (
    for %%I in ("!RAWDATA_ROOT!\..") do set "RAWDATA_ROOT=%%~fI"
  )
)
if not defined RAWDATA_ROOT if defined QFC_CONFIG_FILE (
  set "RAWDATA_ROOT=!QFC_CONFIG_FILE:\02_QGIS_Processing\qfieldcloud.env=\01_BEV_Rawdata!"
  if not exist "!RAWDATA_ROOT!\" set "RAWDATA_ROOT="
  if not defined RAWDATA_ROOT (
    set "RAWDATA_ROOT=!QFC_CONFIG_FILE:\02_QGIS_Processing\qfieldcloud.env=\01_BEV_Rohdaten!"
    if not exist "!RAWDATA_ROOT!\" set "RAWDATA_ROOT="
  )
)
if not defined RAWDATA_ROOT (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_WORKROOT_NAME%\01_BEV_Rawdata") do (
    if not defined RAWDATA_ROOT if exist "%%~fD" set "RAWDATA_ROOT=%%~fD"
  )
)
if not defined RAWDATA_ROOT (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_WORKROOT_NAME%\01_BEV_Rohdaten") do (
    if not defined RAWDATA_ROOT if exist "%%~fD" set "RAWDATA_ROOT=%%~fD"
  )
)
if not defined RAWDATA_ROOT (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rawdata") do (
    if not defined RAWDATA_ROOT if exist "%%~fD" set "RAWDATA_ROOT=%%~fD"
  )
)
if not defined RAWDATA_ROOT (
  for /d %%D in ("%USERPROFILE%\Meine Ablage*\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rohdaten") do (
    if not defined RAWDATA_ROOT if exist "%%~fD" set "RAWDATA_ROOT=%%~fD"
  )
)
if not defined RAWDATA_ROOT if exist "%USERPROFILE%\%QFC_WORKROOT_NAME%\01_BEV_Rawdata\" (
  set "RAWDATA_ROOT=%USERPROFILE%\%QFC_WORKROOT_NAME%\01_BEV_Rawdata"
)
if not defined RAWDATA_ROOT if exist "%USERPROFILE%\%QFC_WORKROOT_NAME%\01_BEV_Rohdaten\" (
  set "RAWDATA_ROOT=%USERPROFILE%\%QFC_WORKROOT_NAME%\01_BEV_Rohdaten"
)
if not defined RAWDATA_ROOT if exist "%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rawdata\" (
  set "RAWDATA_ROOT=%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rawdata"
)
if not defined RAWDATA_ROOT if exist "%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rohdaten\" (
  set "RAWDATA_ROOT=%USERPROFILE%\%QFC_LEGACY_WORKROOT_NAME%\01_BEV_Rohdaten"
)
if defined RAWDATA_ROOT set "RAWDATA_ROOT=!RAWDATA_ROOT:/=\!"
if defined QFC_KG_MAPPING_FILE set "QFC_KG_MAPPING_FILE=!QFC_KG_MAPPING_FILE:/=\!"
if defined RAWDATA_ROOT (
  set "SOURCE_BROWSE_ROOT=!RAWDATA_ROOT!"
  call :ensure_rawdata_ready "!RAWDATA_ROOT!"
  call :prepare_kg_lookup "!RAWDATA_ROOT!"
  if not exist "!SOURCE_BROWSE_ROOT!\" set "SOURCE_BROWSE_ROOT="
)
if defined SOURCE_BROWSE_ROOT set "QFC_BROWSE_HINT=!SOURCE_BROWSE_ROOT!"
if defined SOURCE_BROWSE_ROOT (
  echo Source root: !SOURCE_BROWSE_ROOT!
  echo.
  echo already extracted KG's:
  set /a SRC_COUNT=0
  for /f "delims=" %%D in ('dir /b /ad "!SOURCE_BROWSE_ROOT!" 2^>nul') do (
    if /I not "%%D"=="entzippt" (
      echo(%%D| findstr /r "^[0-9][0-9][0-9][0-9][0-9]$" >nul
      if not errorlevel 1 (
        set /a SRC_COUNT+=1
        set "SRC_NAME_!SRC_COUNT!=%%D"
        set "SRC_PATH_!SRC_COUNT!=!SOURCE_BROWSE_ROOT!\%%D"
        set "SRC_LABEL=%%D"
        call :lookup_kg_name "%%D" SRC_KG_NAME
        if defined SRC_KG_NAME set "SRC_LABEL=%%D ^(!SRC_KG_NAME!^)"
        echo   - !SRC_LABEL!
      )
    )
  )
  echo.
  if !SRC_COUNT! LEQ 0 echo No extracted source subfolders found yet in Rawdata.
  echo Enter the 5-digit KatastralGemeinde number ^(KG-Nr.^), e.g. 51235.
  set "USE_DIALOG=0"
  set /p SRC_CHOICE=KG-Nr. / folder name ^(D = folder dialog, ENTER = manual path^): 
  if defined SRC_CHOICE (
    for /f "tokens=* delims= " %%Z in ("!SRC_CHOICE!") do set "SRC_CHOICE=%%Z"
  )
  if defined SRC_CHOICE (
    call :lookup_kg_name "!SRC_CHOICE!" SRC_CHOICE_KG_NAME
    if defined SRC_CHOICE_KG_NAME echo KG-Nr. !SRC_CHOICE! = !SRC_CHOICE_KG_NAME!
  )
  if defined SRC_CHOICE (
    if /I "!SRC_CHOICE!"=="D" (
      set "USE_DIALOG=1"
    ) else (
      set "SOURCE="
      for /L %%I in (1,1,!SRC_COUNT!) do (
        call set "SRC_NAME=%%SRC_NAME_%%I%%"
        call set "SRC_PATH=%%SRC_PATH_%%I%%"
        if /I "!SRC_CHOICE!"=="!SRC_NAME!" set "SOURCE=!SRC_PATH!"
      )
      if not defined SOURCE if defined RAWDATA_ROOT (
        call :ensure_source_folder_unzipped "!RAWDATA_ROOT!" "!SOURCE_BROWSE_ROOT!" "!SRC_CHOICE!"
        if exist "!SOURCE_BROWSE_ROOT!\!SRC_CHOICE!\" set "SOURCE=!SOURCE_BROWSE_ROOT!\!SRC_CHOICE!"
      )
    )
  )
  if not defined SOURCE if defined SRC_CHOICE if /I not "!SRC_CHOICE!"=="D" (
    if defined SRC_CHOICE_KG_NAME (
      echo Folder / KG-Nr. not available: !SRC_CHOICE! ^(!SRC_CHOICE_KG_NAME!^)
    ) else (
      echo Folder / KG-Nr. not available: !SRC_CHOICE!
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
  set /p SOURCE=Source folder path ^(e.g. C:\...\01_BEV_Rawdata\51235 where 51235 = KG-Nr.^): 
)

if "!SOURCE!"=="" (
  echo ERROR: Source is required.
  pause
  exit /b 2
)
for %%I in ("!SOURCE!") do set "SOURCE_FOLDER=%%~nxI"
call :lookup_kg_name "!SOURCE_FOLDER!" SOURCE_KG_NAME
if defined SOURCE_KG_NAME (
  echo Selected KatastralGemeinde: !SOURCE_FOLDER! ^(!SOURCE_KG_NAME!^)
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
set "TARGET_PROJECT=kataster_!SRC_FOLDER!_qfield"
set "TARGET=!QFC_OUTPUT_ROOT!\!TARGET_PROJECT!\!TARGET_PROJECT!.gpkg"
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
if defined QFC_OUTPUT_ROOT (
  for %%I in ("!QFC_OUTPUT_ROOT!\..") do set "QGIS_BASE=%%~fI"
)
if not defined QGIS_BASE if defined PROJECT_DIR (
  for %%I in ("!PROJECT_DIR!..") do set "QGIS_BASE=%%~fI"
  if not exist "!QGIS_BASE!\04_QField_Sync\" (
    for %%I in ("!PROJECT_DIR!\..\..") do set "QGIS_BASE=%%~fI"
  )
)
if defined PROJECT_DIR (
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
    if defined QFC_RAWDATA_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_RAWDATA_ROOT=!QFC_RAWDATA_ROOT!
    if defined QFC_ROHDATEN_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_ROHDATEN_ROOT=!QFC_ROHDATEN_ROOT!
    if defined QFC_PROCESSING_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_PROCESSING_ROOT=!QFC_PROCESSING_ROOT!
    if defined QFC_OUTPUT_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_OUTPUT_ROOT=!QFC_OUTPUT_ROOT!
    if defined QFC_SYNC_ROOT >> "!QFC_CONFIG_FILE!" echo QFC_SYNC_ROOT=!QFC_SYNC_ROOT!
    if defined QFC_KG_MAPPING_FILE >> "!QFC_CONFIG_FILE!" echo QFC_KG_MAPPING_FILE=!QFC_KG_MAPPING_FILE!
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
    if /I "%%A"=="QFC_RAWDATA_ROOT" if "!QFC_RAWDATA_ROOT!"=="" set "QFC_RAWDATA_ROOT=%%B"
    if /I "%%A"=="QFC_ROHDATEN_ROOT" if "!QFC_ROHDATEN_ROOT!"=="" set "QFC_ROHDATEN_ROOT=%%B"
    if /I "%%A"=="QFC_PROCESSING_ROOT" if "!QFC_PROCESSING_ROOT!"=="" set "QFC_PROCESSING_ROOT=%%B"
    if /I "%%A"=="QFC_OUTPUT_ROOT" if "!QFC_OUTPUT_ROOT!"=="" set "QFC_OUTPUT_ROOT=%%B"
    if /I "%%A"=="QFC_SYNC_ROOT" if "!QFC_SYNC_ROOT!"=="" set "QFC_SYNC_ROOT=%%B"
    if /I "%%A"=="QFC_KG_MAPPING_FILE" if "!QFC_KG_MAPPING_FILE!"=="" set "QFC_KG_MAPPING_FILE=%%B"
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

:prepare_kg_lookup
set "KG_LOOKUP_ROOT=%~1"
if defined KG_MAP_CACHE goto :eof
if not defined KG_LOOKUP_ROOT goto :eof
if not exist "!KG_LOOKUP_ROOT!\" goto :eof
if not exist "%KG_LOOKUP_SCRIPT%" goto :eof

set "KG_MAP_STATUS=%TEMP%\kg_map_status_%RANDOM%_%RANDOM%.txt"
set "KG_MAP_TMP=%TEMP%\kg_map_cache_%RANDOM%_%RANDOM%.txt"
set "KG_MAP_ERROR="
if defined QFC_KG_MAPPING_FILE (
  call "%QGIS_PY%" "%KG_LOOKUP_SCRIPT%" --rawdata-root "!KG_LOOKUP_ROOT!" --mapping-file "!QFC_KG_MAPPING_FILE!" --cache-out "!KG_MAP_TMP!" --status-file "!KG_MAP_STATUS!" >nul 2>nul
) else (
  call "%QGIS_PY%" "%KG_LOOKUP_SCRIPT%" --rawdata-root "!KG_LOOKUP_ROOT!" --cache-out "!KG_MAP_TMP!" --status-file "!KG_MAP_STATUS!" >nul 2>nul
)
set "KG_LOOKUP_EXIT=%ERRORLEVEL%"

if exist "!KG_MAP_STATUS!" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("!KG_MAP_STATUS!") do (
    if /I "%%A"=="MAPPING_FILE" set "KG_MAP_FILE=%%B"
    if /I "%%A"=="EXTRACTED_FROM" set "KG_MAP_EXTRACTED_FROM=%%B"
    if /I "%%A"=="COUNT" set "KG_MAP_COUNT=%%B"
    if /I "%%A"=="ERROR" set "KG_MAP_ERROR=%%B"
  )
  del /q "!KG_MAP_STATUS!" >nul 2>nul
)

if "%KG_LOOKUP_EXIT%"=="0" (
  if exist "!KG_MAP_TMP!" (
    set "KG_MAP_CACHE=!KG_MAP_TMP!"
    if defined KG_MAP_FILE (
      echo KG mapping loaded: !KG_MAP_FILE! ^(!KG_MAP_COUNT! entries^)
    ) else (
      echo KG mapping loaded.
    )
    if defined KG_MAP_EXTRACTED_FROM echo KG mapping extracted from ZIP: !KG_MAP_EXTRACTED_FROM!
  ) else (
    set "KG_MAP_ERROR=KG cache file was not created."
    echo NOTE: KG name lookup unavailable: !KG_MAP_ERROR!
  )
) else (
  if exist "!KG_MAP_TMP!" del /q "!KG_MAP_TMP!" >nul 2>nul
  if defined KG_MAP_ERROR (
    echo NOTE: KG name lookup unavailable: !KG_MAP_ERROR!
  ) else (
    echo NOTE: KG name lookup unavailable.
  )
)
goto :eof

:lookup_kg_name
set "KG_LOOKUP_NUMBER=%~1"
set "KG_LOOKUP_RESULT="
if not defined KG_LOOKUP_NUMBER goto kg_lookup_done
if not defined KG_MAP_CACHE goto kg_lookup_done
if not exist "!KG_MAP_CACHE!" goto kg_lookup_done

echo(!KG_LOOKUP_NUMBER!| findstr /r "^[0-9][0-9][0-9][0-9][0-9]$" >nul
if errorlevel 1 goto kg_lookup_done

for /f "usebackq tokens=1,* delims=;" %%A in (`findstr /b /c:"!KG_LOOKUP_NUMBER!;" "!KG_MAP_CACHE!" 2^>nul`) do (
  set "KG_LOOKUP_RESULT=%%B"
  goto kg_lookup_done
)

:kg_lookup_done
if not "%~2"=="" set "%~2=!KG_LOOKUP_RESULT!"
goto :eof

:ensure_rawdata_ready
set "UNZIP_RAWDATA=%~1"
if not defined UNZIP_RAWDATA goto :eof
if not exist "!UNZIP_RAWDATA!\" mkdir "!UNZIP_RAWDATA!" >nul 2>nul
if not exist "!UNZIP_RAWDATA!\" goto :eof
goto :eof

:ensure_source_folder_unzipped
set "UNZIP_RAWDATA=%~1"
set "UNZIP_TARGET_ROOT=%~2"
set "UNZIP_FOLDER=%~3"
if not defined UNZIP_RAWDATA goto :eof
if not defined UNZIP_TARGET_ROOT goto :eof
if not defined UNZIP_FOLDER goto :eof
if not exist "!UNZIP_RAWDATA!\" goto :eof
if exist "!UNZIP_TARGET_ROOT!\!UNZIP_FOLDER!\" goto :eof

if not exist "!UNZIP_TARGET_ROOT!\" mkdir "!UNZIP_TARGET_ROOT!" >nul 2>nul

set /a ZIP_COUNT=0
for /f "delims=" %%Z in ('dir /b /a-d "!UNZIP_RAWDATA!\*.zip" 2^>nul') do set /a ZIP_COUNT+=1
if !ZIP_COUNT! LEQ 0 (
  echo No ZIP archives found in "!UNZIP_RAWDATA!".
  goto :eof
)

if not exist "%POWERSHELL_EXE%" (
  echo WARNING: PowerShell is unavailable; cannot extract "!UNZIP_FOLDER!" from ZIP.
  goto :eof
)

echo Folder "!UNZIP_FOLDER!" not yet extracted. Searching ZIP archive^(s^)...
set "QFC_UNZIP_SRC=!UNZIP_RAWDATA!"
set "QFC_UNZIP_DST=!UNZIP_TARGET_ROOT!"
set "QFC_UNZIP_FOLDER=!UNZIP_FOLDER!"
"%POWERSHELL_EXE%" -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $src=$env:QFC_UNZIP_SRC; $dst=$env:QFC_UNZIP_DST; $wanted=$env:QFC_UNZIP_FOLDER; $found=$false; $zips=Get-ChildItem -LiteralPath $src -Filter *.zip -File -ErrorAction SilentlyContinue; foreach($zipFile in $zips){ $zip=[System.IO.Compression.ZipFile]::OpenRead($zipFile.FullName); try { foreach($entry in $zip.Entries){ $entryName=$entry.FullName.Replace('\','/'); if([string]::IsNullOrWhiteSpace($entryName)){ continue }; $parts=$entryName.Split('/', [System.StringSplitOptions]::RemoveEmptyEntries); $idx=-1; for($i=0; $i -lt $parts.Length; $i++){ if($parts[$i] -ieq $wanted){ $idx=$i; break } }; if($idx -lt 0){ continue }; $found=$true; $relParts=$parts[$idx..($parts.Length-1)]; $target=Join-Path $dst ($relParts -join '\'); if($entry.Name -eq ''){ [System.IO.Directory]::CreateDirectory($target) | Out-Null; continue }; $targetDir=Split-Path -Parent $target; if($targetDir){ [System.IO.Directory]::CreateDirectory($targetDir) | Out-Null }; [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true) } } finally { $zip.Dispose() } }; if(-not $found){ exit 3 }"
if errorlevel 3 (
  echo Folder "!UNZIP_FOLDER!" was not found in available ZIP archive^(s^).
  goto :eof
)
if errorlevel 1 (
  echo WARNING: ZIP extraction reported an error for "!UNZIP_FOLDER!".
  goto :eof
)
if exist "!UNZIP_TARGET_ROOT!\!UNZIP_FOLDER!\" (
  echo Extracted folder to "!UNZIP_TARGET_ROOT!\!UNZIP_FOLDER!".
) else (
  echo WARNING: Extraction completed but folder "!UNZIP_FOLDER!" is still missing.
)
goto :eof
