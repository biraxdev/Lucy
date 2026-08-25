# Portable environment activation for Project Lucy
$tools = $PSScriptRoot
$env:PATH = "$tools\python312;$tools\python312\Scripts;$tools\node20;$tools\redis;$env:PATH"
Write-Host "Lucy portable runtime activated." -ForegroundColor Green
& "$tools\python312\python.exe" --version
& "$tools\node20\node.exe" --version
& "$tools\redis\redis-server.exe" --version
