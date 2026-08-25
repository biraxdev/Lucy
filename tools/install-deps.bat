@echo off
set "tools=%~dp0"
set "PATH=%tools%python312;%tools%python312\Scripts;%tools%node20;%PATH%"
cd /d "%tools%..\backend"
python -m pip install setuptools wheel --no-warn-script-location
python -m pip install -r requirements.txt
cd /d "%tools%..\frontend"
npm install
