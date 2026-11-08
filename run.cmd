@echo off
cd /d "%~dp0"
start "" /b uv run --quiet pythonw -m mstsc_manager
