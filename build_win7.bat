@echo off
REM Builds a Windows 7 compatible exe.
REM Windows 7 needs Python 3.8 (the last version that supports it) and an
REM older PyInstaller. Install Python 3.8.10 from python.org first:
REM   64-bit: https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
REM   32-bit: https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe
REM Usage: build_win7.bat        (64-bit, default)
REM        build_win7.bat 32     (32-bit, for 32-bit Windows 7)
cd /d "%~dp0"

set "PYVER=3.8"
set "SUFFIX=Win7-x64"
if "%~1"=="32" (
  set "PYVER=3.8-32"
  set "SUFFIX=Win7-x86"
)

py -%PYVER% --version >nul 2>&1 || (
  echo Python %PYVER% not found. Install Python 3.8.10 from python.org ^(see top of this file^).
  goto :error
)

py -%PYVER% -m pip install "pyinstaller==5.13.2" || goto :error
py -%PYVER% -m PyInstaller --onefile --noconsole --clean --name CheckInstrumentReminder-%SUFFIX% reminder.py || goto :error
echo.
echo Built: dist\CheckInstrumentReminder-%SUFFIX%.exe
echo Rename it to CheckInstrumentReminder.exe on the target PC (install_task.bat expects that name).
pause
exit /b 0
:error
echo Build failed.
pause
exit /b 1
