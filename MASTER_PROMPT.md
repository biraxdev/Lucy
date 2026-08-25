Prompt 1 — Structure globale et stack technique



Tu es un architecte software. Conçois la structure complète du projet "Lucy" — un Remote Agent Testing System (RATS) modulaire pour simulations Red Team autorisées.

Stack :
- Backend : Python 3.12 + FastAPI + WebSockets + SQLite (peewee ORM)
- Frontend : React 18 + TypeScript + TailwindCSS + Zustand (state) + Socket.IO client
- Agent (implant) : Python pur (standalone .py) avec fallback C pour modules critiques
- Build : Docker Compose (backend + frontend) + PyInstaller pour agent compilé
- Auth : JWT + API key rotation
- Crypto : AES-256-GCM (messages) + ECDH (key exchange)

Structure de dossiers :
/backend /core — orchestration, auth, crypto /api — endpoints REST + WS /modules — plugins téléchargeables (screenshot, keylog, file, shell, etc.) /agents — gestion des implants connectés /db — migrations, models /tasks — job queue asynchrone /frontend /src /pages — Dashboard, AgentView, ModuleStore, Timeline /components — UI atomique (DataTable, LogFeed, Terminal, Map) /stores — Zustand stores (agents, tasks, ui) /api — client API + socket /types — TypeScript interfaces /agent /core — heartbeat, crypto, module loader /modules — mêmes signatures que backend /payloads — templates pour builds custom





Génère le fichier `project-lucy-structure.md` avec schémas entité-relation et descriptions de chaque module.


Prompt 2 — Initialisation du backend FastAPI



Initialise le backend FastAPI pour Project Lucy.

Exigences techniques :
- Python 3.12, virtualenv, requirements.txt (fastapi, uvicorn, websockets, peewee, pycryptodome, pydantic, python-jose, httpx, celery)
- Application factory pattern
- Middleware : CORS (origin: frontend), Auth JWT, Request logging structuré
- Startup event : migration DB auto, seed admin user
- Lifespan handler propre (startup/shutdown)

Point d'entrée : `backend/main.py` avec structure asynchrone.

Le système doit supporter :
- WebSocket authentifié par token (query param)
- REST API versionnée (/api/v1/agents, /api/v1/tasks, /api/v1/modules)
- Health endpoint non-authentifié (/health)

Génère tous les fichiers : main.py, dependencies.py, config.py, middleware.py, database.py. Assure-toi que l'import fonctionne avec `from core import ...`.
Prompt 3 — Modèles de données et ORM (Peewee)



Crée les modèles SQLite via Peewee pour Project Lucy.

Tables requises :

1. Agent
   - id (UUID primary), hostname, os, username, ip_public, ip_private
   - architecture, processor, ram_total, ram_available
   - first_seen, last_seen, status (online/idle/offline/compromised)
   - public_key (pour ECDH), aes_key (chiffré)
   - group_id (FK), tags (JSON)

2. Task
   - id (UUID), agent_id (FK), module (str), action (str)
   - params (JSON), status (queued/running/completed/failed)
   - result (JSON blob), error (text), created_at, executed_at

