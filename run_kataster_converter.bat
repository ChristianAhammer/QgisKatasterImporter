@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "CLI_SCRIPT=%SCRIPT_DIR%scripts\kataster_converter_cli.py"

if "%OSGEO4W_ROOT%"=="" set "OSGEO4W_ROOT=C:\OSGeo4W"

if not exist "%CLI_SCRIPT%" (
  echo ERROR: Script not found: %CLI_SCRIPT%
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

echo.
echo Kataster Converter (headless)
echo.
set "SOURCE="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='Select source folder with shapefiles'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.SelectedPath}"`) do set "SOURCE=%%I"

if "%SOURCE%"=="" (
  echo No folder selected in dialog.
  set /p SOURCE=Source folder path ^(e.g. C:\...\01_BEV_Rohdaten\entzippt\44106^): 
)

if "%SOURCE%"=="" (
  echo ERROR: Source is required.
  pause
  exit /b 2
)

echo.
set /p TARGET=Target GPKG path ^(optional, ENTER = auto to 03_QField_Output^): 

echo.
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

if "%TARGET%"=="" (
  call "%QGIS_PY%" "%CLI_SCRIPT%" --source "%SOURCE%"
) else (
  call "%QGIS_PY%" "%CLI_SCRIPT%" --source "%SOURCE%" --target "%TARGET%"
)

set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (
  echo Finished successfully.
) else (
  echo Finished with errors. Exit code: %EXITCODE%
)

echo.
pause
exit /b %EXITCODE%
