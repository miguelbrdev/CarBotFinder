@echo off
REM One pass over the home portals (milanuncios, Autocasion), then exit.
REM New matching ads are sent to Telegram and recorded in the state file.
REM Override the portals with arguments, e.g.: refresh-home-scan.bat --portal wallapop
title CarBotFinder refresh
cd /d "%~dp0..\.."
set "PORTALS=--portal milanuncios --portal autocasion"
if not "%~1"=="" set "PORTALS=%*"
where uv >nul 2>nul
if errorlevel 1 (set "UV=python -m uv") else (set "UV=uv")
%UV% run carbotfinder run %PORTALS%
echo.
pause