3. Module
   - id, name, version, description, author
   - code (text — script téléchargeable par l'agent)
   - dependencies (JSON), os_compat (JSON array)
   - signature (HMAC-SHA256), enabled (bool)

4. Credential
   - id, agent_id (FK), url/hostname, username, password (AES encrypted)
   - source (browser/wifi/ssh/rdp), captured_at

5. FileEvent
   - id, agent_id (FK), path, action (upload/download/delete/modify)
   - size, hash (SHA256), timestamp

6. Log
   - id, agent_id (FK nullable), level, module, message, timestamp

7. User (admin panel)
   - id, username, password_hash, role (admin/operator/viewer)
   - api_key, last_login

Méthodes sur AgentModel :
   - def encrypt_for_agent(self, plaintext: bytes) -> bytes
   - def decrypt_from_agent(self, ciphertext: bytes) -> bytes

Génère : backend/db/models.py et backend/db/migrations/001_initial.py
Prompt 4 — Authentification JWT + API Key



Implémente le système d'authentification pour Project Lucy.

Backend requis :
1. POST /api/v1/auth/login — username/password → JWT (access + refresh)
2. POST /api/v1/auth/refresh — refresh token → new access token
3. GET /api/v1/auth/me — current user info
4. Tous les endpoints protégés sauf /health et /api/v1/auth/login

Détails techniques :
- Access token : durée 30 min, payload = {sub: user_id, role, scope}
- Refresh token : durée 7 jours, stocké en DB (rotation possible)
- API Key alternative : header X-API-Key, vérifié côté middleware
- Rate limiting : 100 req/min par IP, 1000 req/min par API key
- Password hashing : bcrypt (passlib)
- Middleware : extrait Bearer token, injecte request.user

Génère : backend/api/auth.py, backend/core/auth.py, tests/test_auth.py
Prompt 5 — WebSocket Manager pour communication temps réel



Crée le WebSocket Manager central pour Project Lucy.

Fonctionnalités :
- Connexion authentifiée via token JWT en query param (ws://host/ws?token=xxx)
- Chaque agent a son propre channel (agent:{agent_id})
- Le panel frontend subscribe aux channels qu'il surveille
- Messages format JSON avec champ "type" :
  - type: "heartbeat" | "task" | "result" | "log" | "module_request" | "error"
  - payload: dict
  - timestamp: ISO8601
  - signature: HMAC-SHA256(payload, session_key)

Classes :
- ConnectionManager : singleton, gère {agent_id: WebSocket}
- AgentConnection : wrapper autour d'un websocket avec heartbeat timeout (30s)
- MessageRouter : achemine les messages vers les bons handlers

Le manager doit supporter :
- Envoi broadcast à tous les agents d'un groupe
- File d'attente pour les agents offline (tasks stockées, flush à la reconnexion)
- Commande "ping/pong" keepalive automatique

Génère : backend/core/ws_manager.py, backend/api/ws.py
Prompt 6 — Agent implant (core)



Développe l'implant agent Python standalone pour Project Lucy.

L'agent est un script Python unique (agent/agent.py) qui s'exécute sans dépendances externes (stdlib uniquement pour compatibilité).

Boucle principale (agentic loop) :

1. Démarrage :
   - Parse config (hardcodée ou fichier .ini chiffré)
   - Vérifie anti-sandbox basique (ram < 2GB, screen < 1024x768, debugger present)
   - Génère paire de clés ECDH (ecdsa lib intégrée)
   - Collecte hostname, os, username, ip, ram, processes

2. Handshake :
   - GET /api/v1/agents/register → envoie infos + clé publique
   - Reçoit clé publique serveur, dérive AES-256-GCM shared key
   - Stocke la clé en mémoire (pas de disk)

3. Heartbeat loop (toutes les 15-30s random) :
   - WebSocket ou HTTP polling (selon config)
   - Envoie {type: "heartbeat", agent_id, cpu, ram, status}
   - Reçoit éventuellement une Task

4. Task execution :
   - Reçoit {task_id, module, action, params}
   - Charge module depuis cache ou télécharge
   - Exécute dans un thread séparé (timeout 60s)
   - Envoie result {task_id, status, data}

Modules embarqués minimaux (built-in) :
   - shell : execute cmd (os.popen)
   - file : read/write/list/upload/download
   - screenshot : PIL ou fallback MSS
   - keylog : pynput ou fallback lecture /dev/input
   - info : system info détaillée

L'agent ne doit écrire aucun fichier sur le disque sauf instruction explicite (file.write). Tout est en mémoire.

Génère : agent/agent.py, agent/modules/builtin.py, agent/core/crypto.py
Prompt 7 — Crypto layer complet (ECDH + AES-GCM)



Implémente la couche cryptographique complète pour Project Lucy.

Algorithme de key exchange :
1. Agent génère ECDH keypair (curve P-256)
2. Agent envoie sa clé publique au serveur (handshake)
3. Serveur génère son propre keypair, dérive shared secret
4. Serveur répond avec sa clé publique + nonce chiffré (proof)
5. Agent dérive le même shared secret, vérifie nonce
6. Dérivation : HKDF(shared_secret, salt=nonce, info="lucy-aes-key") → 32 bytes AES key

Chiffrement messages :
- AES-256-GCM avec nonce aléatoire (12 bytes) + tag (16 bytes)
- Format : base64(nonce + ciphertext + tag)
- Chaque message a son propre nonce

Fonctions à implémenter :

```python
def generate_keypair() -> tuple[bytes, bytes]:
    """(private_key_pem, public_key_pem)"""

def derive_shared_secret(private_key: bytes, peer_public_key: bytes) -> bytes:
    """Returns raw shared secret (32 bytes)"""

def derive_aes_key(shared_secret: bytes, salt: bytes = b"lucy") -> bytes:
    """HKDF expansion → 32 bytes"""

def encrypt(plaintext: bytes, aes_key: bytes) -> str:
    """Returns base64(nonce + cipher + tag)"""

def decrypt(cipher_b64: str, aes_key: bytes) -> bytes:
    """Returns plaintext"""

def sign_message(payload: bytes, hmac_key: bytes) -> str:
    """HMAC-SHA256"""

def verify_signature(payload: bytes, signature: str, hmac_key: bytes) -> bool:
Génère : backend/core/crypto.py et agent/core/crypto.py (doivent être compatibles, mêmes paramètres)





---

## Prompt 8 — Module system (plugin architecture)

Conçois le système de plugins modulaires pour Project Lucy.

Principe : modules téléchargeables par l'agent, exécutés à chaud.

Structure d'un module :

python



class Module(BaseModule):
    name = "screenshot"
    version = "1.0.0"
    dependencies = ["Pillow>=10.0"]  # pip packages
    os_compat = ["windows", "linux", "darwin"]
    
    async def run(self, params: dict) -> dict:
        # params contient : quality, format, region
        # retourne dict avec result, ou raises ModuleError
        ...
Backend API pour modules :

POST /api/v1/modules — upload new module (code + metadata)
GET /api/v1/modules — list available
GET /api/v1/modules/{id}/download — raw code (HMAC signed)
DELETE /api/v1/modules/{id} — remove (admin only)
Agent module loader :

Modules stockés en mémoire (dict)
Import dynamique : exec(compile(code, '<module>', 'exec'), namespace)
Sandboxing basique : timeout, restricted builtins (optionnel)
Cache : stocké en mémoire, invalidé si version mismatch
Modules à développer (livrés avec le projet) :

screenshot — capture écran (PIL)
keylog — keylogging avec buffer circulaire
file_manager — explore, upload, download, delete
shell — shell interactif (thread séparé)
process — list, kill, inject
wifi — scan réseaux, récupération mots de passe (nmap)
browser — dump cookies/history (sqlite)
persistence — install dans startup/cron
geoip — localisation via IP
webcam — capture caméra (OpenCV)
Génère : backend/core/module_manager.py, agent/core/loader.py, backend/api/modules.py, et les 10 modules dans /modules/





---

## Prompt 9 — Timeline et orchestration de tâches

Implémente le système de timeline et d'orchestration pour Project Lucy.

Une timeline est une séquence ordonnée de tâches planifiées.

Structure Timeline (stockée DB) :

json



{
  "id": "uuid",
  "name": "Reconnaissance initiale",
  "description": "Phase 1 - collecte système",
  "agent_group": ["all"],
  "steps": [
    {"order": 1, "module": "info", "params": {}, "delay": 0},
    {"order": 2, "module": "wifi", "params": {}, "delay": 5},
    {"order": 3, "module": "browser", "params": {"depth": "full"}, "delay": 2},
    {"order": 4, "module": "file_manager", 
     "params": {"action": "tree", "path": "C:\\Users"}, 
     "delay": 3}
  ],
  "trigger": "manual | on_connect | schedule(cron)",
  "loop": false | 3600,
  "status": "draft | active | completed | failed"
}
API :

POST /api/v1/timelines — create
GET /api/v1/timelines — list
POST /api/v1/timelines/{id}/execute — run now
PUT /api/v1/timelines/{id} — update
DELETE /api/v1/timelines/{id} — delete
Orchestrateur (agent loop amélioré) : À chaque heartbeat, l'agent check :

Any pending task in queue → exécute
Any active timeline with my group → pull next step
Any scheduled trigger → push task
Le backend gère la file d'attente globale et priorise les tâches (CRITICAL > HIGH > NORMAL > LOW).

Génère : backend/api/timelines.py, backend/core/orchestrator.py, avec tests.





---

## Prompt 10 — Frontend React — Setup et architecture

Initialise le frontend React pour Project Lucy.

Stack exacte :

React 18 + TypeScript + Vite
TailwindCSS v4 avec DaisyUI
Zustand (state management)
Socket.IO client (connexion WebSocket)
React Router v7
React Query (TanStack Query v5) pour les appels API
Recharts pour graphiques
Monaco Editor pour éditeur de modules
Leaflet pour cartographie des agents
Structure :




frontend/
  src/
    main.tsx
    App.tsx
    routes.tsx
    api/
      client.ts       — Axios instance + interceptors
      auth.ts         — login, refresh, me
      agents.ts       — CRUD agents
      tasks.ts        — tasks + timelines
      modules.ts      — module store
    stores/
      authStore.ts    — user session
      agentStore.ts   — liste agents + selected
      taskStore.ts    — task queue active
      uiStore.ts      — sidebar, theme, modals
    pages/
      Dashboard.tsx
      Agents.tsx
      AgentDetail.tsx
      ModuleStore.tsx
      TimelineBuilder.tsx
      Settings.tsx
      Login.tsx
    components/
      Layout.tsx, Sidebar.tsx, Navbar.tsx
      AgentCard.tsx, AgentTable.tsx
      TaskTimeline.tsx, TaskQueue.tsx
      LogViewer.tsx
      Terminal.tsx
      MapView.tsx
      CodeEditor.tsx
      FileExplorer.tsx
    hooks/
      useWebSocket.ts
      useAgents.ts
      useTasks.ts
    types/
      agent.ts, task.ts, module.ts, user.ts
    styles/
      globals.css
Génère le projet Vite complet avec tsconfig, vite.config.ts, tailwind.config.js, et le App.tsx routé.





---

## Prompt 11 — Frontend — Dashboard principal

Crée le Dashboard principal de Project Lucy.

Composants à intégrer :

Statistiques globales (4 cartes en haut) :
Agents connectés / total / offline
Tâches en file d'attente / exécutées / échouées
Credentials collectés (total)
Modules installés
Graphiques Recharts :
Ligne : Connexions agents (24h)
Barre : Tâches par module (top 5)
Pie : Distribution OS des agents
Feed d'activité en temps réel (flux WebSocket) :
Dernières actions (agent connecté, tâche complétée, credential trouvé)
Scroll infini, auto-update via socket
Quick actions :
Bouton "Exécuter recon rapide" → lance timeline prédéfinie
Bouton "Broadcast shell" → ouvre terminal multi-agent
Bouton "Refresh all agents"
Mini-map leaflet :
Marqueurs pour chaque agent (géolocalisation IP)
Clustering automatique si > 50 agents
Click → AgentDetail
Le dashboard doit être réactif (responsive) et fonctionner en temps réel via WebSocket.

Génère : frontend/src/pages/Dashboard.tsx + tous les sous-composants importés.





---

## Prompt 12 — Frontend — Vue Agent détaillée

Crée la page AgentDetail pour Project Lucy.

Affichage :

Header : hostname, OS, IP, statut (badge coloré), uptime
Tabs :
Info : CPU, RAM, disque, processus, logiciels installés
Tasks : historique des tâches exécutées (tableau avec filtre)
Files : explorateur de fichiers arborescent (TreeView) avec actions upload/download
Credentials : tableau des credentials collectés (avec reveal password bouton)
Timeline : timeline temps réel des actions (gantt-like)
Terminal : shell interactif via WebSocket
Modules : modules chargés sur cet agent
Actions rapides :
Exécuter module (dropdown selecteur)
Upload file
Send command shell
Démarrer keylog
Screenshot now
Kill agent (desktop)
Logs en temps réel :
Flux streamé par WebSocket
Filtrable par niveau (info/warn/error/debug)
Export CSV
Le composant utilise AgentDetailStore (Zustand) et se met à jour via socket events.

Génère : frontend/src/pages/AgentDetail.tsx + composants : InfoPanel.tsx, FileExplorer.tsx, CredentialTable.tsx, AgentTerminal.tsx, ModuleList.tsx, TaskHistory.tsx





---

## Prompt 13 — Frontend — Timeline Builder (drag & drop)

Crée le Timeline Builder visuel pour Project Lucy.

C'est un constructeur de chaînes d'attaque par glisser-déposer.

Fonctionnalités :

Palette de modules (sidebar gauche) :
Liste tous les modules disponibles avec icônes
Filtre par nom / catégorie (Recon, Exfiltration, Persistence, etc.)
Canvas (centre) :
Drag & drop des modules depuis la palette
Chaque module est un bloc connectable
Connexions : lignes entre blocs (ordre d'exécution)
Chaque bloc a des paramètres configurables (click → modal)
Paramètres : délai avant exécution, timeout, retry count
Timeline line (bas) :
Vue temporelle horizontale
Barres pour chaque étape avec durée estimée
Scroll horizontal (zoom in/out)
Propriétés (sidebar droite) :
Quand un bloc est sélectionné : ses paramètres
Quand la timeline est sélectionnée : nom, description, trigger, loop
Actions :
Save as draft / Save & activate
Execute now (run sur agents sélectionnés)
Export as JSON / YAML
Import JSON
Duplicate timeline
Agent group selector :
Checkbox pour cibler : All / Online / Custom group
Tags: "windows", "linux", "domain_joined", "high_priv"
Utilise react-dnd (drag & drop) et react-flow (connecteurs).

Génère : frontend/src/pages/TimelineBuilder.tsx + tous les sous-composants (BlockNode.tsx, ConnectionLine.tsx, ParamModal.tsx, TimelinePreview.tsx, AgentSelector.tsx)





---

## Prompt 14 — Backend — Agent group management

Implémente la gestion de groupes d'agents pour Project Lucy.

API :

POST /api/v1/groups — create {name, description, tags, dynamic_query?}
GET /api/v1/groups — list
GET /api/v1/groups/{id}/agents — list agents in group
PUT /api/v1/groups/{id} — update
DELETE /api/v1/groups/{id}
Deux types de groupes :

Static : ajout/suppression manuelle d'agents
Dynamic : requête SQL-like qui est évaluée en temps réel Exemple : os = "windows" AND last_seen > NOW() - INTERVAL 1 HOUR Les agents correspondants sont automatiquement membres.
Le group resolver évalue les groupes dynamiques à chaque :

Connexion d'agent
Heartbeat
Déclenchement de timeline
Génère : backend/api/groups.py, backend/core/group_manager.py, tests/test_groups.py





---

## Prompt 15 — Backend — Task queue + Celery worker

Implémente une file d'attente robuste pour Project Lucy.

Architecture :

Celery avec Redis (broker) + SQLite (result backend)
Priorité : CRITICAL (0s), HIGH (5s), NORMAL (30s), LOW (120s)
Timeout par tâche (configurable, défaut 60s)
Retry : max 3 tentatives, backoff exponentiel (1, 3, 9 minutes)
Task types :

agent_task : push une tâche à un agent spécifique
broadcast_task : push à tous les agents d'un groupe
timeline_task : exécute une timeline complète (orchestrée)
cleanup_task : purge les logs > 30 jours, les vieux résultats
health_check : vérifie les agents silencieux, marque offline
API :

GET /api/v1/tasks — liste paginée + filtres (status, agent, module)
GET /api/v1/tasks/{id} — détail
POST /api/v1/tasks — create (passe par Celery)
DELETE /api/v1/tasks/{id} — cancel si queued
GET /api/v1/tasks/queue — file d'attente actuelle
Le frontend reçoit les mises à jour via WebSocket (task queued → running → completed).

Génère : backend/core/task_queue.py, backend/core/celery_app.py, backend/api/tasks.py, backend/celery_worker.py





---

## Prompt 16 — Agent — Module : Keylogger avancé

Développe le module keylogger pour l'agent Project Lucy.

Fonctionnalités :

Capture toutes les frappes clavier (y compris combinaisons spéciales)
Buffer circulaire en mémoire (taille configurable : défaut 5000 events)
Timestamp chaque event (précision ms)
Détection de fenêtre active (changement de focus → tag dans le log)
Modes :
Live : envoie chaque frappe en temps réel (via WebSocket)
Buffer : stocke et envoie par lot toutes les X secondes
On demand : envoie le buffer complet à la demande
Exfiltration intelligente :
Si champ password détecté (input type="password"), ne capture pas (safe mode)
Si fenêtre de messagerie, priorité haute (envoi immédiat)
Anti-détection :
N'appelle pas pynput si disponible → utilise fallback direct (Windows: ctypes GetAsyncKeyState, Linux: /dev/input, macOS: CGEvent)
Désactivable pour environnement de test
Paramètres :

python



{
  "mode": "buffer",
  "buffer_size": 10000,
  "interval": 30,  # envoi toutes les 30s
  "safe_mode": True,
  "track_windows": True
}
Format retour :

json



{
  "task_id": "...",
  "status": "completed",
  "data": {
    "keys": [
      {"key": "H", "timestamp": "...", "window": "Notepad"},
      {"key": "e", "timestamp": "...", "window": "Notepad"},
      ...
    ],
    "total_keystrokes": 150,
    "duration_seconds": 45
  }
}
Génère : agent/modules/keylog.py avec fallbacks OS natifs





---

## Prompt 17 — Agent — Module : Screenshot avec transmission streaming

Développe le module screenshot pour l'agent Project Lucy.

Modes de capture :

Single : une capture unique
Interval : capture toutes les X secondes (stream)
Region : capture une zone spécifique (x, y, width, height)
Active window : capture uniquement la fenêtre active
Compression :

JPEG qualité configurable (1-100, défaut 85)
Résolution max configurable (downscale si nécessaire)
Compression PNG sans perte en option
Transmission :

Single : base64 intégré dans le JSON result
Stream : WebSocket binary frames (MJPEG-like), fragments de 64KB
Chaque frame a un header (8 bytes) : timestamp (4 bytes) + frame_number (4 bytes)
Progressive : envoie d'abord thumbnail (320x240), puis full resolution
Anti-détection :

Capture via PIL.ImageGrab (Python) ou fallback C avec CreateDC (Windows)
Si aucune librairie, tente xwd (X11), screencapture (macOS), ou direct BitBlt (Windows ctypes)
Paramètres :

python



{
  "mode": "single",
  "quality": 85,
  "max_width": 1920,
  "format": "jpeg",
  "region": null,
  "stream": False,
  "stream_interval": 5,
  "stream_duration": 60
}
Génère : agent/modules/screenshot.py + agent/core/stream_buffer.py





---

## Prompt 18 — Agent — Module : Browser credential stealer

Développe le module browser stealer pour l'agent Project Lucy (pentest autorisé).

Cibles :

Chromium-based (Chrome, Edge, Brave, Opera, Vivaldi) :
Lit Local State (master key AES encrypté)
Déchiffre les mots de passe stockés dans Login Data (sqlite)
Extrait cookies, historique, cartes de crédit
Firefox-based (Firefox, Thunderbird) :
Lit logins.json (chiffré avec master password si présent)
Tente logins.sqlite (ancienne version)
Extrait cert9.db pour cookies
Fallback :
Si pas d'accès direct, tente via WMIC / PowerShell (Windows)
Méthode de déchiffrement (Chromium) :




1. Lire "Local State" → extraire "os_crypt.encrypted_key"
2. Déchiffrer avec DPAPI (Windows) / keychain (macOS) / libsecret (Linux)
3. Ouvrir "Login Data" (sqlite) → extraire rows (origin_url, username_value, password_value)
4. Pour chaque password_value : AES-GCM decrypt avec le master key
Exfiltration :

Par lot (tous les credentials en une réponse)
Filtré par domaine (optionnel)
Si trop volumineux, split en plusieurs messages
Paramètres :

python



{
  "target": "all",           # "chrome" | "firefox" | "all"
  "extract_passwords": True,
  "extract_cookies": True,
  "extract_history": False,
  "extract_cc": False,
  "domain_filter": []         # empty = all domains
}
Génère : agent/modules/browser.py + agent/modules/browser/chromium.py + agent/modules/browser/firefox.py





---

## Prompt 19 — Frontend — Terminal interactif multi-agent

Crée un terminal interactif pour Project Lucy qui supporte le broadcast multi-agent.

Fonctionnalités :

Terminal output :
Composant basé sur xterm.js
Support couleur ANSI (via xterm-addon-fit)
Historique des commandes (flèche haut/bas)
Autocomplétion basique (Tab)
Scrollback illimité (bufférisé)
Mode single agent :
Commande tapée → envoyée à l'agent sélectionné
Résultat affiché en temps réel (stdout/stderr stream)
Prompt personnalisé : lucy@hostname $
Mode broadcast :
Barre de sélection : "Target: All / Group: Windows / Custom (checkboxes)"
Commande tapée → envoyée à TOUS les agents sélectionnés
Résultats groupés par agent (tabs ou accordéon)
Option "Merge output" (concatène stdout dans l'ordre d'arrivée)
Mode script :
Champ pour uploader un script (.bat, .sh, .ps1)
Executé sur la cible
Résultat retourné
Commandes spéciales (interprétées par le frontend, pas envoyées) :
/clear — efface le terminal
/agents — liste les cibles actuelles
/group [name] — change de groupe cible
/exit — ferme le terminal
Communication : WebSocket channel terminal:{agent_id} avec stream de bytes.

Génère : frontend/src/components/Terminal.tsx + composants associés (TerminalTabs.tsx, BroadcastSelector.tsx, ScriptUploader.tsx)





---

## Prompt 20 — Backend — Credential harvesting et exfiltration pipeline

Implémente le pipeline de collecte et stockage des credentials pour Project Lucy.

Flux :

Agent exécute un module (browser, wifi, etc.) → credentials trouvés
Résultat envoyé au backend → endpoint POST /api/v1/credentials/bulk
Backend valide/deduplicate :
Hash (url + username) → SHA256
Si hash existe déjà, compare password (si différent, versionné)
Score de confiance : high (direct read), medium (parsed), low (regex guess)
Chiffrement : AES-256-GCM avec clé dérivée du master key admin
Indexation : Elasticsearch optionnel pour recherche full-text
Endpoints API :

POST /api/v1/credentials/bulk — batch insert (utilisé par agent)
GET /api/v1/credentials — liste paginée + filtres (source, domaine, date)
GET /api/v1/credentials/{id} — détail avec password déchiffré
GET /api/v1/credentials/search?q= — recherche texte
DELETE /api/v1/credentials — purge (admin)
GET /api/v1/credentials/export — format CSV/JSON (option chiffré)
Format credential :

json



{
  "id": "uuid",
  "agent_id": "uuid",
  "source": "chrome",
  "url": "https://admin.company.com/login",
  "username": "admin",
  "password_encrypted": "...",
  "confidence": "high",
  "tags": ["domain_admin", "vpn"],
  "captured_at": "ISO8601",
  "version": 2
}
Fonctionnalité bonus : détection de pattern (admin:motsdepasse, root:toor, etc.) avec flag automatique "weak".

Génère : backend/api/credentials.py, backend/core/credential_manager.py, backend/core/crypto_credential.py





---

## Prompt 21 — Agent — Module : Reverse shell interactif (pty)

Développe le module reverse shell interactif pour l'agent Project Lucy.

Architecture :

L'agent établit un tunnel WebSocket vers le backend
Le backend relaye vers le terminal xterm.js du frontend
PTY (pseudo-terminal) émulé côté agent
Détails techniques :

Windows :
Crée un pipe nommé via ctypes
Lance cmd.exe / powershell.exe avec stdin/stdout redirigé
Taille de fenêtre ajustable (rows, cols)
Linux / macOS :
Utilise pty.openpty() ou os.forkpty()
Lance /bin/bash ou /bin/sh
Support SIGINT (Ctrl+C), SIGTSTP (Ctrl+Z)
Communication :
WebSocket frame types :
stdin : input utilisateur (texte ou bytes)
stdout : output shell (stream continu)
resize : redimensionnement terminal (rows, cols)
exit : fermeture du shell
Buffer : 4096 bytes par frame
Encodage : UTF-8 (avec fallback latin-1 pour bytes bruts)
Timeouts :
Inactivité : 15 minutes (auto-close)
Keepalive : ping toutes les 30s
Sécurité (car autorisé en pentest) :
Chiffrement AES-256-GCM (couche crypto existante)
Session unique : un seul shell par task
Paramètres :

python



{
  "shell": "cmd",          # "cmd" | "powershell" | "bash" | "sh"
  "rows": 24,
  "cols": 80,
  "timeout_minutes": 15
}
Génère : agent/modules/shell.py + agent/core/pty_handler.py





---

## Prompt 22 — Frontend — Module Store avec éditeur de code

Crée le Module Store pour Project Lucy — un marketplace interne de plugins.

Fonctionnalités :

Store grid view :
Cartes avec : nom, version, auteur, description, OS compat, tag (installé/nouveau/update)
Filtres : OS, catégorie, installé/seulement
Recherche : full-text sur nom + description
Module detail :
Vue détaillée (clique sur carte)
Code source affiché (Monaco Editor, read-only si pas auteur)
Métadonnées : dépendances, taille, signature HMAC
Boutons : Install, Update, Delete (admin), Download .zip
Code editor (Monaco Editor) :
Si admin : éditable en direct
Syntax highlighting Python
Linting (pylint / pyright inline)
Save → POST /api/v1/modules/{id} (update)
Bouton "Test" → exécute sur un agent sandbox (optionnel)
Versioning : chaque save crée une nouvelle version
Upload new module :
Drag & drop .py file ou code inline
Formulaire métadonnées : name, version, description, dependencies, os_compat
Generate HMAC signature
Publish
Stats :
Nombre d'installations par module
Taux de succès/échec
Temps d'exécution moyen
Le store utilise la palette de composants Shadcn/ui (DaisyUI).

Génère : frontend/src/pages/ModuleStore.tsx + composants : ModuleCard.tsx, CodeEditor.tsx, ModuleDetail.tsx, UploadForm.tsx





---

## Prompt 23 — Backend — Logging et événements centralisés

Implémente le système de logging centralisé pour Project Lucy.

Types de logs :

System logs : backend events (user login, API calls, errors)
Agent logs : heartbeat, connexion, déconnexion, erreurs agent
Task logs : création, exécution, résultat, échec
Module logs : output spécifique des modules
Security logs : tentatives échouées, anomalies, rate limit
Stockage :

SQLite pour les logs récents (7 jours)
Rotation automatique : archive les logs > 7 jours dans des fichiers JSON compressés (.gz)
Optionnel : export Elasticsearch pour recherche avancée
API :

GET /api/v1/logs — liste paginée + filtres (level, module, agent_id, date range)
GET /api/v1/logs/stream — SSE (Server-Sent Events) pour flux temps réel
GET /api/v1/logs/export — download CSV/JSON
DELETE /api/v1/logs/purge — purge manuelle (admin)
Le LogManager suit le pattern singleton et bufferise les logs en mémoire avant écriture batch (flush toutes les 5s ou 100 logs).

Niveaux : DEBUG, INFO, WARN, ERROR, CRITICAL

Génère : backend/core/log_manager.py, backend/api/logs.py, backend/core/log_rotation.py





---

## Prompt 24 — Agent — Module : Wifi credential extractor

Développe le module wifi stealer pour l'agent Project Lucy.

Plateformes supportées :

Windows :
netsh wlan show profiles → liste tous les SSID connus
netsh wlan show profile name="SSID" key=clear → mot de passe en clair
Parse du XML/texte structuré
Linux :
Lit /etc/NetworkManager/system-connections/* (fichiers .nmconnection)
Extrait la section [wifi-security] avec psk= (si non chiffré)
Ou /etc/wpa_supplicant/wpa_supplicant.conf (ssid et psk)
Nécessite root ou lecture sudo
macOS :
security find-generic-password -wa "SSID" (keychain)
/Library/Preferences/SystemConfiguration/com.apple.airport.preferences.plist (ancien)
Format retour :

json



{
  "task_id": "...",
  "status": "completed",
  "data": {
    "networks": [
      {"ssid": "Corp_WiFi", "bssid": "00:11:22:33:44:55", "password": "Corp@2024!", "security": "WPA2", "frequency": "5GHz"},
      {"ssid": "Guest", "bssid": "00:11:22:33:44:66", "password": "guest2024", "security": "WPA2", "frequency": "2.4GHz"}
    ],
    "total": 2,
    "os": "windows"
  }
}
Génère : agent/modules/wifi.py avec implémentations OS-spécifiques





---

## Prompt 25 — Backend — Healthcheck et monitoring

Implémente le système de monitoring pour Project Lucy.

Endpoints :

GET /health — uptime, version, DB status, Redis status, queue size
GET /api/v1/monitor/stats — métriques temps réel
GET /api/v1/monitor/alerts — alertes actives
Alertes automatiques :

Agent offline > 5 min → WARN
Agent offline > 30 min → ALERT (flag "compromised"?)
Queue growth > 100 tâches en 5 min → WARN
Erreur rate > 10% sur les dernières 100 tâches → ALERT
Nouvel agent inconnu (non whitelisted) → INFO
Le monitor exporte les métriques au format Prometheus (optionnel) :




lucy_agents_online{group="windows"} 12
lucy_tasks_completed_total{module="screenshot"} 450
lucy_credentials_collected_total 1234
Génère : backend/api/monitor.py, backend/core/alert_manager.py, backend/core/metrics.py





---

## Prompt 26 — Frontend — MapView géolocalisation des agents

Crée la MapView pour visualiser les agents géographiquement sur Project Lucy.

Technologie : Leaflet avec React-Leaflet

Fonctionnalités :

Marqueurs :
Chaque agent = marqueur avec couleur selon statut (vert=online, orange=idle, rouge=offline)
Popup au click : hostname, OS, IP, uptime, dernières actions
Lien "View Agent" → navigation vers AgentDetail
Heatmap :
Option toggle : heatmap des agents par densité
Utile pour voir les clusters géographiques
Contrôles :
Zoom +/- , plein écran
Filtre : afficher seulement online / un groupe spécifique
Couche satellite / street
Clusterisation :
Quand > 20 marqueurs visibles, active le clustering (Leaflet.markercluster)
Affiche le nombre d'agents dans le cluster
Timeline replay :
Slider temporel : montre la position des agents à un instant T
Lecture automatique (vitesse 1x, 2x, 10x)
Trace les mouvements IP (si un agent change de réseau)
Le component utilise un WebSocket pour les mises à jour en temps réel des positions.

Génère : frontend/src/components/MapView.tsx + composants : AgentPopup.tsx, MapControls.tsx, TimeSlider.tsx





---

## Prompt 27 — Agent — Communication resilient (fallback channels)

Implémente la résilience réseau pour l'agent Project Lucy.

L'agent doit maintenir sa communication quoi qu'il arrive.

Stratégie de fallback (par ordre de préférence) :

WebSocket (primaire) : wss://c2-server.com/ws?token=xxx
Reconnexion automatique avec exponential backoff (1s, 2s, 4s, 8s... max 60s)
Jitter : ±20% aléatoire
HTTP polling (fallback 1) :
POST /api/v1/agents/{id}/checkin — envoie heartbeat, reçoit task (si existe)
Période : 15-45s (randomisé)
Méthode : JSON over HTTPS
DNS tunneling (fallback 2) :
Encapsule les messages dans des requêtes TXT DNS
Format : {base64_message}.channel-{agent_id}.tunnel.lucy.internal
Réponse DNS = commande encodée
Serveur DNS autoritaire personnalisé
ICMP (fallback 3) :
Encapsule data dans ICMP echo request (payload)
Nécessite raw socket (root/admin)
Serveur ICMP listener côté backend
SMTP / IMAP (fallback 4) :
Utilise un compte email préconfiguré
Envoie heartbeat comme email (sujet + corps encodé)
Lit les commandes depuis la boîte de réception
Si auth SMTP/IMAP disponible sans MFA
Détection de coupure :

Si 3 heartbeats consécutifs sans réponse → switch fallback
Si fallback actif et primaire redevient dispo → retour au primaire
État stocké en mémoire : current_channel, last_success, retry_count
Génère : agent/core/channels.py, agent/core/channel_ws.py, agent/core/channel_http.py, agent/core/channel_dns.py, agent/core/channel_icmp.py, agent/core/channel_smtp.py





---

## Prompt 28 — Backend — API de build et compilation agent

Crée le service de build d'agent personnalisé pour Project Lucy.

Principe : un opérateur peut générer un agent compilé (.exe / .bin) avec configuration embarquée.

Endpoints API :

POST /api/v1/builds — create build job Body :
json



{
  "c2_url": "https://c2.example.com",
  "fallback_channels": ["ws", "http", "dns"],
  "heartbeat_jitter": [15, 45],
  "anti_sandbox": true,
  "modules_embeded": ["info", "shell", "screenshot"],
  "modules_remote": ["browser", "keylog"],
  "persistence": ["registry:run", "scheduled_task"],
  "icon": "base64...",
  "compression": "upx",
  "target_os": "windows_x64"
}
GET /api/v1/builds/{id}/status → pending/building/ready/failed
GET /api/v1/builds/{id}/download → binary .exe / .bin
GET /api/v1/builds → history
Pipeline de build :

Template selection : selon target_os
Configuration injection : remplace les placeholders dans agent.py
Module bundling : inclut les modules_embeded, ajoute les imports dynamiques pour les modules_remote
PyInstaller compilation : pyinstaller --onefile --noconsole --icon=... agent_build.py
Compression : UPX (optionnel)
Signature : Authenticode (optionnel, si certificat fourni)
HMAC signature : hash du binaire pour vérification d'intégrité
Le service utilise un worker Celery séparé avec PyInstaller installé.

Génère : backend/api/builds.py, backend/core/build_engine.py, backend/core/build_templates.py, backend/core/signer.py





---

## Prompt 29 — Frontend — Builder UI pour génération d'agent

Crée l'interface utilisateur du Builder d'agent pour Project Lucy.

C'est un wizard en plusieurs étapes :

Step 1 — Configuration C2 :

URL du serveur (input avec validation URL)
Port, SSL toggle
Fallback channels (checkboxes : WebSocket, HTTP, DNS, ICMP, SMTP)
Heartbeat interval (slider 5-120s)
Step 2 — Modules :

Deux listes : "Modules embarqués" (drag vers left) et "Modules distants" (right)
Barre de recherche
Chaque module montre sa taille estimée (KB)
Warning si taille totale > 10MB
Step 3 — Anti-sandbox & Evasion :

Toggle : Vérifier RAM (<2GB)
Toggle : Vérifier écran (<1024x768)
Toggle : Vérifier debugger
Toggle : Vérifier VM (mac address, registry)
Toggle : Vérifier analyse (process list, nom d'utilisateur)
Step 4 — Persistence :

Checkboxes : Registry (Run), Scheduled Task, Startup folder, Cron, Launchd
Option : déguisé en processus système ("svchost.exe", "explorer.exe", "kernel_task")
Step 5 — Compilation :

Target OS : Windows (x86/x64), Linux (x86/x64/ARM), macOS
Compression : UPX (levels 1-9)
Icon : upload .ico ou sélection parmi prédéfinies
Output name : personnalisable
Option : signer le binaire (upload certificat .pfx)
Step 6 — Build & Download :

Résumé de la configuration
Bouton "Build" → barre de progression
Une fois prêt : bouton "Download" + QR code pour transfert mobile
Hash SHA256 affiché (vérification d'intégrité)
Toute la config est sérialisée en JSON et envoyée à POST /api/v1/builds.

Génère : frontend/src/pages/AgentBuilder.tsx + composants : StepC2.tsx, StepModules.tsx, StepAntiSandbox.tsx, StepPersistence.tsx, StepCompile.tsx, StepDownload.tsx





---

## Prompt 30 — Agent — Anti-analysis et evasion basique

Développe les mécanismes anti-analysis pour l'agent Project Lucy.

Checklist exécutée au démarrage (avant tout beacon) :

Sandbox detection :



- RAM < 2GB → suspect (sandbox)
- CPU cores < 2 → suspect
- Disk < 60GB → suspect
- Screen resolution = 800x600 ou 1024x768 → suspect
- Hostname matches regex: (sandbox|malware|virus|analysis|sample) → suspect
- Username: (admin|user|virus|malware|sandbox|sysadmin) → suspect
VM detection :



- Windows: Check registry HKLM\SYSTEM\CurrentControlSet\Services\Disk\Enum
  Si contient "VBOX", "VMWARE", "QEMU", "VIRTUAL" → VM détectée
- Check MAC address prefixes: 00:0C:29 (VMware), 08:00:27 (VirtualBox), 00:50:56 (VMware)
- Check processes: vmtoolsd.exe, VBoxService.exe, qemu-ga.exe, xenservice.exe
- Check hardware: BIOS string contient "VirtualBox", "VMware", "QEMU"
Debugger detection :



- Windows: IsDebuggerPresent() (kernel32 via ctypes)
- Windows: NtQueryInformationProcess avec ProcessDebugPort
- Linux: Check /proc/self/status → TracerPid != 0
- macOS: sysctl.proc_info avec debug flag
- Temps d'exécution : si certaines opérations prennent anormalement longtemps (effet breakpoint)
Timing evasion :



- Sleep avec jitter : sleep(random(30-60s))
- Si execution time < 1ms (remplacé par NOP dans un debugger), skip
Process masquerading :



- Renomme le processus en nom légitime (svchost.exe, explorer.exe, bash, kernel_task)
- Windows: SetConsoleTitle + modification PEB (ImagePathName)
Si un indicateur est détecté → l'agent peut :

S'arrêter silencieusement (exit 0)
Ou entrer en mode dormant (sleep 24h avant prochain check)
Ou envoyer un heartbeat "benign" sans exécuter de modules
La configuration est contrôlée par les paramètres de build.

Génère : agent/core/evasion.py, agent/core/anti_sandbox.py, agent/core/anti_vm.py, agent/core/anti_debug.py





---

## Prompt 31 — Frontend — Timeline visualisation en temps réel (Gantt)

Crée une vue Gantt temps réel pour visualiser l'exécution des timelines sur les agents.

Fonctionnalités :

Gantt chart :
Axe X : temps (millisecondes à heures selon zoom)
Axe Y : agents (ou groupes)
Barres horizontales : chaque tâche avec durée
Couleurs par module : shell=bleu, screenshot=vert, browser=orange, keylog=rouge
État : queued (gris), running (animé), completed (vert), failed (rouge)
Zoom et navigation :
Molette : zoom in/out temporel
Drag : défilement horizontal
Focus auto : scroll vers la tâche en cours
Boutons : 30s, 5min, 1h, 4h, All
Détails au survol :
Tooltip : module, params, agent, durée, status
Click : ouvre le résultat de la tâche dans une modal
Filtres :
Par agent / groupe
Par module
Par statut (running/failed/completed)
Time markers :
Ligne verticale "NOW" (temps réel, mis à jour chaque seconde)
Marqueurs d'événements (agent connecté, credential trouvé, alerte)
Le composant est mis à jour via WebSocket (events : task_started, task_progress, task_completed).

Implémentation : custom SVG ou librairie lightweight (d3.js ou Frappe Gantt adapté).

Génère : frontend/src/components/TimelineGantt.tsx + sous-composants : GanttBar.tsx, TimeAxis.tsx, AgentAxis.tsx, TimelineControls.tsx, TaskDetailModal.tsx





---

## Prompt 32 — Backend — Export et reporting

Crée le système de reporting pour Project Lucy.

Génération de rapports structurés au format HTML, PDF, JSON.

Types de rapports :

Rapport d'engagement (complet) :
Résumé exécutif (nombre d'agents, credentials, tâches, durée)
Timeline de l'opération (événements horodatés)
Liste complète des credentials collectés (groupés par domaine)
Liste des modules exécutés et leurs résultats
Topologie réseau découverte
Screenshots capturés (gallerie)
Rapport credentials :
Tableau : URL, username, password, source, confiance
Filtrable par domaine / niveau de criticité
Export CSV / XLSX
Rapport technique (JSON brut) :
Données machine : hostname, IP, OS, users, logiciels
Résultats module par module
Arborescence fichiers
API :

POST /api/v1/reports/generate — body : {type, format, agent_ids?, date_range?}
GET /api/v1/reports/{id}/download — file
GET /api/v1/reports — liste des rapports générés
Le service de génération tourne en background (Celery) avec :

Template Jinja2 pour HTML
WeasyPrint pour HTML → PDF
json.dumps avec indent pour JSON
Génère : backend/api/reports.py, backend/core/report_engine.py, backend/templates/reports/executive_summary.html, backend/templates/reports/credentials.html





---

## Prompt 33 — Frontend — Settings et configuration panel

Crée la page Settings pour Project Lucy.

Tabs de configuration :

1. General :

Theme : Light / Dark / System
Langue : EN / FR (préparé i18n)
Timezone
Refresh interval (secondes, défaut 5s)
2. API :

Afficher / Régénérer API key
Rate limiting visuel (combien d'appels restants)
Webhook URLs (Slack, Discord, Teams) pour notifications
3. Notifications :

Events notifications : Agent connect, Task complete, Credential found, Error
Par level : push, email, webhook, ou silencieux
4. Agents :

Default heartbeat timeout (minutes)
Auto-purge offline agents après X jours
Default modules à installer sur nouveau agent
5. Security :

Change password
MFA toggle (TOTP via pyotp)
Session timeout (minutes)
IP whitelist (accès panel)
Audit log (dernières connexions)
6. Database :

Taille de la DB
Purge logs > X jours
Export full backup
Import backup
7. About :

Version, build date, license
Liens documentation
Chaque section a un bouton "Save" individuel (auto-save avec Zustand persist).

Génère : frontend/src/pages/Settings.tsx + composants : GeneralSettings.tsx, ApiSettings.tsx, NotificationSettings.tsx, AgentSettings.tsx, SecuritySettings.tsx, DatabaseSettings.tsx, AboutSection.tsx





---

## Prompt 34 — Final Assembly — Docker Compose, CI/CD, déploiement

Assemble et finalise l'intégralité du projet Project Lucy.

Docker Compose (docker-compose.yml) :
yaml



services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [redis]
    volumes: ["./data:/app/data"]
    env_file: .env
  
  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [backend]
  
  redis:
    image: redis:7-alpine
    ports: ["6379"]
  
  celery_worker:
    build: ./backend
    command: celery -A core.celery_app worker --loglevel=info
    depends_on: [backend, redis]
  
  celery_beat:
    build: ./backend
    command: celery -A core.celery_app beat --loglevel=info
    depends_on: [backend, redis]
Dockerfile.backend :
Python 3.12-slim
pip install -r requirements.txt
Copie backend/
CMD: uvicorn main:app --host 0.0.0.0 --port 8000
Dockerfile.frontend :
Build stage : node:20-alpine, npm run build
Run stage : nginx:alpine, copie dist/ dans /usr/share/nginx/html
Custom nginx.conf (proxy_pass /api/ vers backend)
.env.example :



DATABASE_URL=sqlite:///data/lucy.db
SECRET_KEY=change-me-32bytes-random
JWT_SECRET=change-me
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=http://localhost:3000
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-strong
ENCRYPTION_MASTER_KEY=generate-with-openssl-rand-32
Makefile :
make dev : docker-compose up
make build : builds agents
make reset : reset DB
make logs : tail logs
CI/CD GitHub Actions (.github/workflows/deploy.yml) :
Build and push Docker images
Run tests
Deploy to VPS (docker-compose on remote host via SSH)
Documentation (docs/README.md) :
Architecture overview
Setup instructions
API reference
Module development guide
Security considerations (pentest usage)
Tests :
backend/tests/test_api.py (pytest, httpx AsyncClient)
backend/tests/test_crypto.py
backend/tests/test_modules.py
backend/tests/test_agents.py
Coverage target : > 80%
Génère : docker-compose.yml, Dockerfile.backend, Dockerfile.frontend, .env.example, Makefile, .github/workflows/deploy.yml, docs/README.md, backend/tests/*.py





---

## Prompt 35 — Final : Vérification et validation du projet complet

Effectue une validation complète de l'intégration de tous les composants de Project Lucy.

Tu as tous les fichiers du projet. Exécute ces vérifications et génère le rapport :

Vérification des imports :
from backend.core.crypto import encrypt, decrypt fonctionne
from agent.core.channels import ChannelManager fonctionne
from frontend/src/api/client.ts importe bien Axios
Vérification des contrats API :
Tous les endpoints listés dans backend/api/ existent
Les types TS dans frontend/types/ correspondent aux modèles Pydantic
Vérification des signatures de fonctions :
Agent screenshot.run(params) retourne dict avec "status" et "data"
Backend TaskManager.create(agent_id, module, params) valide les champs requis
Vérification des WebSocket events :
Les events émis par backend/ws_manager.py sont écoutés par frontend/hooks/useWebSocket.ts
Mêmes noms de types (heartbeat, task, result, log, error)
Tests d'intégration simulés :
Scénario : Agent se connecte → heartbeat → recoit task screenshot → execute → envoie result → frontend affiche
Vérifie que chaque étape est correctement chaînée
Lint & format :
Vérifie que tous les fichiers Python respectent PEP8 (flake8)
Vérifie que tous les fichiers TypeScript passent (eslint --fix)
Vérifie que les imports sont ordonnés (isort)
Génération du rapport final :



Project Lucy — Validation Report
────────────────────────────────
Components : 47 fichiers backend, 38 fichiers frontend, 12 fichiers agent
Endpoints API : 42 (REST) + 6 (WebSocket)
Agents modules : 12
Tests : 84 pass, 0 fail
Couverture : 83%
Build Docker : OK

Status: ✅ READY FOR DEPLOYMENT
Corrige TOUS les problèmes détectés, meme les plus petits (typo, imports manquants, types mismatch).

Génère le rapport complet et les patches correctifs si nécessaire.





---

## Prompt 36 — Module 23: Internal Browser — Research / Security Browser

Intègre un navigateur Internet interne comme module de première classe dans Lucy. Le module est destiné à la recherche et au travail sécurité autorisé, pas à un iframe générique. Le livrable de cette étape documentaire est le MEGAPLAN + architecture ; aucun code applicatif, manifeste, migration ou dépendance ne doit être implémenté maintenant.

### État actuel et contraintes

- Lucy est aujourd’hui servi par FastAPI + React/Vite, embarqué en portable dans `pywebview` (`tools/portable/window.py`). `pywebview` reste un shell legacy/fallback, pas le moteur cible.
- `frontend/src/components/copilot/WebBrowser.tsx` est un mini-browser mono-page iframe (`sandbox="..."`) : navigation incomplète, pas d’onglets, pas de profils, retour arrière confondu avec l’historique Lucy.
- La recherche web est codée en dur dans `backend/api/ai_chat.py` (DuckDuckGo, Google/Bing/MITRE/Exploit-DB) ; elle doit devenir un registre de providers.
- Lucy possède déjà une Resource Library générique (`Resource`, `ResourceVersion`, `ResourceRelation`, `backend/core/library/registry.py`) avec providers natifs/linked, mais aucun router REST dédié ni UI frontend n’a été trouvé.
- Le RBAC (`backend/api/rbac.py`), l’audit (`AuditTrail` hash-chaîné dans `backend/core/audit_logger.py`), les tenants, les WebSockets (`backend/core/ws_manager.py`) et la recherche unifiée existent mais nécessitent un durcissement avant d’exposer des API Browser.

### Architecture cible

- **Electron Main / Browser Host (privilégié)** : possède les `WebContentsView`, les sessions/partitions Chromium, les proxies, DevTools, les téléchargements, les popup/permissions et les limites de ressources.
- **React Renderer (UI Lucy)** : sans accès Node/filesystem/shell ; reçoit uniquement un `contextBridge` allowlisté, typé, versionné et soumis aux permissions.
- **FastAPI Control Plane** : modèles, RBAC, capabilities, mode sécurité global, audit, Library, historique, file de commandes et broker agent.
- **WebContentsView** : jamais un iframe ni le tag Electron `<webview>` ; contenu distant en `nodeIntegration=false`, `contextIsolation=true`, `sandbox=true`, `webSecurity=true`.

Flux agent futur : actor → FastAPI `BrowserCommandBroker` → policy/RBAC/global mode → commande persistée → Browser Host authentifié → Electron Main → résultat expurgé → audit.

### V1 — Socle local opérateur

- Electron AppShell supervisant FastAPI, chargement de l’UI React via protocole local sécurisé.
- Onglets réels : create, duplicate, close, reopen, pin, mute, move, group, restore.
- États par onglet : URL, titre, favicon, loading, historique de navigation, zoom, mute, groupe/workspace, contexte de sécurité.
- Profils hybrides : persistent/shared, private (mémoire), disposable (partition unique jetable).
- Réseau V1 : DIRECT. Indicateur de contexte visible (URL, profil, network, security mode).
- Library en métadonnées seulement : bookmarks, references, notes, collections.
- Command palette extensible, audit des actions sensibles, fallback web/pywebview dégradé explicite.
- Pas d’agent, pas de Tor, pas de Firefox, pas de DevTools, pas de téléchargements automatiques.

### Modèle de données V1

Réutiliser le modèle `Resource` existant. Pas de `LibraryResource` parallèle.

Types natifs à ajouter si retenus : `bookmark`, `reference`, `browser_snapshot`, `collection`. Réutiliser `note`, `research`, `asset`.

Métadonnées persistantes : URL canonique, domaine, titre, favicon/preview, source profile/workspace, tags, visibilité, project/campaign. Stockées dans `Resource.source` et `Resource.metadata`.

- `ResourceRelation` : liens vers CVE, PoC, Finding, Module, Campaign, Agent, collection.
- `ResourceVersion` : notes et snapshots explicites.
- Les cookies/cache/local storage/session storage Chromium restent dans les partitions Electron et ne sont pas copiés dans SQLite.
- Screenshot/snapshot/PDF/page complète : action explicite + vault hashé.

Nouveaux modèles V1 (tenant-scoped) : `BrowserProfile`, `BrowserWorkspace`, `BrowserTabState`, `BrowserHistoryEntry`, `BrowserNetworkProfile`, `BrowserPermissionGrant`, `BrowserCommandRequest`.

### Mode global et autorisation

- Mode global administrateur : désactivé par défaut, activable par admin, indicateur permanent, horodaté et audité.
- Capabilities Browser : `browser:read`, `browser:navigate`, `browser:inspect`, `browser:capture`, `browser:library:write`, `browser:download`, `browser:devtools`, `browser:network:manage`, `browser:agent:request`, `browser:security:active`.
- Éligible ≠ autorisé : tous les types d’agents pourront être éligibles dans une phase ultérieure, mais chaque acteur reçoit des grants explicites.
- Actions sensibles passent par `PermissionGate` et sont auditées avec actor, tenant, profile, tab, command, origin, outcome, correlation id.

### Agent Browser (phase ultérieure)

Commandes initiales autorisées : `open`, `search`, `navigate`, `inspect` passif, `screenshot` borné, `extract` borné, `bookmark`, `save_to_library`.

Exclus en V1 : JavaScript arbitraire, remplissage/soumission de formulaires, lecture cookies/tokens, export non expurgé, téléchargement/exécution, DevTools.

File offline sécurisée : visible, TTL court, taille limitée, idempotence, annulation, revalidation permissions/global mode/profile/host avant exécution, refus si devenue invalide, pas de replay automatique.

### Phases d’implémentation

0. **ADR et fondations sécurité** : threat model, schémas IPC/commands, durcissement auth/tenant/RBAC/audit/SSRF, prototype Windows `WebContentsView`, go/no-go.
1. **Local operator browser** : AppShell, onglets, profils hybrides, DIRECT, Library métadonnées, command palette, audit.
2. **Research workspace** : search provider registry, multi-source layout, notes/highlights, liens CVE/NVD/PoC/Campaign.
3. **Passive inspection + downloads** : headers/DOM/source/TLS/network, DevTools permissionné, download manager/quarantaine/hash/scan.
4. **Agent + extensions** : Browser Host Gateway, broker, grants, queue, extensions signées least-privilege.
5. **Proxy/Tor** : processus dédié, SOCKS, healthcheck, fail-closed, pas de fallback DIRECT, pas de partage cache/DNS/WebRTC.
6. **Firefox compatibility** : adapter externe uniquement si besoin concret.

### Comparaison moteur

| Option | Avantages | Limites | Décision |
|---|---|---|---|
| iframe React actuel | aucun runtime | CSP/X-Frame-Options, pas de session/DevTools | rejeté |
| pywebview/WebView2 | léger, déjà présent | API trop étroite, pas de vrais onglets/partitions/proxy | legacy/fallback |
| Tauri/WebView2 | plus léger | stack Rust, plugins natifs | non retenu V1 |
| Electron + `WebContentsView` | contrôle maximal, partitions, proxy, DevTools, downloads | poids, patching, packaging | retenu |
| CEF/CEF Python | contrôle natif | distribution, intégration Python | rejeté |
| Firefox embarqué | Gecko | pas de voie intégrée réaliste | adapter externe futur |

### Dépendances

V1 : Electron (version stable épinglée, publiée ≥ 7 jours), Electron Forge/maker Windows, Zod ou équivalent validation IPC, FastAPI/Pydantic/Peewee/SQLite/Axios/Zustand/React Query déjà présents.

Tests : Vitest, React Testing Library, Playwright Electron, fuses/checklist sécurité.

Futures : Tor daemon, scanner adapters, Firefox automation (optionnel).

### Risques et pré-requis de durcissement

1. Ajouter `require_permission()` réel avant les routes Browser.
2. Corriger `User.tenant` (auto-référence actuelle → `Tenant`).
3. JWT/contexte fiable avec username + tenant_id.
4. Chaîne `AuditTrail` transactionnelle et sûre sous concurrence.
5. Derive actor/tenant depuis l’authentification, jamais du client.
6. Normaliser imports `audit_logger` / `log_event`.
7. Exposer Resource Library par une API REST dédiée + client frontend.
8. Corriger tenant/visibility dans `library/providers`.
9. Ajouter types natifs Browser et compléter provider CVE manquant.
10. Invariants `source_type/source_id` et relations de collection.
11. Traiter `/fetch-url` comme surface SSRF avant réutilisation agent.
12. Valider schéma, taille, rate, sender sur WebSocket Browser Host/agents.
13. Nommer le domaine backend `internal_browser` et le runtime desktop `BrowserHost` pour éviter confusion avec `agent/modules/browser.py`.

### Critères d’acceptation

- Prompts 1–35 inchangés, Prompt 36 unique, conclusion indiquant 36 prompts.
- Choix confirmés inscrits : Electron, Windows-first, V1 local, métadonnées-only, profils hybrides, mode global, agents postérieurs, file offline sécurisée.
- Aucun code applicatif, manifeste, migration ou dépendance installée dans cette étape.
- L’implémentation future incluera tests backend, frontend, Electron E2E Windows, sécurité, isolation profils, Library metadata-only, queue agent, téléchargements, Tor fail-closed.

Écris maintenant ce Prompt 36 comme un plan d’architecture complet et cohérent, prêt à guider l’implémentation sans la lancer.

---

Ce découpage en 36 prompts agentiques te donne un **cycle complet** : 