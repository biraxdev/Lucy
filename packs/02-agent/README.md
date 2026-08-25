# Pack 2 — L'Agent & Modules (Bras Armé)

Le soldat sur le terrain. L'agent est le "corps", les modules sont ses "outils". Un implant Python léger, standalone, qui se connecte au C2 et télécharge ses modules à la volée.

## Contenu

- `agent/agent.py` — Boucle principale (config, handshake, heartbeat, task loop)
- `agent/config.py` — Configuration baked au build (C2 URL, API key, heartbeat, stealth)
- `agent/main.py` — Entry point PyInstaller
- `agent/core/crypto.py` — Miroir backend crypto (ECDH, AES-256-GCM, HKDF)
- `agent/core/loader.py` — Téléchargement module + vérification HMAC + exec
- `agent/core/stealth.py` — Anti-sandbox, anti-debug, VM checks
- `agent/core/offline_queue.py` — Buffer tâches quand déconnecté
- `agent/core/dns_beacon.py` — Fallback DNS beacon
- `agent/core/malleable.py` — C2 profiles malleables
- `agent/core/smb_pipe.py` — Fallback SMB pipe
- `agent/core/tcp_beacon.py` — Fallback TCP beacon
- `agent/modules/` — 31 modules (builtin, shell, screenshot, keylog, browser, clipboard, edr_evasion, injection, kerberoast, lateral, macos, persistence, pivoting, port_scan, pth, remote_control, screen_stream, sleep_mask, stack_spoof, syscalls, tls_fingerprint, token, uac_bypass, webcam, wifi, etc.)
- `agent/tests/` — Tests unitaires (anti_analysis, offline_queue, stealth)
- `agent/payloads/config_template.ini` — Template config agent
- `build.bat` / `build.ps1` — Scripts PyInstaller Windows

## Démarrage rapide

```bash
cd agent
python agent.py                    # Mode développement
# ou
pyinstaller main.py --onefile --noconsole --name lucy_agent  # Mode production
```

## Module DIY

Voir `MODULE_DIY.md` pour créer un nouveau module compatible.
