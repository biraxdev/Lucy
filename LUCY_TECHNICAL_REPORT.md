# Lucy — Compte rendu technique

> Version : aout 2026  
> Objectif : permettre a un technicien de comprendre l'architecture, le stack et le fonctionnement de Lucy.

---

## 1. Qu'est-ce que Lucy ?

**Lucy** est un **C2 (Command & Control)** leger, 100 % autonome, concu pour des **simulations Red Team autorisees**. Il permet de :

- Generer un agent implant (payload Windows/Linux/macOS).
- Controler les agents a distance via une interface web.
- Envoyer des taches (shell, fichiers, keylogger, screenshot, recon, etc.).
- Recolter credentials, findings, logs et evenements.
- Orchestrer des scenarios via des **timelines** et des **groupes d'agents**.
- Produire des rapports d'engagement.

Le tout fonctionne en **mode portable** (cle USB, dossier unique) sans dependance externe (pas de Docker obligatoire, pas de Redis obligatoire en mode portable).

---

## 2. Stack technique

| Couche | Technologie |
|--------|-------------|
| **Backend** | Python 3.12, FastAPI, Uvicorn, WebSockets, SQLite, Peewee ORM |
| **Frontend** | React 18 + TypeScript, Vite, TailwindCSS, DaisyUI, Zustand |
| **Agent** | Python 3.x (bibliotheque standard), binaire compile avec PyInstaller |
| **File d'attente** | Celery + Redis (en mode Docker) ; desactive en mode portable |
| **Authentification** | JWT (access 30 min / refresh 7 jours), bcrypt, rotation de cle API |
| **Cryptographie** | AES-256-GCM, ECDH P-256, HKDF, HMAC-SHA256 |
| **Build** | Docker Compose (dev) ou PyInstaller (agent) |
| **Interface native** | pywebview (facultatif, fenetre desktop) |

---

## 3. Architecture globale

```
┌─────────────────────┐
│   Opérateur (vous)  │
│  Navigateur / App   │
└──────────┬──────────┘
           │ HTTPS / WS
           ▼
┌─────────────────────┐      ┌─────────────┐
│  FastAPI C2 Backend │<---->│  SQLite DB  │
│  - REST API         │      └─────────────┘
│  - WebSocket agents │
│  - WebSocket front  │
└──────────┬──────────┘
           │ WebSocket + messages chiffres
           ▼
┌─────────────────────┐
│  Agent implant      │
│  Python / .exe      │
│  Modules dynamiques │
└─────────────────────┘
```

---

## 4. Composants principaux

### 4.1 Backend (`backend/`)

- **`main.py`** : point d'entree FastAPI, gestion du cycle de vie.
- **`config.py`** : parametres lus depuis `.env` (DB, JWT, CORS, portable).
- **`middleware.py`** : CORS, logging, authentification JWT/cle API, chemins publics.
- **`api/`** : routes REST et WebSocket.
  - `auth.py` : login, refresh, changement de mot de passe, rotation cle API.
  - `agents.py` : gestion des agents.
  - `tasks.py` : soumission et suivi des taches.
  - `build.py` : generation d'agent (PyInstaller) + telechargement.
  - `ws.py` : WebSocket frontend (`/ws/frontend`) + WebSocket agent (`/ws/agent/{id}`).
  - `reports.py`, `findings.py`, `credentials.py`, `modules.py`, `groups.py`, `timelines.py` : modules metiers.
- **`core/`** : logique metier (auth, crypto, orchestrateur, gestionnaires de connexion/taches/logs/credentials).
- **`db/models.py`** : modeles Peewee (Agent, Task, User, Credential, Module, etc.).

### 4.2 Frontend (`frontend/src/`)

- **`main.tsx`** : montage React + ErrorBoundary.
- **`routes.tsx`** : react-router, lazy loading des pages.
- **`pages/`** : ecrans (Dashboard, Agents, Tasks, Builder, Settings, etc.).
- **`api/client.ts`** : instance axios avec intercepteur JWT.
- **`stores/`** : etat global Zustand (auth, agents, taches, UI).
- **`hooks/`** : WebSocket, react-query, agents.

### 4.3 Agent (`agent/`)

- Script Python autonome.
- Se connecte au C2 par WebSocket.
- Telecharge les modules a la volee (signes HMAC).
- Chiffre les messages (ECDH + AES-256-GCM).

---

## 5. Flux d'utilisation typique (mode portable)

1. Lancer `tools/portable/launcher.py` ou le raccourci bureau.
2. Le backend demarre sur `http://127.0.0.1:8000`.
3. Ouvrir l'interface dans le navigateur (fallback si pywebview n'est pas disponible).
4. Se connecter avec les identifiants par defaut :
   - **Username : `admin`**
   - **Password : `admin`**
