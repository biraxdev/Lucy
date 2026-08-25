#!/usr/bin/env pwsh
# Portable runtime setup for Project Lucy (Python 3.12, Node 20, Redis 5)
# Downloads self-contained binaries into tools/ so no system installation is required.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$tools = $PSScriptRoot
$tmp = Join-Path $tools "tmp"

$packages = @(
    @{
        name = "python312"
        url = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
        archive = "python-3.12.7-embed-amd64.zip"
        dir = Join-Path $tools "python312"
    },
    @{
        name = "node20"
        url = "https://nodejs.org/dist/v20.18.1/node-v20.18.1-win-x64.zip"
        archive = "node-v20.18.1-win-x64.zip"
        dir = Join-Path $tools "node20"
    },
    @{
        name = "redis50"
        url = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
        archive = "Redis-x64-5.0.14.1.zip"
        dir = Join-Path $tools "redis"
    }
)

function New-DirectoryIfMissing($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

function Save-RemoteFile($url, $dest) {
    if (Test-Path $dest) {
        Write-Host "Found cached $dest"
        return
    }
    Write-Host "Downloading $url ..."
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}

New-DirectoryIfMissing $tmp

foreach ($pkg in $packages) {
    New-DirectoryIfMissing $pkg.dir
    $archivePath = Join-Path $tmp $pkg.archive
    Save-RemoteFile $pkg.url $archivePath

    Write-Host "Extracting $($pkg.archive) ..."
    Expand-Archive -Path $archivePath -DestinationPath $pkg.dir -Force

    # Remove archive to save space
    Remove-Item $archivePath -Force

    # Flatten Node.js nested directory (e.g. node-v20.x-win-x64/... -> node20/...)
    if ($pkg.name -eq "node20") {
        $nested = Get-ChildItem -Path $pkg.dir -Directory | Where-Object { $_.Name -like "node-v*" } | Select-Object -First 1
        if ($nested) {
            Get-ChildItem -Path $nested.FullName | Move-Item -Destination $pkg.dir -Force
            Remove-Item $nested.FullName -Recurse -Force
        }
    }
}

# Configure portable Python for pip + site-packages
$pthFile = Get-ChildItem -Path (Join-Path $tools "python312") -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    $pth = $pthFile.FullName
    $content = Get-Content $pth
    $content = $content | ForEach-Object {
        if ($_ -match "^#import site") { "import site" }
        else { $_ }
    }
    if (-not ($content -contains "Lib\site-packages")) {
        $content = @("python312.zip", ".", "Lib\site-packages") + ($content | Where-Object { $_ -notin @("python312.zip", ".") })
    }
    Set-Content $pth ($content -join "`r`n") -Force
}

$pythonExe = Join-Path $tools "python312\python.exe"
New-DirectoryIfMissing (Join-Path $tools "python312\Lib\site-packages")

# Install pip
$getPip = Join-Path $tmp "get-pip.py"
Save-RemoteFile "https://bootstrap.pypa.io/get-pip.py" $getPip
& $pythonExe $getPip --no-warn-script-location
Remove-Item $getPip -Force

# Install build tools so source distributions can be built
& $pythonExe -m pip install setuptools wheel --no-warn-script-location

# Create convenience scripts
$activatePs1 = @"
# Portable environment activation for Project Lucy
`$tools = `$PSScriptRoot
`$env:PATH = "`$tools\python312;`$tools\python312\Scripts;`$tools\node20;`$tools\redis;`$env:PATH"
Write-Host "Lucy portable runtime activated." -ForegroundColor Green
& "`$tools\python312\python.exe" --version
& "`$tools\node20\node.exe" --version
& "`$tools\redis\redis-server.exe" --version
"@

$activateBat = @"
@echo off
set "tools=%~dp0"
set "PATH=%tools%python312;%tools%python312\Scripts;%tools%node20;%tools%redis;%PATH%"
echo Lucy portable runtime activated.
"%tools%python312\python.exe" --version
"%tools%node20\node.exe" --version
"%tools%redis\redis-server.exe" --version
"@

$startRedis = @"
@echo off
"%~dp0redis\redis-server.exe" --port 6379
"@

$stopRedis = @"
@echo off
"%~dp0redis\redis-cli.exe" -p 6379 shutdown nosave
"@

$installDeps = @"
@echo off
set "tools=%~dp0"
set "PATH=%tools%python312;%tools%python312\Scripts;%tools%node20;%PATH%"
cd /d "%tools%..\backend"
python -m pip install -r requirements.txt
cd /d "%tools%..\frontend"
npm install
"@

Set-Content (Join-Path $tools "activate.ps1") $activatePs1 -Force
Set-Content (Join-Path $tools "activate.bat") $activateBat -Force
Set-Content (Join-Path $tools "start-redis.bat") $startRedis -Force
Set-Content (Join-Path $tools "stop-redis.bat") $stopRedis -Force
Set-Content (Join-Path $tools "install-deps.bat") $installDeps -Force

# Clean up tmp
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }

Write-Host "`nPortable runtime setup complete." -ForegroundColor Green
Write-Host "Activate:   .\tools\activate.ps1" -ForegroundColor Cyan
Write-Host "Start Redis: .\tools\start-redis.bat" -ForegroundColor Cyan
Write-Host "Install deps: .\tools\install-deps.bat" -ForegroundColor Cyan
