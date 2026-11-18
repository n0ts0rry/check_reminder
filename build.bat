@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :error
python -m PyInstaller --onefile --noconsole --name CheckInstrumentReminder reminder.py || goto :error
echo.
echo Built: dist\CheckInstrumentReminder.exe
pause
exit /b 0
:error
echo Build failed.
pause
exit /b 1
