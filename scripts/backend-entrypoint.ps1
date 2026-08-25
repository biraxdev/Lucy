# Backend entrypoint for Windows local development.
# Run from the project root or any location; it moves to the backend directory first.
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path -Path $projectRoot -ChildPath "backend"

Set-Location -Path $backendDir
python main.py
