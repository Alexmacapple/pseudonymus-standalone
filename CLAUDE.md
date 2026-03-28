# Pseudonymus standalone

**Dépôt** : `git@github.com:Alexmacapple/pseudonymus-standalone.git`
**Branche principale** : `main`
**Licence** : GPL v3
**Python** : 3.8+

---

## Description

Outil de pseudonymisation/anonymisation de données personnelles, 100 % local. Moteur Python (CLI + API) avec interface web DSFR. Aucune donnée ne transite vers un service externe.

**Utilisateurs cibles** : agents publics, DPO, équipes data manipulant des données personnelles (RGPD).

---

## Architecture

```
pseudonymus-standalone/
├── pseudonymise.py        # Moteur principal (CLI + API)
├── depseudonymise.py      # Restauration des jetons
├── formats.py             # Parseurs multi-format (CSV, XLSX, ODS, DOCX, PDF, TXT, MD)
├── serveur.py             # Serveur HTTP local (port 8090)
├── convertir-donnees.py   # Régénération des données statiques
├── data/                  # 9 fichiers JSON de référence (884k patronymes, 169k prénoms)
├── exemples/              # Mappings et données de test
├── confidentiel/          # Correspondances CSV (gitignoré, jamais versionné)
├── interface/             # Frontend DSFR
│   ├── index.html         # 7 pages (pseudo, import, analyse, scoring, correspondances, restauration, doc)
│   ├── app.js             # Logique frontend
│   ├── style.css          # Styles complémentaires
│   └── dsfr/              # CSS, JS, polices DSFR embarqués
├── prd/                   # PRD à faire (à la racine)
│   └── done/              # PRD terminés + documentation
├── install.sh             # Installation complete (venv + dependances + tests)
├── tests/
│   ├── test-options.py    # 49 tests moteur
│   ├── test-v3.py         # 145 tests API/formats/securite
│   ├── test-e2e.sh        # 14 tests e2e navigateur (agent-browser)
│   └── fixtures/          # Donnees de reference
├── requirements.txt       # Dépendances optionnelles
├── CHANGELOG.md           # Historique des versions
└── LICENSE                # GPL v3
```

---

## Commandes essentielles

```bash
# Lancer le serveur web
python3 serveur.py --port 8090

# CLI : pseudonymiser un fichier
python3 pseudonymise.py fichier.json --mapping mapping.json --pseudo

# CLI : dry-run (100 premiers enregistrements, pas d'écriture)
python3 pseudonymise.py fichier.json --mapping mapping.json --dry-run

# CLI : générer un mapping automatiquement
python3 pseudonymise.py fichier.json --mapping-generate

# CLI : scoring RGPD sans pseudonymiser
python3 pseudonymise.py fichier.json --mapping mapping.json --score-only

# Dépseudonymiser
python3 depseudonymise.py fichier_PSEUDO.json --correspondances confidentiel/correspondances.csv

# Tests
python3 tests/test-options.py         # 49 tests moteur
.venv/bin/python3 tests/test-v3.py   # 145 tests formats + API + e2e
```

---

## Conventions

### Langue

Tout en français : commits, documentation, messages d'erreur, interface.

### Git

- Messages de commit en français, forme nominale (« Ajout de... », « Correction de... »)
- Branches : `feature/`, `fix/`, `docs/`
- Pas de `git push --force` ni `git reset --hard` sans confirmation
- Mettre à jour [CHANGELOG.md](CHANGELOG.md) à chaque commit (section courante en haut du fichier)

### Code Python

- Pas de dépendance externe pour le cœur (JSON, CSV, serveur)
- Imports optionnels avec try/except et message d'erreur clair
- Chemins relatifs au script (`os.path.dirname(__file__)`)
- Correspondances toujours dans `confidentiel/` à la racine du projet

### Interface DSFR

- Composants DSFR natifs (pas de CSS custom quand un composant existe)
- Accessibilité RGAA vérifiée
- `lang="fr"` sur `<html>`, formulaires avec `<label for>`

---

## Points d'attention

- **`confidentiel/`** contient les correspondances en clair (jetons / valeurs originales). Ce dossier est gitignoré (chmod 700) et ne doit jamais être versionné.
- **`data/noms.json`** (11,6 Mo) et **`data/prenoms.json`** (1,9 Mo) sont des données de référence immuables. Elles ne sont pas régénérées par `convertir-donnees.py`.
- **Le serveur écoute sur `127.0.0.1` uniquement** (pas d'accès réseau). Ne jamais changer pour `0.0.0.0` sans sécurisation.
- **`/api/download`** est sécurisé par whitelist : seuls les fichiers générés par le serveur sont téléchargeables.
- **Fichiers > 500 Mo** : en mode chemin local (interface web), le fichier est chargé entièrement en mémoire. Pour les très gros fichiers, utiliser le CLI avec `--chunk-size 5000` (streaming par paquets, nécessite ijson).
- **CORS** : restreint à localhost. Pour un accès externe (Tailscale), définir `PSEUDONYMUS_ALLOWED_ORIGIN=https://mon-serveur.ts.net:port`.

---

## Tests

Toujours exécuter les deux suites après modification :

```bash
python3 tests/test-options.py    # Moteur : modes, options, formats, dépseudonymisation
python3 tests/test-v3.py         # Formats multi, serveur, API REST
```

Seuil : **208/208 (49 + 145 + 14 e2e)**, 0 FAIL, 0 SKIP.
Exécuter avec le venv pour couvrir tous les formats : `.venv/bin/python3 tests/test-v3.py`

---

## Dépendances optionnelles

Le cœur fonctionne avec zéro dépendance (stdlib Python uniquement). Les formats bureautiques nécessitent :

| Format | Package |
|--------|---------|
| XLSX | `openpyxl` |
| ODS/ODT | `odfpy` |
| DOCX | `python-docx` |
| PDF | `pdfplumber` |
| Streaming | `ijson` |
| NLP | `spacy` + modèle `fr_core_news_sm` |

---

## Historique

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique complet des versions (v1.0.0 à v3.0.0).

## Origine

Issu de Pseudonymus v2 (JavaScript, dépôt `claude-workflow-perso`). La v3 Python a été extraite comme dépôt autonome le 2026-03-26.
