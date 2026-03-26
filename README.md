# Pseudonymus standalone — Pseudonymisation multi-format

Script Python local de pseudonymisation/anonymisation de fichiers JSON, CSV, Excel, DOCX et PDF.
Iso-périmètre fonctionnel avec Pseudonymus v2 + interface web locale DSFR.

Traitement 100 % local. Aucune donnée ne transite vers un service externe.

---

## Démarrage rapide

### Interface web (recommandé)

```bash
# Lancer le serveur
python3 serveur.py

# Ouvrir http://127.0.0.1:8090 dans le navigateur
# Documentation intégrée : http://127.0.0.1:8090/#documentation
```

### Ligne de commande

```bash
# 1. Générer un mapping automatiquement
python3 pseudonymise.py fichier.json --mapping-generate

# 2. Vérifier le mapping généré, ajuster si besoin
# 3. Dry-run (test sur 100 enregistrements)
python3 pseudonymise.py fichier.json --mapping mapping.json --dry-run

# 4. Pseudonymiser
python3 pseudonymise.py fichier.json --mapping mapping.json --pseudo
```

---

## Formats supportés

| Format | Import | Export | Dépendance |
|--------|--------|--------|------------|
| JSON | Oui | Oui | Aucune |
| CSV / TSV | Oui | Oui | Aucune |
| XLSX / XLS | Oui | Oui | `pip3 install openpyxl` |
| ODS | Oui | Oui | `pip3 install odfpy` |
| DOCX | Oui | Oui | `pip3 install python-docx` |
| ODT | Oui | Oui | `pip3 install odfpy` |
| PDF | Oui | Texte (.txt) | `pip3 install pdfplumber` |

Les dépendances sont optionnelles : le script fonctionne sans si le format n'est pas utilisé.

---

## Options CLI

| Option | Rôle |
|--------|------|
| `--mapping fichier.json` | Fichier de mapping (obligatoire sauf --mapping-generate) |
| `--pseudo` | Pseudonymisation réversible + CSV correspondances |
| `--anon` | Anonymisation irréversible |
| `--dry-run` | Test sur 100 enregistrements, pas de fichier écrit |
| `--score-only` | Scoring RGPD sans pseudonymiser |
| `--fort` | Mode fort : prénoms isolés, patronymes préfixe, propagation, majuscules |
| `--nlp` | Pré-filtre spaCy fr (optionnel, +2-5 % de détection) |
| `--tech` | Regex techniques : IPv4/v6, MAC, JWT, API keys, GPS, plaques |
| `--mapping-generate` | Inspecte le fichier et propose un mapping squelette |
| `--input-dir dossier/` | Traite tous les .json d'un dossier |
| `--chunk-size N` | Streaming par paquets de N enregistrements (fichiers > 2 Go, nécessite `pip3 install ijson`) |

---

## Interface web DSFR

```bash
python3 serveur.py --port 8090
```

Serveur local sur http://127.0.0.1:8090 avec 6 pages :

| Page | URL | Fonction |
|------|-----|----------|
| Pseudonymisation | `/#pseudonymisation` | Coller du texte et pseudonymiser |
| Correspondances | `/#correspondances` | Table jeton/valeur avec recherche et export CSV |
| Restauration | `/#restauration` | Dépseudonymiser avec les correspondances |
| Import fichier | `/#import-fichier` | Traiter un fichier complet (upload ou chemin local) |
| Scoring RGPD | `/#scoring-rgpd` | Évaluer le risque avant pseudonymisation |
| Documentation | `/#documentation` | Glossaire, guide, FAQ, référence technique |

### API

| Route | Méthode | Fonction |
|-------|---------|----------|
| `/api/pseudonymise-texte` | POST | Pseudonymiser du texte brut |
| `/api/pseudonymise` | POST | Pseudonymiser un fichier (upload) |
| `/api/pseudonymise-local` | POST | Pseudonymiser via chemin local (gros fichiers) |
| `/api/depseudonymise` | POST | Restaurer les jetons |
| `/api/score` | POST | Scoring RGPD |
| `/api/mapping/generate` | POST | Génération automatique de mapping |
| `/api/stats` | GET | Statistiques dictionnaires |
| `/api/health` | GET | Santé du serveur |

---

## Fichier de mapping

### JSON plat

```json
{
  "description": "Registre clients",
  "champs_sensibles": {
    "nom": {"type": "nom", "jeton": "NOM"},
    "prenom": {"type": "prenom", "jeton": "PRENOM"},
    "email": {"type": "email", "jeton": "EMAIL"},
    "telephone": {"type": "tel", "jeton": "TEL"},
    "code_postal": {"type": "cp", "jeton": "CP"},
    "id": {"type": "id", "jeton": "ID"}
  },
  "texte_libre": ["commentaire", "notes"],
  "lookup_noms": {"prenom": "prenom", "nom": "nom"},
  "whitelist": ["ORANGE", "SFR"],
  "blacklist": []
}
```

### JSON imbriqué (notation pointée + unwrap)

