# Héritage du dépôt original Pseudonymus v2

Ce document trace ce qui a été repris du dépôt original et ce qui a été modifié ou ajouté.

**Dépôt source** : https://forge.apps.education.fr/vibe-edu/pseudonymus2
**Commit de référence** : `a39831c` (dernier commit du dépôt original au moment du fork)
**Date du fork** : 2025-03-25

---

## Ce qui a été repris tel quel

### L'application web Pseudonymus v2

Le dossier `public/` est intégralement celui du dépôt original. Rien n'a été modifié.

| Fichier | Rôle |
|---------|------|
| `public/index.html` | Interface utilisateur (onglets pseudonymisation, correspondances, restauration) |
| `public/assets/css/style.css` | Styles de l'application (glassmorphism) |
| `public/assets/css/all.min.css` | Font Awesome local |
| `public/assets/js/app.js` | Moteur de pseudonymisation (2062 lignes, 90 Ko) |
| `public/assets/js/matomo-init.js` | Suivi Matomo LaForgeÉdu |
| `public/assets/js/vendor/` | Bibliothèques tierces (PDF.js, Mammoth, SheetJS, jsPDF, Compromise) |
| `public/assets/js/vendor/noms.js` | Dictionnaire de noms INSEE (218k+ entrées) |
| `public/assets/js/vendor/prenoms-fr.js` | Dictionnaire de prénoms français |
| `public/assets/img/logo.ico` | Favicon |
| `public/assets/webfonts/` | Polices Font Awesome (woff2) |

### Les fichiers racine

| Fichier | Rôle |
|---------|------|
| `README.md` | Documentation du projet original |
| `CHANGELOG` | Journal des modifications |
| `licence.lic` | Licence GNU GPL v3.0 |
| `.gitlab-ci.yml` | CI GitLab Pages |
| `.vscode/` | Configuration VS Code |

---

## Ce qui a été repris et adapté

### Les regex de détection (`app.js` → `pseudonymise-json.py`)

Le coeur du projet original est le moteur regex dans `public/assets/js/app.js`. Notre script Python en reprend la logique de détection, adaptée au contexte batch JSON.

#### Regex reprises (app.js lignes 11-84)

| Regex JS (app.js) | Regex Python | Modifications |
|--------------------|-------------|---------------|
| `RX.email` (l.16) | `RX_EMAIL` | Aucune — syntaxe identique |
| `RX_SENSITIVE.emailObfuscated` (l.69) | `RX_EMAIL_OBFUSCATED` | Aucune |
| `RX_SENSITIVE.nir` (l.56) | `RX_NIR` | Lookbehind `(?<!\d)` : en JS il précède un pattern variable, en Python le lookbehind doit être de taille fixe. Fonctionne ici car `\d` = 1 char |
| `RX_SENSITIVE.iban` (l.58) | `RX_IBAN` | Aucune |
| `RX_SENSITIVE.cb` (l.60) | `RX_CB` | Aucune sur la regex. Validation Luhn modifiée (voir ci-dessous) |
| `RX.tel` (l.18) | `RX_TEL` | Aucune |
| `RX_SENSITIVE.telFuzzy` (l.74) | `RX_TEL_FUZZY` | Lookbehind adapté (même cas que NIR) |
| `RX.voieNum` (l.20) | `RX_VOIE_NUM` | Aucune |

#### Regex non reprises

