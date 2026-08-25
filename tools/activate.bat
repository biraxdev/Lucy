@echo off
set "tools=%~dp0"
set "PATH=%tools%python312;%tools%python312\Scripts;%tools%node20;%tools%redis;%PATH%"
echo Lucy portable runtime activated.
"%tools%python312\python.exe" --version
"%tools%node20\node.exe" --version
"%tools%redis\redis-server.exe" --version
