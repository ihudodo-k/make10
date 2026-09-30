@echo off
rem Make10: serve docs/ to phones on the same Wi-Fi (see serve_lan.py).
rem Double-click to start. Press Ctrl+C in this window to stop.
rem This file is kept ASCII-only so cmd.exe reads it correctly in any code page.
cd /d "%~dp0"
python serve_lan.py
echo.
pause
