$ErrorActionPreference = 'Continue'
$body = '{"username":"admin","password":"admin"}'
$resp = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method Post -Body $body -ContentType 'application/json'
$tok = $resp.access_token
$rtok = $resp.refresh_token
$aid = 'baa3576f-4a28-45db-bc2e-91fceb3466c6'

$ok = 0; $fail = 0; $failed = @()

function T($name, $method, $ep, $body) {
    $headers = @{Authorization="Bearer $tok"; 'Content-Type'='application/json'}
    try {
        $params = @{Uri = "http://localhost:8000$ep"; Method = $method; Headers = $headers; TimeoutSec = 15}
        if ($body) { $params.Body = $body }
        $r = Invoke-WebRequest @params
        Write-Output "OK  $name"
        $script:ok++
    } catch {
        $code = ''
        if ($_.Exception.Response) { $code = $_.Exception.Response.StatusCode.value__ }
        Write-Output "FAIL $name => $code"
        $script:fail++
        $script:failed += "$name => $code"
    }
}

# GET endpoints
$gets = @(
    '/api/v1/agents', "/api/v1/agents/$aid", '/api/v1/tasks?limit=50',
    "/api/v1/tasks?agent_id=$aid", '/api/v1/modules', '/api/v1/groups',
    '/api/v1/groups/summaries/all', '/api/v1/timelines', '/api/v1/pocs',
    '/api/v1/credentials', '/api/v1/findings', '/api/v1/alerts',
    '/api/v1/defense/status', '/api/v1/defense/rules', '/api/v1/defense/alerts',
    '/api/v1/defense/scanners', '/api/v1/defense/mitre-map', '/api/v1/defense/events?limit=5',
    '/api/v1/rbac/roles', '/api/v1/rbac/permissions', '/api/v1/rbac/matrix',
    '/api/v1/rbac/users', '/api/v1/rbac/me', '/api/v1/monitor',
    '/api/v1/build-packs', '/api/v1/strategy/tactics', '/api/v1/strategy/techniques',
    '/api/v1/strategy/campaigns', '/api/v1/strategy/playbooks', '/api/v1/strategy/notes',
    '/api/v1/reports', '/api/v1/chat/history?limit=5', '/api/v1/operators/online',
    '/api/v1/ai-agent/status', '/api/v1/ai-chat/status', '/api/v1/ai-agent/context',
    '/api/v1/logs?limit=5', '/api/v1/auth/me', '/health'
)
foreach ($ep in $gets) { T "GET $ep" 'GET' $ep }

# POST tasks
$modules = @(
    @('shell','exec','{"cmd":"whoami"}'),
    @('screenshot','capture','{}'),
    @('file','list','{"path":"."}'),
    @('port_scan','scan','{"host":"127.0.0.1","ports":[22,80,443]}'),
    @('clipboard','capture','{}'),
    @('persistence','check','{}'),
    @('keylog','start','{}'),
    @('wifi','scan','{}'),
    @('info','collect','{}'),
    @('process','list','{}')
)
foreach ($m in $modules) {
    $tb = "{`"agent_id`":`"$aid`",`"module`":`"$($m[0])`",`"action`":`"$($m[1])`",`"params`":$($m[2]),`"priority`":`"normal`"}"
    T "POST task $($m[0])/$($m[1])" 'POST' '/api/v1/tasks' $tb
}

# AI Agent
T 'POST AI analyze-threat' 'POST' '/api/v1/ai-agent/analyze-threat' '{"query":"test"}'
T 'POST AI suggest-steps' 'POST' '/api/v1/ai-agent/suggest-steps' '{"current_state":{}}'
T 'POST AI analyze-results' 'POST' '/api/v1/ai-agent/analyze-results' '{"task_results":[]}'
T 'POST AI generate-script' 'POST' '/api/v1/ai-agent/generate-script' '{"task_description":"hello","language":"python"}'