| Regex JS | Raison de l'exclusion |
|----------|----------------------|
| `RX.voieSans` (l.21) | 37% de faux positifs sur du texte courant (« allée dans un magasin ») |
| `RX.salutation` (l.24) | Trop de faux positifs dans les réclamations (« Bonjour Marie » où Marie n'est pas le déclarant) |
| `RX.titre` (l.25) | Idem — « Monsieur Dupont » dans le texte libre peut être un tiers |
| `RX.prenomNom` (l.27) | Remplacé par le lookup direct Firstname/Lastname (plus précis) |
| `RX.prenomNomMaj` (l.26) | Idem |
| `RX.majLong` (l.29) | Spécifique au mode « Complet » de Pseudonymus, non pertinent en batch JSON |
| `RX.cp` (l.22) | Les codes postaux dans le texte libre génèrent trop de faux positifs (numéros de commande). Le CP structuré est traité en Phase 1 |
| `RX.ville` (l.23) | Dépend de `RX.cp`, non repris |
| `RX.url` (l.19) | Les URLs dans les réclamations sont celles des entreprises, pas des données personnelles |
| `RX_SENSITIVE.ipv6/ip/mac/jwt/apiKey` (l.43-51) | Non pertinent dans des réclamations consommateurs |
| `RX_SENSITIVE.plaque` (l.81) | Rare dans les réclamations, risque de faux positifs |
| `RX_SENSITIVE.numFiscal` (l.83) | Collision avec d'autres séquences de 13 chiffres |
| `RX_SENSITIVE.dateNaiss` (l.77) | Contextuel (« né le »), peu fréquent dans les réclamations |
| `RX_SENSITIVE.gps` (l.79) | Non pertinent |
| `RX_SENSITIVE.cvv` (l.62) | Contextuel, très rare |
| `RX_SENSITIVE.siret` (l.64) | Les SIRET identifient des entreprises, pas des personnes. Traités comme non-sensibles |

#### Validateurs repris (app.js lignes 89-111)

| Validateur JS | Validateur Python | Modifications |
|--------------|-------------------|---------------|
| `VALIDATORS.luhn` (l.90-101) | `luhn_check()` | Exclusion ajoutée : les séquences de 9 chiffres (SIREN) et 14 chiffres (SIRET) sont exclues avant le test Luhn, car elles passent souvent Luhn par coïncidence |
| `VALIDATORS.nir` (l.103-110) | `nir_check()` | Identique — validation structure (longueur 13, mois 1-12) |

#### Éléments non repris de app.js

| Élément | Lignes app.js | Raison |
|---------|---------------|--------|
| `RiskScorer` | l.116+ | Scoring RGPD inutile en batch (on pseudonymise tout) |
| Dictionnaires INSEE (`noms.js`, `prenoms-fr.js`) | vendor/ | Non nécessaires — le lookup direct utilise le Firstname/Lastname de chaque enregistrement, pas un dictionnaire global |
| Interface DOM | l.500+ | Application web, non pertinent pour un script CLI |
| Import/Export (PDF, DOCX, etc.) | l.1500+ | Le script travaille sur du JSON, pas sur des fichiers bureautiques |
| Système d'onglets, tableau de correspondances UI | l.800+ | Remplacé par le CSV de correspondances |

---

## Ce qui a été ajouté (n'existe pas dans le dépôt original)

| Élément | Fichier | Raison |
|---------|---------|--------|
| Script de pseudonymisation batch | `pseudonymise-json.py` | Le dépôt original ne gère que du texte unitaire dans le navigateur |
| Mode anonymisation (`--anon`) | `pseudonymise-json.py` | Remplacement irréversible, pas dans l'original |
| Mode dry-run (`--dry-run`) | `pseudonymise-json.py` | Test sur échantillon avant le traitement complet |
| Lookup direct noms | `pseudonymise-json.py` | L'original utilise les dictionnaires INSEE. Le script utilise le Firstname/Lastname de chaque enregistrement pour un matching plus précis |
| Stratégie noms courts | `pseudonymise-json.py` | Prénoms < 4 lettres combinés avec le nom uniquement. Pas dans l'original |
| Exclusion SIRET dans Luhn | `pseudonymise-json.py` | L'original ne filtre pas les longueurs 9/14 |
| Gestion erreurs + progression | `pseudonymise-json.py` | Skip + log stderr, compteur `[12000/31891]` |
| Table de correspondances CSV | `pseudonymise-json.py` | L'original maintient la table en mémoire navigateur |
| Scripts de vérification | `verif-sample.py`, `verif-complet.py` | N'existent pas dans l'original |
| Suite de tests | `test-options.py` | N'existe pas dans l'original |
| Documentation projet | `alex/` | PRD, guide utilisateur, retour pédagogique |
| `.gitignore` | racine | Exclusion des données sensibles |

---

## Résumé

```
Dépôt original (Pseudonymus v2)
├── Interface web (HTML/CSS/JS)          → Conservée intacte
├── Regex de détection (app.js l.11-84)  → 8 reprises, 16 exclues
├── Validateurs (app.js l.89-111)        → 2 repris (Luhn modifié)
├── Dictionnaires INSEE (noms/prénoms)   → Non repris (lookup direct)
├── RiskScorer, Interface DOM, Import/Export → Non repris
└── Licence GNU GPL v3.0                 → Héritée

Ajouts (branche feature/alex-workflow)
├── pseudonymise-json.py                 → Script batch Python
├── verif-sample.py                      → Vérification rapide
├── verif-complet.py                     → Audit automatisé
├── test-options.py                      → 35 tests
├── alex/                                → Documentation complète
└── .gitignore                           → Sécurité données
```
