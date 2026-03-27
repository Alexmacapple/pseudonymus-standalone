# Changelog

Historique des modifications de Pseudonymus standalone.
Issu de la branche `feature/alex-workflow` du depot `pseudonymus2`.

---

## v3.3.0 — 2026-03-27

Refonte UX de l'interface web, nouveaux formats, documentation restructurée.

### Interface web

- **Import fichier** : layout colonne unique (workflow séquentiel), tous formats supportés (JSON, CSV, TSV, XLSX, XLS, ODS, DOCX, ODT, PDF, TXT, MD)
- **Prévisualisation** : cards DSFR par fiche (10 enregistrements) au lieu d'un tableau, badges par type de champ
- **Mapping automatique** : fonctionne en mode upload (multipart) en plus du chemin local
- **Progression** : élément `<progress>` natif HTML accessible (RGAA) au lieu d'une div custom
- **Correspondances** : pagination DSFR conforme (`aria-current="page"`), compteur de résultats, callout vide avec liens, caption accessible
- **Documentation** : restructurée (CLI, interface web, glossaire en accordéon, FAQ en accordéon), sommaire DSFR avec ancres, grille col-8
- **Navigation** : menu réordonné par workflow (pseudo, import, scoring, correspondances, restauration, doc)
- **Page virtuelle** `#import-local` : deep link vers le mode chemin local sans entrée de menu
- **Tableaux** : `<caption>` sur tous les tableaux (RGAA 5.1), `fr-table--no-caption` pour éviter le chevauchement visuel
- **Boutons** : ordre prévisualiser (secondaire) puis lancer (primaire), bouton export CSV avec icône DSFR
- **DSFR** : `window.dsfr.start()` après chaque navigation pour initialiser les composants dans les pages masquées

### Formats

- **TXT** et **MD** : nouveaux formats en lecture et écriture (chargés comme un dict `{"texte": "..."}`)

### Serveur

- `/api/mapping/generate` accepte le multipart (upload de fichier) en plus du JSON (chemin local)
- `/api/pseudonymise` retourne `apercu_fiches` en mode dry-run (groupé par enregistrement)
- `deepcopy` des données avant traitement pour le dry-run upload (corrige l'aperçu vide)

### PRD

- Nouveau PRD : analyse de fichier avant traitement (`prd/PRD-analyse-fichier.md`)

---

## v3.2.1 — 2026-03-27

Correction prévisualisation et mapping automatique.

### Corrections

- **Prévisualisation** : aperçu structuré par champ du mapping (avant/après), résumé par type (nombre + exemples)
- **Serveur** : deepcopy des données avant traitement pour un vrai diff avant/après
- **Mapping automatique** : détection par nom de clé prioritaire sur la détection par valeur
  - `Report.Siret` correctement typé `siret` (plus `tel`)
  - `Report.Lastname` correctement typé `nom` (plus `prenom`)
  - Ajout détection SIRET (14 chiffres), SIREN (9 chiffres), GUID, Gender, PostalCode par nom de clé

---

## v3.2.0 — 2026-03-26

Parité fonctionnelle CLI / interface web.

### Nouvelles fonctionnalités

- **Dry-run (prévisualisation)** : bouton "Prévisualiser" sur la page Import, traite 100 enregistrements max sans écrire de fichier. Fonctionne en mode local et upload.
- **Traitement par lot (batch)** : nouvelle route `/api/pseudonymise-batch`, checkbox "Traiter un dossier entier" en mode local. Tableau récapitulatif par fichier avec gestion des erreurs.
- **ThreadingHTTPServer** : le serveur reste réactif pendant les traitements longs (remplace HTTPServer mono-thread).
- **Nommage CSV par fichier en batch** : `confidentiel/correspondances_{nom_fichier}.csv` (corrige l'écrasement du CLI).

### Tests

- 12 nouveaux tests dans `tests/test-v3.py` : dry-run local, batch, batch dry-run, erreurs 400/404
- Total : 104/104 (49 + 55), 0 FAIL

---

## v3.1.0 — 2026-03-26

Restructuration du dépôt pour standards git.

### Structure

- Tests déplacés dans `tests/` (test-options.py, test-v3.py)
- Documentation réorganisée : `prd/` (à faire) + `prd/done/` (terminés)
- Exemples renommés : `donnees-json-plat.json`, `donnees-json-imbrique.json`, `mapping-json-plat.json`, `mapping-json-imbrique.json`
- Placeholders génériques dans l'interface (plus de chemins utilisateur)

### Claude Code

- Init `.claude/` : agents (test-runner, audit-coherence), rules (projet)
- Ajout `AGENTS.md` : catalogue des sous-agents
- Ajout `CLAUDE.md` : instructions projet complètes

---

## v3.0.0 — 2026-03-26

Dépôt autonome, indépendant du monorepo `pseudonymus2`.

### Autonomie du dépôt

- Renommage `generique/` en `pseudonymus-standalone/`
- Internalisation complète : zéro dépendance vers `public/`, `virginie/`, `specifique/`
- Centralisation de `confidentiel/` à la racine du projet
- Ajout `requirements.txt`, `.gitignore`, `LICENSE` (GPL v3)
- Nettoyage de toutes les références à l'ancien nom `generique/`
- Données de test SignalConso synthétiques (`exemples/donnees-json-imbrique.json`)
- Documentation réorganisée dans `prd/`
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
