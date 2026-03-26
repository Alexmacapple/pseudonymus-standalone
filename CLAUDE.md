# Pseudonymus standalone

**Depot** : `git@github.com:Alexmacapple/pseudonymus-standalone.git`
**Branche principale** : `main`
**Licence** : GPL v3
**Python** : 3.8+

---

## Description

Outil de pseudonymisation/anonymisation de donnees personnelles, 100% local. Moteur Python (CLI + API) avec interface web DSFR. Aucune donnee ne transite vers un service externe.

**Utilisateurs cibles** : agents publics, DPO, equipes data manipulant des donnees personnelles (RGPD).

---

## Architecture

```
pseudonymus-standalone/
├── pseudonymise.py        # Moteur principal (CLI + API)
├── depseudonymise.py      # Restauration des jetons
├── formats.py             # Parseurs multi-format (CSV, XLSX, ODS, DOCX, PDF)
├── serveur.py             # Serveur HTTP local (port 8090)
├── convertir-donnees.py   # Regeneration des donnees statiques
├── data/                  # 9 fichiers JSON de reference (884k patronymes, 169k prenoms)
├── exemples/              # Mappings et donnees de test
├── confidentiel/          # Correspondances CSV (gitignore, jamais versionne)
├── interface/             # Frontend DSFR
│   ├── index.html         # 6 pages (pseudo, correspondances, restauration, import, scoring, doc)
│   ├── app.js             # Logique frontend
│   ├── style.css          # Styles complementaires
│   └── dsfr/              # CSS, JS, polices DSFR embarques
├── docs/
│   ├── prd/               # PRD (decisions produit)
│   └── doc/               # Documentation utilisateur
├── test-options.py        # 49 tests moteur
├── test-v3.py             # 43 tests formats + serveur + API
├── requirements.txt       # Dependances optionnelles
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

# CLI : dry-run (100 premiers enregistrements, pas d'ecriture)
python3 pseudonymise.py fichier.json --mapping mapping.json --dry-run

# CLI : generer un mapping automatiquement
python3 pseudonymise.py fichier.json --mapping-generate

# CLI : scoring RGPD sans pseudonymiser
python3 pseudonymise.py fichier.json --mapping mapping.json --score-only

# Depseudonymiser
python3 depseudonymise.py fichier_PSEUDO.json --correspondances confidentiel/correspondances.csv

# Tests
python3 test-options.py    # 49 tests moteur
python3 test-v3.py         # 43 tests formats + API
```

---

## Conventions

### Langue

Tout en francais : commits, documentation, messages d'erreur, interface.

### Git

- Messages de commit en francais, forme nominale ("Ajout de...", "Correction de...")
- Branches : `feature/`, `fix/`, `docs/`
- Pas de `git push --force` ni `git reset --hard` sans confirmation

### Code Python

- Pas de dependance externe pour le coeur (JSON, CSV, serveur)
- Imports optionnels avec try/except et message d'erreur clair
- Chemins relatifs au script (`os.path.dirname(__file__)`)
- Correspondances toujours dans `confidentiel/` a la racine du projet

### Interface DSFR

- Composants DSFR natifs (pas de CSS custom quand un composant existe)
- Accessibilite RGAA verifiee
- `lang="fr"` sur `<html>`, formulaires avec `<label for>`

---

## Points d'attention

- **`confidentiel/`** contient les correspondances en clair (jetons / valeurs originales). Ce dossier est gitignore et ne doit jamais etre versionne.
- **`data/noms.json`** (11,6 Mo) et **`data/prenoms.json`** (1,9 Mo) sont des donnees de reference immuables. Elles ne sont pas regenerees par `convertir-donnees.py`.
- **Le serveur ecoute sur `127.0.0.1` uniquement** (pas d'acces reseau). Ne jamais changer pour `0.0.0.0` sans securisation.
- **`/api/download`** accepte un chemin arbitraire sans validation (risque de path traversal). A securiser avant tout deploiement non local.

---

## Tests

Toujours executer les deux suites apres modification :

```bash
python3 test-options.py    # Moteur : modes, options, formats, depseudonymisation
python3 test-v3.py         # Formats multi, serveur, API REST
```

Seuil : **92/92 (49 + 43)**, 0 FAIL, 0 SKIP.

---

## Dependances optionnelles

Le coeur fonctionne avec zero dependance (stdlib Python uniquement). Les formats bureautiques necessitent :

| Format | Package |
|--------|---------|
| XLSX | `openpyxl` |
| ODS/ODT | `odfpy` |
| DOCX | `python-docx` |
| PDF | `pdfplumber` |
| Streaming | `ijson` |
| NLP | `spacy` + modele `fr_core_news_sm` |

---

## Origine

Issu de Pseudonymus v2 (JavaScript, depot `claude-workflow-perso`). La v3 Python a ete extraite comme depot autonome le 2026-03-26. Voir `CHANGELOG.md` pour l'historique complet.
