@echo off
cd /d "D:\COGU AGENT\cogu_agent"
set PYTHONPATH=D:\COGU AGENT\cogu_agent
start /b python -c "import sys; sys.path.insert(0, r'D:\COGU AGENT\cogu_agent'); from cogu.desktop.loong import _get_or_create_app; import uvicorn; app = _get_or_create_app(); uvicorn.run(app, host='127.0.0.1', port=8198, log_level='warning')"