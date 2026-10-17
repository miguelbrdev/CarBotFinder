@echo off
REM Runs CarBotFinder in this window until Ctrl+C or the window is closed.
REM Default portals: the ones that block GitHub's IPs. Override with arguments.
title CarBotFinder home scan
cd /d "%~dp0.."
set "PORTALS=--portal milanuncios --portal autocasion"
if not "%~1"=="" set "PORTALS=%*"
where uv >nul 2>nul
if errorlevel 1 (set "UV=python -m uv") else (set "UV=uv")
%UV% run carbotfinder run %PORTALS% --interval 300 -v
