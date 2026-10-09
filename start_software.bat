@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 goto use_py
python start_software.py %*
goto finished
:use_py
where py >nul 2>&1
if errorlevel 1 goto missing
py -3 start_software.py %*
goto finished
:missing
echo Python 3.10+ is required. Please install Python and try again.
pause
exit /b 1
:finished
if errorlevel 1 pause
