@echo off
REM Stops the window started by start-home-scan.bat.
setlocal
set "PIDFILE=%~dp0..\state\home-scan.pid"
if not exist "%PIDFILE%" goto :not_running
set /p PID=<"%PIDFILE%"
tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
if errorlevel 1 goto :stale
taskkill /PID %PID% /T /F >nul
del "%PIDFILE%"
echo Stopped CarBotFinder home scan ^(PID %PID%^).
exit /b 0

:stale
del "%PIDFILE%"
:not_running
echo CarBotFinder home scan is not running.
exit /b 0