# Chat
T 'POST Chat command' 'POST' '/api/v1/chat/command' '{"message":"list agents"}'

# Defense
T 'POST Defense event' 'POST' '/api/v1/defense/events' '{"source":"sensor","hostname":"FBOX","event_type":"test","details":{},"severity":"info"}'
T 'POST Defense bulk' 'POST' '/api/v1/defense/events/bulk' '{"events":[{"source":"sensor","hostname":"FBOX","event_type":"proc","details":{},"severity":"info"}]}'
T 'POST Defense scanner' 'POST' '/api/v1/defense/scanners/dispatch' "{`"agent_id`":`"$aid`",`"scanner`":`"port_scan`"}"

# Strategy
T 'POST Strategy tactic' 'POST' '/api/v1/strategy/tactics' '{"mitre_id":"TA9999","name":"Test Tactic","phase":"test","description":"test"}'
T 'POST Strategy technique' 'POST' '/api/v1/strategy/techniques' '{"mitre_id":"T9999","name":"Test Tech","description":"test","platform":"all"}'
T 'POST Strategy campaign' 'POST' '/api/v1/strategy/campaigns' '{"name":"Test Campaign","description":"test","objective":"test","status":"active"}'
T 'POST Strategy playbook' 'POST' '/api/v1/strategy/playbooks' '{"name":"Test PB","description":"test","steps":[],"tags":["test"]}'
T 'POST Strategy note' 'POST' '/api/v1/strategy/notes' "{`"agent_id`":`"$aid`",`"content`":`"Test note`",`"category`":`"observation`"}"

# Findings, Reports, Groups
T 'POST Finding' 'POST' '/api/v1/findings' '{"title":"Test Finding","severity":"medium","status":"draft","description":"test"}'
T 'POST Report' 'POST' '/api/v1/reports' '{"title":"Test Report","format":"json","scope":"all"}'
T 'POST Group' 'POST' '/api/v1/groups' '{"name":"Test Group","description":"test"}'

# Auth
T 'POST Auth refresh' 'POST' '/api/v1/auth/refresh' "{`"refresh_token`":`"$rtok`"}"
T 'POST Auth change-password' 'POST' '/api/v1/auth/change-password' '{"current_password":"admin","new_password":"admin"}'

# Timeline
T 'POST Timeline create' 'POST' '/api/v1/timelines' '{"name":"Test TL","description":"test","steps":[]}'

# PoC import (puid)
$headers2 = @{Authorization="Bearer $tok"; 'Content-Type'='application/json'}
$pocs = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/pocs' -Method Get -Headers $headers2 -TimeoutSec 10
if ($pocs -and $pocs.Count -gt 0 -and $pocs[0].puid) {
    T 'POST PoC import' 'POST' "/api/v1/pocs/$($pocs[0].puid)/import"
}

# Build
T 'POST Build agent' 'POST' '/api/v1/build' "{`"os`":`"windows`",`"arch`":`"x64`",`"modules`":[`"shell`",`"file`",`"screenshot`"],`"server_url`":`"http://localhost:8000`",`"api_key`":`"test`"}"

# GraphQL
T 'POST GraphQL' 'POST' '/graphql' '{"query":"{ agents { id hostname status } }"}'

# PUT RBAC user
$users = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/rbac/users' -Method Get -Headers $headers2 -TimeoutSec 10
if ($users -and $users.Count -gt 0) {
    T 'PUT RBAC user' 'PUT' "/api/v1/rbac/users/$($users[0].id)" '{"role":"admin"}'
}

# Module download (no auth)
T 'GET Module download' 'GET' '/api/v1/modules/shell/download'

# Summary
Write-Output "`n========================================"
Write-Output "TOTAL: $($ok+$fail) | OK: $ok | FAIL: $fail"
Write-Output "========================================"
if ($fail -gt 0) {
    Write-Output "FAILED:"
    $failed | ForEach-Object { Write-Output "  $_" }
}
