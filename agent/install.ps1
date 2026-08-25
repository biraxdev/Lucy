# Lucy Agent — installateur persistant Windows
# Build un .exe depuis Lucy et l'installe en service Windows.

param(
    [string]$LucyBase = "http://localhost:8000",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [string]$Pack = "recon",
    [string]$InstallDir = "C:\ProgramData\Lucy",
    [string]$ServiceName = "LucyAgent"
)

$ErrorActionPreference = "Stop"

function Invoke-LucyApi {
    param($Method, $Uri, $Body, $Token)
    $headers = @{ Authorization = "Bearer $Token" }
    if ($Body) {
        $headers["Content-Type"] = "application/json"
        $resp = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $headers -Body $Body
    } else {
        $resp = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $headers
    }
    return $resp
}

# 1. Login
$login = @{ username = $Username; password = $Password } | ConvertTo-Json -Compress
$token = (Invoke-RestMethod -Uri "$LucyBase/api/v1/auth/login" -Method POST -ContentType "application/json" -Body $login).access_token
Write-Host "Authentifié"

# 2. Récupérer la clé API opérateur
$apiKey = (Invoke-LucyApi -Method GET -Uri "$LucyBase/api/v1/auth/api-key" -Token $token).api_key
Write-Host "Clé API obtenue"

# 3. Charger le pack
$pack = Invoke-LucyApi -Method GET -Uri "$LucyBase/api/v1/build-packs/$Pack" -Token $token
Write-Output "pack type = $($pack.GetType().FullName)"
Write-Output "pack raw = $pack"
$modules = $pack.modules
if ($modules -is [string]) { $modules = $modules | ConvertFrom-Json }
$buildOptions = $pack.build_options
if ($buildOptions -is [string]) { $buildOptions = $buildOptions | ConvertFrom-Json }
Write-Host "Pack chargé : $($pack.name) ($($modules.Count) modules)"

# 4. Build EXE
$buildBody = @{
    os = "windows"
    arch = "x64"
    modules = $modules
    server_url = $LucyBase
    api_key = $apiKey
    transport = "websocket"
}
foreach ($k in $buildOptions.PSObject.Properties.Name) {
    $buildBody[$k] = $buildOptions.$k
}
$buildJson = $buildBody | ConvertTo-Json -Compress

$build = Invoke-LucyApi -Method POST -Uri "$LucyBase/api/v1/build" -Body $buildJson -Token $token
$buildId = $build.build_id
Write-Host "Build démarré : $buildId"

# 5. Attendre la fin du build
do {
    Start-Sleep -Seconds 5
    $status = Invoke-LucyApi -Method GET -Uri "$LucyBase/api/v1/build/$buildId" -Token $token
    Write-Host "  $($status.stage) - $($status.stage_message)"
} while ($status.stage -ne "done" -and $status.stage -ne "failed")

if ($status.stage -eq "failed") {
    throw "Build échoué : $($status.stage_message)"
}

# 6. Télécharger
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$exePath = Join-Path $InstallDir "lucy_agent.exe"
Invoke-WebRequest -Uri "$LucyBase/api/v1/build/$buildId/download" -OutFile $exePath -Headers @{ Authorization = "Bearer $token" }
Write-Host "EXE téléchargé : $exePath"

# 7. Installer / mettre à jour le service
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
}
New-Service -Name $ServiceName -BinaryPathName "`"$exePath`"" -DisplayName "Lucy Agent" -StartupType Automatic
Start-Service -Name $ServiceName
Write-Host "Service $ServiceName installé et démarré"
