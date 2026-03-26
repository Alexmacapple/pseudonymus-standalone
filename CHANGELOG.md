# Changelog

Historique des modifications de Pseudonymus standalone.
Issu de la branche `feature/alex-workflow` du depot `pseudonymus2`.

---

## v3.0.0 — 2026-03-26

Depot autonome, independant du monorepo `pseudonymus2`.

### Autonomie du depot

- Renommage `generique/` en `pseudonymus-standalone/`
- Internalisation complete : zero dependance vers `public/`, `virginie/`, `specifique/`
- Centralisation de `confidentiel/` a la racine du projet
- Ajout `requirements.txt`, `.gitignore`, `LICENSE` (GPL v3)
- Nettoyage de toutes les references a l'ancien nom `generique/`
- Donnees de test SignalConso synthetiques (`exemples/test-signalconso.json`)
- Documentation reorganisee dans `docs/prd/` et `docs/doc/`
- 92/92 tests OK en isolation

### Interface web DSFR

- Navigation par ancres avec fil d'Ariane DSFR
- 6 pages : pseudonymisation, correspondances, restauration, import fichier, scoring RGPD, documentation
- Footer DSFR complet avec liens obligatoires
- Import par chemin local (fichiers volumineux, zero transfert HTTP)
- Telechargement zip (resultat + correspondances) en mode local
- Generation automatique de mapping depuis l'interface
- Options fort/NLP/tech sur toutes les pages
- Conformite RGAA verifiee

### Documentation

- README complet : demarrage rapide, CLI, API, formats, securite, arborescence
- Guide utilisateur, glossaire, FAQ
- Parcours concret avec exemple avant/apres
- Documentation CLI integree dans l'interface web

---

## v2.0.0 — 2026-03-25

Moteur Python multi-format avec serveur web local.

### Moteur de pseudonymisation

- Iso-perimetre fonctionnel avec Pseudonymus v2 (JavaScript)
- Mode standard + mode fort (pipeline complet)
- NLP optionnel (spaCy) pour detection des entites nommees
- Regex techniques : IPv4/v6, MAC, JWT, API keys (`--tech`)
- Scoring RGPD : 4 categories (direct, finance, tech, indirect)
- Depseudonymisation reversible via table de correspondances CSV

### Formats supportes

- JSON, CSV, TSV : natif (zero dependance)
- XLSX : via openpyxl
- ODS, ODT : via odfpy
- DOCX : via python-docx
- PDF : via pdfplumber (lecture seule)

### CLI

- `--pseudo` : pseudonymisation reversible
- `--anon` : anonymisation irreversible
- `--dry-run` : test sur 100 enregistrements
- `--score-only` : scoring RGPD sans pseudonymiser
- `--mapping-generate` : generation automatique de mapping
- `--input-dir` : traitement batch d'un dossier
- `--chunk-size` : streaming pour fichiers > 2 Go (ijson)
- `--fort`, `--nlp`, `--tech` : options de detection

### Serveur web local

- `serveur.py` : serveur HTTP sur 127.0.0.1:8090
- API REST : 8 endpoints (pseudo, depseudo, score, mapping, stats, health, download)
- Interface DSFR servie en local (CSS, JS, polices embarques)

### Donnees de reference

- 884 314 patronymes INSEE
- 169 244 prenoms INSEE
- Stopwords capitalises et minuscules
- Villes francaises, mots d'organisations, contexte institutionnel, acronymes

### Tests

- 49 tests moteur (`test-options.py`)
- 43 tests formats + serveur + API (`test-v3.py`)

---

## v1.0.0 — 2026-03-25

Premier script Python de pseudonymisation.

### Fonctionnalites initiales

- Script batch pour fichiers JSON
- Pseudonymisation et anonymisation
- Mode standard avec regex (noms, prenoms, emails, telephones, CP, IBAN, NIR)
- Table de correspondances CSV
- 35 tests automatises

---

## Origine

Ce projet est issu de [Pseudonymus v2](https://github.com/Alexmacapple/claude-workflow-perso) (application JavaScript cote client). La v3 Python a ete developpee dans la branche `feature/alex-workflow` (24 commits, 2026-03-25 au 2026-03-26) puis extraite comme depot autonome.