5. Aller dans **Agent Builder**.
   - Le C2 URL est pre-rempli.
   - La cle API est generee automatiquement.
   - Choisir un pack (Basic Recon, Stealth, etc.) ou **Quick Build**.
6. Telecharger l'artefact (ZIP pour Windows).
7. Sur la cible : extraire, lancer `build.bat`, puis `dist/lucy_agent.exe`.
8. L'agent apparait dans le Dashboard.
9. Envoyer des taches, consulter credentials/findings, generer des rapports.

---

## 6. Securite

- Tous les endpoints API (sauf login/health) exigent un JWT ou une cle API.
- Le build est protege par un token JWT et optionnellement un `BUILD_AUTH_TOKEN`.
- Chaque agent genere est **watermarke** (ID operateur + build ID + TTL) et logge dans `data/build_audit.log`.
- Communications agent/C2 chiffrees (ECDH + AES-GCM).
- L'agent peut detecter VM/debugger/sandbox (options de build).

---

## 7. Ameliorations recentes

- **Chat-first operator experience (Lucy Chat)** : nouvelle page `/chat` permettant de piloter Lucy en langage naturel. Les evenements agents (heartbeat, resultats, connexions/deconnexions, logs) sont traduits automatiquement en messages personnalises par une persona locale, sans appel a un LLM externe.
  - Intents supportes : statut agent, execution de taches, declenchement de timelines, consultation des credentials/findings/tasks, build d'agent, auto-destruction.
  - Moteur : `backend/core/chat_engine.py`, `chat_intents.py`, `chat_persona.py`.
  - Persistance : modele `ChatMessage` avec table `chat_messages` et migration `002`.
  - Diffusion : le WebSocket frontend emet des messages de type `chat` en temps reel.
- **Stealth Pack** : preset `AgentBuilder` qui active en un clic `hide_window`, `beacon_jitter`, `anti_analysis`, `startup_delay` et `self_destruct` pour minimiser l'empreinte sur la cible.
- **Hardening agent** : dissimulation de la console Windows au demarrage, User-Agent banalise pour les requetes HTTP, jitter aleatoire sur les appels reseau, action `stealth.self_destruct` declenchable depuis le chat.
- **Donnees de strategie** : modeles `Tactic`, `Technique`, `Campaign`, `Playbook` et `AgentNote` pour cartographier les TTPs, organiser les campagnes, stocker des notes d'operateur et executer des playbooks reutilisables.
- **Fonctions pratiques** depuis le chat :
  - envoi de taches en masse (`run whoami on all online agents`)
  - operations fichiers (`list files on Agent 01 in C:\Users`)
  - notes d'agent (`note that Agent 01 is a domain controller`)
  - campagnes (`create campaign Alpha`, `campaign summary`)
  - playbooks (`run playbook recon on Agent 01`)
  - mapping MITRE (`map technique T1059`)
- **Page Strategy** : tableau de bord visuel des campagnes, playbooks, techniques et notes.
- **Variables d'environnement** : `CHAT_HISTORY_LIMIT`, `CHAT_LOCAL_LLM_URL` (prepare pour future integration LLM local), `STEALTH_PACK_DEFAULT`.
- **Authentification du telechargement** : `AgentBuilder` et `Reports` utilisent maintenant axios avec blob au lieu de `window.open`, ce qui envoie le token JWT.
- **Robustesse WebSocket** : route `/ws/frontend` corrigée pour correspondre au client, et le montage statique ignore proprement les scopes non-HTTP.
- **Correction crash Dashboard** : garde `?? []` sur `agents`/`tasks` et memoization avec `useMemo`.
- **UX noob-friendly** : carte Quick Start sur le Dashboard, bouton **Quick Build**, cle API auto-generee, infobulles sur les options.
- **ErrorBoundary** : evite l'ecran blanc en cas d'erreur React.
- **Launcher** : reste actif si la fenetre native echoue et bascule sur le navigateur.

---

## 8. Points de vigilance

- **Ne jamais** utiliser Lucy sur un systeme sans autorisation explicite.
- Le mode portable utilise `tools/portable/lucy.db` (SQLite), separe de la DB Docker.
- Les identifiants admin sont synchronises avec `.env` au demarrage ; les changer via **Settings** apres la premiere connexion.
- Le build Windows produit un ZIP contenant les sources + script `build.bat` car PyInstaller Windows doit s'executer sur Windows.

---

## 9. Commandes utiles

```powershell
# Mode portable (Windows)
python tools/portable/launcher.py

# Mode navigateur explicite
python tools/portable/launcher.py --browser

# Backend direct (dev)
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Frontend dev
cd frontend
npm run dev

# Build frontend
cd frontend
npm run build
```

---

## 10. Contact / Support

- Fichier structure complet : `project-lucy-structure.md`
- Prompts systeme : `MASTER_PROMPT.md`
- Reset admin portable : `tools/portable/reset_admin.py`
