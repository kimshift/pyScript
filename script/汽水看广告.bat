@REM qishui music auto ad-watch: run / stop with Ctrl+C
@echo off
chcp 65001 >nul
title qishui_auto
cd /d "%~dp0.."
mise run qs:run
echo.
pause
