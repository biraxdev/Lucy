# Règles de contexte Devin — Lucy

## Principes généraux
- Ne jamais demander si on arrête/démarre un service ou une tâche. Prendre la décision optimale par défaut.
- Ne jamais poser de question binaire quand une solution technique est possible. Proposer l'implémentation ; l'utilisateur corrigera si besoin.
- Chaque action doit faire évoluer l'outil vers un état supérieur.
- Aucune poudre aux yeux : pas de tests trafiqués, pas de timeouts bidons, pas de réponses factices.
- Privilégier l'action à la demande de permission.

## Intelligence / latitude
- Anticiper les besoins : persistence, redondance, états de vie, auto-réparation, pack manager.
- En cas d'ambiguïté, choisir l'interprétation la plus proche du but et la justifier en une phrase.
- Ne jamais réduire les compétences pour faire passer un test.
- Ne jamais couper, tronquer ou altérer les données collectées.
- Préserver l'architecture existante ; ajouter des modules propres plutôt que réécrire.

## Build / agent
- Le build `.exe` est systématique quand on construit un agent.
- L'agent installé est persistant : service Windows, redémarrage auto, modes dormant / vivant / mort.
- L'installation ne demande rien avant de builder.

## Pack Manager
- Un pack est un `BuildPack` réutilisable (modules + options).
- Toutes les opérations pack (créer, éditer, dupliquer, supprimer, rechercher, combiner, appliquer, automatiser, télécharger, uploader) doivent être accessibles depuis Lucy.
- L'interface reste simple : une page, des actions one-click, pas de wizard complexe.

## Vérification
- Toujours fournir des preuves concrètes (résultats de tests, captures, logs).
- Tester après chaque modification significative.
