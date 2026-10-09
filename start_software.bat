@echo off
rem InboundRoute 软件启动：按模块工作台里已启用的模块拉起整套软件
setlocal
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
