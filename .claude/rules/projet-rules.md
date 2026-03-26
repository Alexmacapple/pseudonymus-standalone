# Règles du projet Pseudonymus standalone

## Langue

Tout en français : code, commits, documentation, messages d'erreur, interface.

## Architecture

- Le cœur (JSON, CSV, serveur) fonctionne avec zéro dépendance externe (stdlib Python uniquement)
- Tous les chemins sont relatifs au script (`os.path.dirname(__file__)`)
- `confidentiel/` est toujours à la racine du projet, jamais à côté du fichier source
- Les données de référence (`data/noms.json`, `data/prenoms.json`) sont immuables

## Tests

- Toujours exécuter les deux suites après modification : `python3 tests/test-options.py` + `python3 tests/test-v3.py`
- Seuil : 92/92, 0 FAIL, 0 SKIP
- Ne jamais commiter avec des tests en échec

## Sécurité

- Le serveur écoute sur `127.0.0.1` uniquement
- `confidentiel/` est gitignoré et ne doit jamais être versionné
- `/api/download` accepte un chemin arbitraire (risque connu, à sécuriser)

## Interface DSFR

- Composants DSFR natifs uniquement
- Accessibilité RGAA vérifiée
- Pas de chemins absolus utilisateur dans les placeholders
