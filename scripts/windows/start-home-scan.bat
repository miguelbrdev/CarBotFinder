@echo off
REM Starts home-scan-window.bat in its own window and remembers its PID so that
REM stop-home-scan.bat can stop exactly that window. Arguments are passed through.
setlocal
set "ROOT=%~dp0..\.."
set "PIDFILE=%ROOT%\state\home-scan.pid"

if not exist "%PIDFILE%" goto :check_env
set /p OLDPID=<"%PIDFILE%"
tasklist /FI "PID eq %OLDPID%" 2>nul | find "%OLDPID%" >nul
if errorlevel 1 goto :stale
echo Already running ^(PID %OLDPID%^). Run stop-home-scan.bat first.
pause
exit /b 1
:stale
del "%PIDFILE%"

:check_env
if exist "%ROOT%\.env" goto :start
echo Missing %ROOT%\.env  ^(copy .env.example and fill in the Telegram token and chat id^)
pause
exit /b 1

:start
if not exist "%ROOT%\state" mkdir "%ROOT%\state"
powershell -NoProfile -Command ^
  "$p = Start-Process cmd -WorkingDirectory '%ROOT%' -PassThru -ArgumentList '/k', '\"%~dp0home-scan-window.bat\" %*';" ^
  "Set-Content -Path '%PIDFILE%' -Value $p.Id -Encoding ascii"
if errorlevel 1 goto :fail
set /p NEWPID=<"%PIDFILE%"
echo Started CarBotFinder home scan ^(PID %NEWPID%^). Stop it with stop-home-scan.bat
exit /b 0

:fail
echo Could not start the scan window.
pause
exit /b 1
