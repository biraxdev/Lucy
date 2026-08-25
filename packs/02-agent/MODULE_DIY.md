# Module DIY — Créer un module Lucy compatible

Un module Lucy est un simple fichier Python. Tu n'as pas besoin de toucher le backend ou le frontend.

## La Recette (Step-by-Step)

1. **Créer un fichier `.py`** dans `agent/modules/`. Nomme-le par exemple `mon_module.py`.
2. **Définir les métadonnées** globales : `NAME`, `VERSION`, `DESCRIPTION`, `AUTHOR`, `DEPENDENCIES`, `OS_COMPAT`.
3. **Définir la fonction `run(action, params)`** — c'est tout ce que l'agent appelle.
4. **Retourner un dict JSON** avec `status`, `data`, et optionnellement `error`.

## Template minimal

```python
# mon_module.py

NAME = "mon_module"
VERSION = "1.0.0"
DESCRIPTION = "Ce que fait mon module"
AUTHOR = "ton_nom"
DEPENDENCIES = []  # Liste de packages pip si besoin (optionnel)
OS_COMPAT = ["windows", "linux", "darwin"]  # OS supportés


def run(action: str, params: dict) -> dict:
    """
    action : string — ce que l'opérateur demande (ex: "execute", "scan", "collect")
    params : dict — arguments envoyés depuis le dashboard (ex: {"target": "127.0.0.1"})

    Retourne obligatoirement un dict avec :
    - status: "completed" | "failed"
    - data: any (résultat)
    - error: str (optionnel, si failed)
    """
    if action == "execute":
        # Ta logique ici
        result = _do_something(params)
        return {
            "status": "completed",
            "data": result
        }

    return {
        "status": "failed",
        "data": None,
        "error": f"Action inconnue: {action}"
    }


def _do_something(params: dict) -> dict:
    return {"message": "Hello from mon_module!"}
```

## Exemple concret : shell.py

```python
NAME = "shell"
VERSION = "1.0.0"
DESCRIPTION = "Execute shell commands"
AUTHOR = "lucy"
DEPENDENCIES = []
OS_COMPAT = ["windows", "linux", "darwin"]


def run(action, params):
    import subprocess
    if action == "execute":
        cmd = params.get("cmd", "whoami")
        result = subprocess.check_output(cmd, shell=True).decode()
        return {"status": "completed", "data": {"stdout": result}}
    return {"status": "failed", "data": None, "error": "Action inconnue"}
```

## Règles importantes

| Règle | Pourquoi |
|-------|----------|
| **Stdlib uniquement** | L'agent n'a pas accès à pip. Si tu as besoin d'un package externe, liste-le dans `DEPENDENCIES` — le loader essaiera de le télécharger, mais ce n'est pas garanti. |
| **Pas d'écriture disque** | Sauf action explicite `file.write`. Tout doit rester en mémoire. |
| **Pas de print/stdout** | Tout retour doit passer par le dict de `run()`. |
| **Thread-safe** | L'agent exécute les modules dans des threads. Utilise `threading.Lock` si tu as du state global. |
| **Timeout** | Le timeout par défaut est 60s. Si ton module dépasse, il sera tué. |

## Upload

1. Va dans le dashboard → **Module Store** (`/modules`)
2. Clique **Upload**
3. Sélectionne ton fichier `.py`
4. Le backend lit les métadonnées, signe le code avec HMAC, et l'enregistre dans la DB
5. L'agent peut maintenant le télécharger et l'exécuter

## Signature et sécurité

Le backend signe chaque module avec HMAC-SHA256. L'agent vérifie la signature avant d'exécuter. Si la signature ne correspond pas, le module est rejeté.
