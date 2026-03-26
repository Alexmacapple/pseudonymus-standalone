# Pseudonymus standalone — Pseudonymisation multi-format

Script Python local de pseudonymisation/anonymisation de fichiers JSON, CSV, Excel, DOCX et PDF.
Iso-perimetre fonctionnel avec Pseudonymus v2 + interface web locale DSFR.

Traitement 100% local. Aucune donnee ne transite vers un service externe.

---

## Demarrage rapide

### Interface web (recommande)

```bash
# Lancer le serveur
python3 serveur.py

# Ouvrir http://127.0.0.1:8090 dans le navigateur
# Documentation integree : http://127.0.0.1:8090/#documentation
```

### Ligne de commande

```bash
# 1. Generer les donnees de reference (une seule fois)
python3 convertir-donnees.py

# 2. Generer un mapping automatiquement
python3 pseudonymise.py data/fichier.json --mapping-generate

# 3. Verifier le mapping genere, ajuster si besoin
# 4. Dry-run (test sur 100 enregistrements)
python3 pseudonymise.py data/fichier.json --mapping mapping.json --dry-run

# 5. Pseudonymiser
python3 pseudonymise.py data/fichier.json --mapping mapping.json --pseudo
```

---

## Formats supportes

| Format | Import | Export | Dependance |
|--------|--------|--------|------------|
| JSON | Oui | Oui | Aucune |
| CSV / TSV | Oui | Oui | Aucune |
| XLSX / XLS | Oui | Oui | `pip3 install openpyxl` |
| ODS | Oui | Oui | `pip3 install odfpy` |
| DOCX | Oui | Oui | `pip3 install python-docx` |
| ODT | Oui | Oui | `pip3 install odfpy` |
| PDF | Oui | Texte (.txt) | `pip3 install pdfplumber` |

Les dependances sont optionnelles : le script fonctionne sans si le format n'est pas utilise.

---

## Options CLI

| Option | Role |
|--------|------|
| `--mapping fichier.json` | Fichier de mapping (obligatoire sauf --mapping-generate) |
| `--pseudo` | Pseudonymisation reversible + CSV correspondances |
| `--anon` | Anonymisation irreversible |
| `--dry-run` | Test sur 100 enregistrements, pas de fichier ecrit |
| `--score-only` | Scoring RGPD sans pseudonymiser |
| `--fort` | Mode fort : prenoms isoles, patronymes prefixe, propagation, majuscules |
| `--nlp` | Pre-filtre spaCy fr (optionnel, +2-5% de detection) |
| `--tech` | Regex techniques : IPv4/v6, MAC, JWT, API keys, GPS, plaques |
| `--mapping-generate` | Inspecte le fichier et propose un mapping squelette |
| `--input-dir dossier/` | Traite tous les .json d'un dossier |
| `--chunk-size N` | Streaming par paquets de N enregistrements (fichiers > 2 Go, necessite `pip3 install ijson`) |

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
| Restauration | `/#restauration` | Depseudonymiser avec les correspondances |
| Import fichier | `/#import-fichier` | Traiter un fichier complet (upload ou chemin local) |
| Scoring RGPD | `/#scoring-rgpd` | Evaluer le risque avant pseudonymisation |
| Documentation | `/#documentation` | Glossaire, guide, FAQ, reference technique |

### API

| Route | Methode | Fonction |
|-------|---------|----------|
| `/api/pseudonymise-texte` | POST | Pseudonymiser du texte brut |
| `/api/pseudonymise` | POST | Pseudonymiser un fichier (upload) |
| `/api/pseudonymise-local` | POST | Pseudonymiser via chemin local (gros fichiers) |
| `/api/depseudonymise` | POST | Restaurer les jetons |
| `/api/score` | POST | Scoring RGPD |
| `/api/mapping/generate` | POST | Generation automatique de mapping |
| `/api/stats` | GET | Statistiques dictionnaires |
| `/api/health` | GET | Sante du serveur |

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