```json
{
  "description": "Réclamations SignalConso",
  "structure": {
    "unwrap": {
      "field": "RCLMFicheReportJsonSC",
      "parse": "json_string"
    }
  },
  "champs_sensibles": {
    "DOAR_IDENT": {"type": "id", "jeton": "ID"},
    "Report.Firstname": {"type": "prenom", "jeton": "PRENOM"},
    "Report.Lastname": {"type": "nom", "jeton": "NOM"},
    "Report.Email": {"type": "email", "jeton": "EMAIL"}
  },
  "texte_libre": [
    "Report.Question",
    "Report.Details[].Value"
  ],
  "lookup_noms": {"prenom": "Report.Firstname", "nom": "Report.Lastname"},
  "whitelist": ["ORANGE"],
  "blacklist": []
}
```

### Champs du mapping

| Champ | Rôle |
|-------|------|
| `champs_sensibles` | Champs à pseudonymiser avec leur type et préfixe de jeton |
| `texte_libre` | Champs texte à scanner par les regex + dictionnaires |
| `lookup_noms` | Champs contenant le prénom/nom (pour lookup dans le texte libre) |
| `whitelist` | Mots à ne jamais pseudonymiser (noms d'entreprise, etc.) |
| `blacklist` | Mots à toujours forcer en pseudonymisation |
| `structure.unwrap` | JSON stringifié à dépaqueter avant traitement |

---

## Dépseudonymisation

```bash
python3 depseudonymise.py fichier_PSEUDO.json \
    --correspondances confidentiel/correspondances.csv
```

Produit `fichier_RESTAURE.json` avec les valeurs originales.

---

## Données de référence

Les dictionnaires sont livrés dans `data/` et prêts à l'emploi. Le script `convertir-donnees.py` ne régénère que les 7 fichiers statiques (stopwords, villes, organisations, etc.). Les fichiers `noms.json` et `prenoms.json` sont des données de référence immuables.

| Fichier | Contenu | Entrées |
|---------|---------|---------|
| `data/noms.json` | Patronymes INSEE | 884 314 |
| `data/prenoms.json` | Prénoms INSEE (M+F) | 169 244 |
| `data/stopwords-capitalises.json` | Mots capitalisés à ne jamais pseudonymiser | 242 |
| `data/stopwords-minuscules.json` | Mots minuscules à ne jamais pseudonymiser | 151 |
| `data/majuscules-garder.json` | Mots en majuscules à préserver | 94 |
| `data/villes-france.json` | Top villes françaises | 97 |
| `data/mots-organisations.json` | Mots-clés organisations (SA, SARL...) | 38 |
| `data/contexte-institution.json` | Mots de contexte institutionnel | 60 |
| `data/acronymes-garder.json` | Acronymes à préserver | 12 |

---

## Tests

```bash
# Tests moteur : 49 tests
python3 tests/test-options.py

# Tests formats, serveur, API : 43 tests
python3 tests/test-v3.py
```

92 tests au total, zéro échec.

---

## Arborescence

```
pseudonymus-standalone/
  pseudonymise.py        Moteur principal (CLI + API)
  depseudonymise.py      Restauration
  formats.py             Parseurs multi-format (CSV, XLSX, ODS, DOCX, ODT, PDF)
  serveur.py             Serveur web local (port 8090)
  convertir-donnees.py   Régénération des données statiques
  tests/
    test-options.py      Tests moteur (49 tests)
    test-v3.py           Tests v3 (43 tests)
  requirements.txt       Dépendances optionnelles
  LICENSE                GPL v3
  CHANGELOG.md           Historique des versions
  CLAUDE.md              Instructions projet pour Claude Code
  README.md              Ce fichier
  .gitignore             Exclusions Python, OS, données sensibles
  data/                  Dictionnaires et stopwords
  exemples/              Exemples de mappings et données de test
  confidentiel/          Correspondances CSV (gitignoré)
  interface/             Frontend DSFR
    index.html           6 pages (pseudo, correspondances, restauration, import, scoring, doc)
    app.js               Logique frontend
    style.css            Styles complémentaires
    dsfr/                CSS, JS et polices DSFR en local
  prd/                   PRD à faire
    done/                PRD terminés + documentation
```

---

## Sécurité

- Le serveur écoute sur `127.0.0.1` uniquement (pas d'accès réseau)
- Le fichier `confidentiel/correspondances.csv` contient les données en clair
- Permissions `chmod 600` appliquées automatiquement
- Gitignoré (fichier `.gitignore` créé automatiquement)
- Ne jamais partager les correspondances avec un service externe

---

## Origine et crédits

Ce projet s'est fortement inspiré de [Pseudonymus v2](https://forge.apps.education.fr/vibe-edu/pseudonymus2/), application JavaScript de pseudonymisation côté client développée sur la Forge des Communs Numériques Éducatifs.

Pseudonymus standalone en reprend les dictionnaires (patronymes INSEE, prénoms) et la logique de détection par regex, mais constitue une réécriture complète :

- Portage en **Python** avec CLI complète (modes pseudo, anon, dry-run, scoring, batch, streaming)
- Interface web **DSFR** (Design System de l'État) avec serveur local
- Gestion native du **JSON structuré** : notation pointée, unwrap de JSON imbriqué, mappings configurables
- Support **multi-format** : CSV, XLSX, ODS, DOCX, ODT, PDF

