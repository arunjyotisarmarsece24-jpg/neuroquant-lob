@echo off
cd /d "%~dp0"
title NEUROQUANT-LOB: REST API Healthcheck Inspector
python check_api.py
echo.
pause