### JSON imbrique (notation pointee + unwrap)

```json
{
  "description": "Reclamations SignalConso",
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

| Champ | Role |
|-------|------|
| `champs_sensibles` | Champs a pseudonymiser avec leur type et prefixe de jeton |
| `texte_libre` | Champs texte a scanner par les regex + dictionnaires |
| `lookup_noms` | Champs contenant le prenom/nom (pour lookup dans le texte libre) |
| `whitelist` | Mots a ne jamais pseudonymiser (noms d'entreprise, etc.) |
| `blacklist` | Mots a toujours forcer en pseudonymisation |
| `structure.unwrap` | JSON stringifie a depaqueter avant traitement |

---

## Depseudonymisation

```bash
python3 depseudonymise.py data/fichier_PSEUDO.json \
    --correspondances confidentiel/correspondances.csv
```

Produit `data/fichier_RESTAURE.json` avec les valeurs originales.

---

## Donnees de reference

Generees par `convertir-donnees.py` depuis les fichiers JS de Pseudonymus v2.

| Fichier | Contenu | Entrees |
|---------|---------|---------|
| `data/noms.json` | Patronymes INSEE | 884 314 |
| `data/prenoms.json` | Prenoms INSEE (M+F) | 169 244 |
| `data/stopwords-capitalises.json` | Mots capitalises a ne jamais pseudonymiser | 242 |
| `data/stopwords-minuscules.json` | Mots minuscules a ne jamais pseudonymiser | 151 |
| `data/majuscules-garder.json` | Mots en majuscules a preserver | 94 |
| `data/villes-france.json` | Top villes francaises | 97 |
| `data/mots-organisations.json` | Mots-cles organisations (SA, SARL...) | 38 |
| `data/contexte-institution.json` | Mots de contexte institutionnel | 60 |
| `data/acronymes-garder.json` | Acronymes a preserver | 12 |

---

## Tests

```bash
# Tests moteur (v1+v2) : 49 tests
python3 test-options.py

# Tests v3 (formats, serveur, API) : 43 tests
python3 test-v3.py
```

92 tests au total, zero echec.

---

## Arborescence

```
pseudonymus-standalone/
  pseudonymise.py        Moteur principal (CLI + API)
  depseudonymise.py      Restauration
  formats.py             Parseurs multi-format (CSV, XLSX, ODS, DOCX, ODT, PDF)
  serveur.py             Serveur web local (port 8090)
  convertir-donnees.py   Regeneration des donnees statiques
  test-options.py        Tests moteur (49 tests)
  test-v3.py             Tests v3 (43 tests)
  requirements.txt       Dependances optionnelles
  LICENSE                GPL v3
  README.md              Ce fichier
  .gitignore             Exclusions Python, OS, donnees sensibles
  data/                  Dictionnaires et stopwords
  exemples/              Exemples de mappings et donnees de test
  confidentiel/          Correspondances CSV (gitignore)
  interface/             Frontend DSFR
    index.html           6 pages (pseudo, correspondances, restauration, import, scoring, doc)
    app.js               Logique frontend
    style.css            Styles complementaires
    dsfr/                CSS, JS et polices DSFR en local
```

---

## Securite

- Le serveur ecoute sur `127.0.0.1` uniquement (pas d'acces reseau)
- Le fichier `confidentiel/correspondances.csv` contient les donnees en clair
- Permissions `chmod 600` appliquees automatiquement
- Gitignored (fichier `.gitignore` cree automatiquement)
- Ne jamais partager les correspondances avec un service externe

---

## Performance

| Volume | Mode | Temps |
|--------|------|-------|
| 31 891 enregistrements (118 Mo) | Standard | ~1 minute |
| 31 891 enregistrements (118 Mo) | Fort | ~5 minutes |
| > 2 Go | `--chunk-size 5000` | Streaming, memoire constante |
