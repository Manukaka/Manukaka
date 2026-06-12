@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
rem Everything is cached locally after setup — force offline mode
set HF_HUB_OFFLINE=1
python -m assistant.app
pause
