@echo off
set "EXE=%~dp0CheckInstrumentReminder.exe"
if not exist "%EXE%" (
  echo CheckInstrumentReminder.exe not found next to this script.
  pause
  exit /b 1
)
schtasks /Create /TN "CheckInstrumentReminder" /TR "\"%EXE%\"" /SC MINUTE /MO 30 /F
if errorlevel 1 (echo Failed to create task.) else (echo Task "CheckInstrumentReminder" installed: runs every 30 minutes.)
pause
