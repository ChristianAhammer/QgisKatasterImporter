@echo off
setlocal

echo Kopiere Plugin...

REM Quelle: Repo-Pfad
set SOURCE=C:\Users\Christian\GitRepos\QgisKatasterImporter

REM Ziel: QGIS Plugin-Verzeichnis
set TARGET=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\kataster_converter

REM Vorherige Version löschen
rmdir /S /Q "%TARGET%"

REM Kopieren (inkl. Unterordner, still)
xcopy "%SOURCE%" "%TARGET%" /E /I /Y >nul

echo Fertig. Plugin wurde aktualisiert.
pause
