# PRD : Pseudonymisation générique multi-JSON

**Date** : 2025-03-25
**Derniere mise a jour** : 2026-03-25
**Statut** : v1 livree, v2 livree, v3 livree
**Auteur** : Alex
**Objectif** : iso-perimetre fonctionnel avec Pseudonymus v2 (`app.js`, 2062 lignes) + prise en charge de JSON potentiellement lourds.

---

## Contexte

Pseudonymus v2 est une appli navigateur qui pseudonymise du texte. On porte **toute sa logique** dans un script Python batch pour traiter des JSON volumineux en local.

**Contrainte** : zéro donnée sensible ne transite vers un service externe.

**Approche** : trois versions incrémentales.

| Version | Périmètre |
|---------|-----------|
| v1 | Iso-fonctionnel avec l'original sur la détection texte + JSON plat |
| v2 | JSON complexe + multi-fichiers + streaming gros fichiers |
| v3 | Multi-format (CSV, Excel, DOCX, PDF) + interface web locale |

---

## Données de référence à porter

Tous les fichiers de référence sont convertis depuis les sources JS et stockés dans `generique/data/`.

### Dictionnaires

| Source JS | Entrées | Cible Python |
|-----------|---------|-------------|
| `vendor/noms.js` (`PATRONYMES`) | 884 314 | `data/noms.json` |
| `vendor/prenoms-fr.js` (masculins) | 87 642 | `data/prenoms.json` |
| `vendor/prenoms-fr.js` (féminins) | 96 184 | `data/prenoms.json` |

### Stopwords (anti-faux-positifs)

Extraits depuis `app.js` lignes 235-301. Indispensables pour éviter que les dictionnaires INSEE matchent des mots courants.

| Source JS | Entrées | Cible Python | Rôle |
|-----------|---------|-------------|------|
| `STOPWORDS_CAPITALISES` (l.239-273) | ~150 mots | `data/stopwords-capitalises.json` | Mots capitalisés à ne jamais pseudonymiser (« Bonjour », « Conseil », « Direction », « Pierre »...) |
| `STOPWORDS_MINUSCULES` (l.276-301) | ~100 mots | `data/stopwords-minuscules.json` | Mots minuscules à ne jamais pseudonymiser (« le », « est », « personne », « nom »...) |
| `MAJUSCULES_A_GARDER` (l.303-317) | ~60 mots | `data/majuscules-garder.json` | Mots en majuscules à ne jamais pseudonymiser (« FRANCE », « PARIS », « NORD », « PDF »...) |

### Villes et organisations

| Source JS | Entrées | Cible Python | Rôle |
|-----------|---------|-------------|------|
| `VILLES_FRANCE` (l.341-353) | ~80 villes | `data/villes-france.json` | Top villes françaises — détection `[VILLE]` dans le texte |
| `MOTS_CLEFS_ORGANISATION` (l.355-360) | ~30 mots | `data/mots-organisations.json` | SA, SARL, ASSOCIATION... — détection `[ORGANISATION]` |
| `CONTEXTE_INSTITUTION` (l.325-339) | ~50 mots | `data/contexte-institution.json` | école, collège, clinique... — filtre anti-faux-positifs |
| `ACRONYMES_A_GARDER` (l.235-237) | ~12 mots | `data/acronymes-garder.json` | DRANE, EAFC, PDF... — mots techniques à préserver |

### Regex de contexte (portées directement dans le code, pas en fichier data/)

| Source JS | Rôle |
|-----------|------|
| `CONTEXTE_NB_NEGATIF` (l.363) | Empêche la pseudonymisation de nombres précédés de « n° », « ref. », « page », « kg », « € »... |
| `CONTEXTE_NB_NEGATIF_SUITE` (l.364) | Empêche la pseudonymisation de nombres suivis de « kg », « € », « % », « degrés »... |

Ces deux regex sont portées directement dans le code Python (pas en fichier JSON car ce sont des patterns, pas des listes).

### Script de conversion

`generique/convertir-donnees.py` — extrait toutes ces données depuis les fichiers JS et les sérialise en JSON Python.

---

## Regex complètes

Toutes les regex de `app.js` portées en Python, organisées par phase.

### Regex coeur (toujours actives)

| Regex | Source app.js | Détecte | Jeton |
|-------|-------------|---------|-------|
| `RX_EMAIL` | l.16 | Emails standards | `[EMAIL]` |
| `RX_EMAIL_OBFUSCATED` | l.69 | Emails obfusqués (`[at]`, `(at)`) | `[EMAIL]` |
| `RX_MAILTO` | l.71 | Liens mailto | `[EMAIL]` |
| `RX_EMAIL_AVEC` | l.13 | « De: Marie <email> » | Préserve le contexte |
| `RX_EMAIL_ESPACE` | l.15 | Emails avec espaces | `[EMAIL]` |
| `RX_NIR` | l.56 | Numéro de sécurité sociale + validation | `[NIR]` |
| `RX_IBAN` | l.58 | IBAN | `[IBAN]` |
| `RX_CB` | l.60 | Cartes bancaires + validation Luhn (excl. SIREN/SIRET 9/14 chiffres) | `[CB]` |
| `RX_CVV` | l.62 | CVV contextuel (« CVV 123 ») | `[CVV]` |
| `RX_SIRET` | l.64 | SIRET/SIREN dans le texte + validation Luhn | `[SIRET]` / `[SIREN]` |
| `RX_NUM_FISCAL` | l.83 | Numéro fiscal (13 chiffres commençant par 0-3) | `[ID_FISCAL]` |
| `RX_TEL` | l.18 | Téléphones français | `[TEL]` |
| `RX_TEL_FUZZY` | l.74 | Téléphones format flou (+33, 0033) | `[TEL]` |
| `RX_TEL_PREFIXE` | l.17 | « TEL : 06 ... » | `[TEL]` |
| `RX_URL` | l.19 | URLs (http, https, www) | `[URL]` |
| `RX_VOIE_NUM` | l.20 | Adresses numérotées (« 43 rue Pierre Brossolette ») | `[VOIE]` |
| `RX_SALUTATION` | l.24 | « Bonjour Marie », « Cher Monsieur » | `[PERSONNE_X]` |
| `RX_TITRE` | l.25 | « M. Dupont », « Mme Martin » | `[PERSONNE_X]` |
| `RX_PRENOM_NOM_MAJ` | l.26 | « Pierre DUPONT » | `[PERSONNE_X]` |
| `RX_PRENOM_NOM` | l.27 | « Pierre Dupont » | `[PERSONNE_X]` |

### Regex mode fort (activées par `--fort`)

| Regex | Source app.js | Détecte | Jeton |
|-------|-------------|---------|-------|
| `RX_VOIE_SANS` | l.21 | Adresses sans numéro (« rue Victor Hugo ») | `[VOIE]` |
| `RX_CP` | l.22 | Codes postaux 5 chiffres dans le texte | `[CP]` |
| `RX_VILLE` | l.23 | Ville après un code postal | `[VILLE]` |
| `RX_DATE_NAISS` | l.77 | « Né le 15/03/1990 » | `[DATE_NAISSANCE]` |
| `RX_GPS` | l.79 | Coordonnées GPS décimales | `[GPS]` |
| `RX_PLAQUE` | l.81 | Plaques d'immatriculation | `[PLAQUE_IMMAT]` |
| `RX_PRENOM_ISOLE` | l.467 | Prénoms isolés capitalisés vérifiés par dictionnaire | `[PERSONNE_X]` |
| `RX_PRENOM_ISOLE_MINUSC` | l.469 | Prénoms isolés en minuscule vérifiés par dictionnaire | `[PERSONNE_X]` |
| `RX_PREFIXES` | l.1067 | Patronymes à préfixe (BEN, EL, AL, AIT, ABDEL) | `[PERSONNE_X]` |
| `RX_MAJ_LONG` | l.29 | Mots en majuscules >= 2 lettres (noms de famille isolés) | `[PERSONNE_X]` |

### Regex techniques (activées par `--tech`)

| Regex | Source app.js | Détecte | Jeton |
|-------|-------------|---------|-------|
| `RX_IPV4` | l.45 | Adresses IPv4 | `[IPV4]` |
| `RX_IPV6` | l.43 | Adresses IPv6 | `[IPV6]` |
| `RX_MAC` | l.47 | Adresses MAC | `[MAC_ADDR]` |
| `RX_JWT` | l.49 | Tokens JWT | `[JWT_TOKEN]` |
| `RX_API_KEY` | l.51 | Clés API (sk_, pk_, api_) | `[API_KEY]` |

### Regex détection organisations/villes

| Regex | Source app.js | Détecte | Jeton |
|-------|-------------|---------|-------|
| `RX_ORGA_AGRESSIF` | l.369 | « Société Générale SA », « Groupe Renault » | `[ORGANISATION]` |
| `RX_ORGA_MOTS` | l.367 | Mots-clés org. isolés (SA, SARL, ASSOCIATION...) | `[ORGANISATION]` |
| `RX_VILLES` | l.366 | Top 80 villes françaises | `[VILLE]` |
| `RX_VILLE_COMPOSEE` | l.321 | Villes composées (NEUVILLE SUR ESCAUT) | Préservées (pas pseudonymisées) |

---

## Logique métier à porter

Au-delà des regex, `app.js` contient de la logique métier que nos scripts doivent reproduire.

### 1. Normalisation des personnes (app.js l.191-202)

L'original normalise les noms pour détecter les doublons :
- Suppression des titres (M., Mme, Monsieur...)
- Suppression des jetons existants
- Ne garde que les lettres, tirets, apostrophes
- Si 2 mots sans apostrophe : tri alphabétique (« Dupont Marie » = « Marie Dupont »)
- Tout en minuscule

Notre `TokenTable` doit implémenter cette normalisation pour que la même personne obtienne le même jeton quelle que soit l'ordre prénom/nom.

### 2. Contexte institutionnel (app.js l.375-385)

Fonction `estContexteInstitution()` : vérifie si un mot capitalisé est adjacent à un mot de contexte institutionnel (école, collège, clinique, bibliothèque...). Si oui, ce n'est pas un nom de personne.

Exemple : « école Victor Hugo » → Victor Hugo n'est pas pseudonymisé. « Bonjour Victor Hugo » → pseudonymisé.

### 3. Contexte numérique négatif (app.js l.363-364)

Les regex `CONTEXTE_NB_NEGATIF` et `CONTEXTE_NB_NEGATIF_SUITE` empêchent de pseudonymiser des nombres précédés/suivis de contexte non personnel : « n° 12345 », « 150 kg », « page 42 », « 25 € ».

### 4. Propagation heuristique (app.js l.1107-1140, mode fort)

Si un `[PERSONNE_X]` est adjacent à un mot en majuscules, ce mot est absorbé dans le même jeton. Exemple : « [PERSONNE_1] DUPONT » → DUPONT est ajouté à PERSONNE_1. Boucle max 3 itérations.

### 5. Prénoms composés à préfixe (app.js l.1065-1077, mode fort)

Regex dédiée pour les patronymes BEN AHMED, EL KHATIB, AIT MOHAND, ABDEL NASSER. Combine le préfixe avec le(s) mot(s) suivant(s).

### 6. Vérification prénoms via dictionnaire (app.js l.405-425)

Fonction `estPrenomConnu()` : vérifie si un mot est un prénom français connu via le dictionnaire INSEE (183k prénoms). Normalisation sans accents pour le matching. Cache de performance.

### 7. Vérification patronymes via dictionnaire (app.js l.431-435)

Fonction `estPatronymeIdentifie()` : vérifie si un mot en majuscules est un patronyme connu via le dictionnaire INSEE (884k noms).

### 8. Détection NLP (app.js l.441-464, remplacé par spaCy fr)

L'original utilise Compromise.js (librairie NLP anglophone) comme pré-filtre : il propose des candidats « personne » que les dictionnaires INSEE valident ensuite. Compromise est redondant avec nos regex + dictionnaires sur le français, mais le principe du pré-filtre NLP attrape ~2-5% de noms supplémentaires (noms isolés sans contexte, titres non listés).

**Décision** : remplacer Compromise.js par spaCy `fr_core_news_sm` (modèle NER entraîné sur du français, nettement meilleur que Compromise sur notre langue). Activé par `--nlp`, optionnel — le script fonctionne sans.

**Dépendance optionnelle** : `pip install spacy && python -m spacy download fr_core_news_sm` (~100 Mo).

**Fonctionnement `--nlp`** :
1. spaCy analyse le texte et détecte les entités de type `PER` (personne)
2. Chaque entité détectée est validée : longueur >= 3, commence par une majuscule, pas dans les stopwords
3. Les entités validées sont pseudonymisées comme `[PERSONNE_X]`
4. Le reste du pipeline (regex, dictionnaires) s'applique normalement après

**Sans `--nlp`** : les dictionnaires INSEE + regex couvrent ~95% des cas. Le `--nlp` ajoute ~2-5% de détection sur les noms hors dictionnaire et les noms isolés sans contexte regex.

### 9. Scoring RGPD (app.js l.116-150)

| Catégorie | Points |
|-----------|--------|
| `direct` (noms, emails, tél) | 3 |
| `finance` (CB, IBAN, NIR, fiscal) | 5 |
| `tech` (IP, JWT, MAC) | 2 |
| `indirect` (dates, villes, adresses) | 1 |

Niveaux : NUL (0), FAIBLE (<10), MODÉRÉ (<50), ÉLEVÉ (<100), CRITIQUE (>=100).

### 10. Dépseudonymisation (app.js l.1860+)

L'original a un onglet de restauration qui remplace les jetons par les valeurs originales. Notre équivalent : un script `depseudonymise.py` qui lit le JSON pseudonymisé + le CSV de correspondances et produit le JSON original.

---

## Ordre d'application (pipeline de l'original)

L'original applique les traitements dans cet ordre précis (`pseudonymiserBloc()`, l.797-1154). Notre script doit respecter ce même ordre.

```
1. Protection tokens existants (ne pas re-pseudonymiser)
2. Pré-analyse NLP spaCy (si --nlp) → détection entités PER, validation longueur/majuscule/stopwords
3. Protection whitelist du mapping (mots à ne jamais pseudonymiser — « blacklist » dans l'original)
4. Application blacklist du mapping (forcer la pseudonymisation — « whitelist » dans l'original)

--- PHASE 1 : Finance & régalien ---
5. Numéro fiscal (13 chiffres, commence par 0-3)
6. NIR + validation
7. IBAN
8. CB + validation Luhn (excl. SIREN/SIRET)
9. CVV contextuel
10. SIRET/SIREN + validation Luhn

--- PHASE 2 : Communication ---
11. Liens mailto
12. Emails obfusqués
13. Emails standards

--- PHASE 3 : Infrastructure technique (si --tech, inactif en v1) ---
14. JWT
15. API keys
16. IPv6
17. MAC
18. IPv4
19. GPS
20. Plaques d'immatriculation

--- PHASE 4 : Téléphones ---
21. Téléphones fuzzy
22. Téléphones avec préfixe « TEL : »

--- PHASE 5 : URLs ---
23. URLs (http, https, www)

--- PHASE 6 : Organisations & villes ---
24. Organisations (Nom + Statut juridique)
25. Mots-clés organisations
26. Villes (Top 80)

--- PHASE 7 : Contexte & entités ---
27. Dates de naissance (si --fort)
28. Adresses numérotées
29. Adresses sans numéro (si --fort)
30. CP dans le texte (si --fort)
31. Villes après CP (si --fort)
32. Salutations + nom
33. Titres + nom

--- PHASE 8 : Dictionnaires (si --fort) ---
34. Prénom + NOM_MAJ (vérifié dictionnaire)
35. Prénom + Nom classique (vérifié dictionnaire)
36. Prénoms isolés capitalisés (vérifié dictionnaire)
37. Prénoms isolés minuscules (vérifié dictionnaire)
38. Patronymes composés à préfixe (BEN, EL, AL, AIT, ABDEL)
39. Mots en MAJUSCULES (vérifié dictionnaire patronymes)

--- PHASE 9 : Propagation (si --fort) ---
40. Heuristique tableur : mots majuscules isolés entre tabulations/retours à la ligne ne sont PAS pseudonymisés (probablement des en-têtes de colonnes)
41. Absorption des mots majuscules adjacents aux jetons (max 3 itérations)

--- PHASE 10 : Nettoyage ---
42. Espacement autour des jetons
43. Restauration blacklist
44. Restauration tokens protégés
```

---

## V1 — JSON plat, iso-fonctionnel avec l'original

### Périmètre v1

- JSON plat (array d'objets, premier niveau)
- Mapping simple (champs premier niveau)
- **Toute la logique de détection de l'original** : regex complètes, dictionnaires INSEE, stopwords, contexte institutionnel, normalisation noms, détection organisations/villes
- Deux modes de détection : standard (regex coeur) et `--fort` (pipeline complet)
- Modes `--pseudo`, `--anon`, `--dry-run`
- Scoring RGPD (`--score-only`)
- Script de dépseudonymisation

### Ce qui est hors v1 (reporté en v2)

- Notation pointée, unwrap JSON stringifié
- `--input-dir` (multi-fichiers)
- `--tech` (regex techniques — les étapes 14-20 du pipeline sont inactives en v1)
- `--mapping-generate`
- `--chunk-size` (streaming)

**`--nlp` est disponible dès la v1** (optionnel, nécessite spaCy installé).

### Mapping v1

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
  "lookup_noms": {
    "prenom": "prenom",
    "nom": "nom"
  },
  "whitelist": ["ORANGE", "AMAZON", "SFR", "FREE"],
  "blacklist": ["Victor Hugo", "Jean Moulin"]
}
```

**`whitelist`** : mots à ne jamais pseudonymiser, même s'ils sont dans les dictionnaires INSEE. Couvre les noms d'entreprise qui sont aussi des patronymes (ORANGE, PETIT, MARTIN...). Correspond à la blacklist manuelle de l'original (étape 3 du pipeline — « protéger ces mots »).

**`blacklist`** : mots à toujours forcer en pseudonymisation, même s'ils sont dans les stopwords ou protégés par le contexte institutionnel. Correspond à la whitelist manuelle de l'original (étape 4 du pipeline — « forcer la pseudonymisation de ces mots »). Exemple : « Victor Hugo » est normalement protégé par le contexte institutionnel si adjacent à « école », mais si on veut quand même le pseudonymiser, on le met dans la blacklist.

**Note terminologique** : l'original utilise « blacklist » pour protéger et « whitelist » pour forcer — c'est inversé par rapport à l'usage courant. Notre mapping utilise les termes dans leur sens naturel : whitelist = protéger, blacklist = forcer.

### Interface v1

```bash
# Standard (regex coeur + lookup + dictionnaires + stopwords)
python3 generique/pseudonymise.py data/clients.json --mapping mapping.json --pseudo

# Fort (pipeline complet : prénoms isolés, propagation, patronymes préfixe...)
python3 generique/pseudonymise.py data/clients.json --mapping mapping.json --fort --pseudo

# Avec NLP spaCy (optionnel, +2-5% de détection)
python3 generique/pseudonymise.py data/clients.json --mapping mapping.json --fort --nlp --pseudo

# Scoring sans pseudonymiser
python3 generique/pseudonymise.py data/clients.json --mapping mapping.json --score-only

# Dry-run
python3 generique/pseudonymise.py data/clients.json --mapping mapping.json --dry-run

# Dépseudonymisation
python3 generique/depseudonymise.py data/clients_PSEUDO.json --correspondances confidentiel/correspondances.csv
```

### Dry-run amélioré

Le dry-run affiche :
- Nombre de remplacements par type et échantillons (comme le script spécifique)
- Les 20 mots les plus fréquemment matchés par les dictionnaires (pour calibrer la whitelist)
- Les mots matchés qui sont aussi dans les stopwords (signale les collisions)
- Le score RGPD moyen sur l'échantillon

### Livrables v1

| Script | Rôle |
|--------|------|
| `generique/convertir-donnees.py` | Conversion de toutes les données JS → JSON Python |
| `generique/pseudonymise.py` | Script principal (standard + fort + scoring) |
| `generique/depseudonymise.py` | Script de dépseudonymisation |
| `generique/verif-complet.py` | Audit automatisé |
| `generique/test-options.py` | Suite de tests |

| Données | Entrées |
|---------|---------|
| `generique/data/noms.json` | 884 314 |
| `generique/data/prenoms.json` | 183 826 |
| `generique/data/stopwords-capitalises.json` | ~150 |
| `generique/data/stopwords-minuscules.json` | ~100 |
| `generique/data/majuscules-garder.json` | ~60 |
| `generique/data/villes-france.json` | ~80 |
| `generique/data/mots-organisations.json` | ~30 |
| `generique/data/contexte-institution.json` | ~50 |
| `generique/data/acronymes-garder.json` | ~12 |

| Documentation | |
|---------------|---|
| `generique/README.md` | Guide utilisateur |
| `generique/exemples/` | Exemples de mappings |

### Critères de validation v1

| # | Critère | Outil |
|---|---------|-------|
| 1 | JSON plat pseudonymisé correctement avec mapping | verif-complet |
| 2 | Mode standard : regex coeur + stopwords fonctionnent | Dry-run |
| 3 | Mode `--fort` : prénoms isolés, patronymes préfixe, propagation fonctionnent | Dry-run avec texte de test |
| 4 | Stopwords empêchent les faux positifs (« Bonjour », « Direction », « Pierre » matériau) | Dry-run |
| 5 | Contexte institutionnel : « école Victor Hugo » non pseudonymisé | Test unitaire |
| 6 | Normalisation : « Dupont Marie » = « Marie Dupont » = même jeton | Test unitaire |
| 7 | Organisations détectées : « Société Générale SA » → `[ORGANISATION]` | Dry-run |
| 8 | Villes détectées dans le texte | Dry-run |
| 9 | Scoring RGPD cohérent avec les niveaux de l'original | Comparaison |
| 10 | Dépseudonymisation fonctionne (JSON pseudo + CSV → JSON original) | Test aller-retour |
| 11 | Dictionnaires chargés en < 5 secondes | Chrono |
| 12 | Whitelist du mapping fonctionne | Dry-run avec ORANGE dans le texte |
| 13 | `--nlp` : spaCy détecte des noms supplémentaires hors dictionnaire | Dry-run avec et sans --nlp, comparer les stats |
| 14 | `--nlp` absent : le script fonctionne sans spaCy installé | Test sans spaCy dans le path |
| 15 | Performance : mode standard < 5 min pour 31k enregistrements | Chrono |
| 16 | Performance : mode `--fort` < 15 min pour 31k enregistrements | Chrono |
| 17 | Blacklist du mapping force la pseudonymisation malgré stopwords/contexte | Test unitaire |

### Séquence de travail v1

1. Alex valide la v1 de ce PRD
2. Claude écrit `convertir-donnees.py` et génère tous les fichiers data/
3. Claude écrit `generique/pseudonymise.py` (mode standard + fort)
4. Claude écrit `generique/depseudonymise.py`
5. Test sur un JSON plat de test (données synthétiques couvrant tous les cas)
6. Test dry-run : calibrage whitelist, vérification stopwords
7. Tests automatisés et documentation

---

## V2 — Structures complexes + multi-fichiers + streaming

### Périmètre v2 (après validation v1)

| Feature | Détail |
|---------|--------|
| **Notation pointée** | `Report.Firstname`, `Report.Details[].Value` |
| **Unwrap JSON stringifié** | `"parse": "json_string"` dans le mapping |
| **`--input-dir`** | Tous les `.json` d'un dossier, table de correspondances globale |
| **`--tech`** | IPv4, IPv6, MAC, JWT, API keys |
| **`--mapping-generate`** | Inspecte un JSON, propose un mapping squelette |
| **`--chunk-size N`** | Streaming via `ijson` pour fichiers > 2 Go (seule dépendance externe : `pip install ijson`) |

### Mapping v2

Extension du v1 avec notation pointée et unwrap :

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
    "Report.Id": {"type": "uuid", "jeton": "UUID"},
    "Report.Firstname": {"type": "prenom", "jeton": "PRENOM"},
    "Report.Lastname": {"type": "nom", "jeton": "NOM"},
    "Report.Email": {"type": "email", "jeton": "EMAIL"},
    "Report.Phone": {"type": "tel", "jeton": "TEL"},
    "Report.ConsumerPhone": {"type": "tel", "jeton": "TEL"},
    "Report.PostalCode": {"type": "cp", "jeton": "CP"},
    "Report.Gender": {"type": "genre", "jeton": "GENRE"}
  },
  "texte_libre": [
    "Report.Question",
    "Report.Description",
    "Report.Details[].Value"
  ],
  "lookup_noms": {
    "prenom": "Report.Firstname",
    "nom": "Report.Lastname"
  },
  "whitelist": ["ORANGE", "SFR", "FREE"]
}
```

### Rétrocompatibilité

Le script générique v2 + mapping SignalConso produit les mêmes remplacements sur les champs structurés que le script spécifique. Le texte libre peut différer (le générique détecte plus via dictionnaires + logique métier complète).

### Critères de validation v2

| # | Critère |
|---|---------|
| 1 | Notation pointée fonctionne |
| 2 | Unwrap JSON stringifié fonctionne |
| 3 | Rétrocompatibilité champs structurés avec script spécifique |
| 4 | `--input-dir` : table globale, même personne = même jeton entre fichiers |
| 5 | `--tech` : détecte IPv4, IPv6, MAC, JWT, API keys |
| 6 | `--mapping-generate` : propose un mapping cohérent |
| 7 | `--chunk-size` : traite un fichier > 2 Go sans saturer la RAM |

---

## V3 — Multi-format + interface web locale

### Périmètre v3 (après validation v2)

| Feature | Dépendance Python |
|---------|-------------------|
| Import/export CSV/TSV | `csv` (stdlib) |
| Import/export Excel (XLS/XLSX/ODS) | `openpyxl` + `odfpy` (ODS) |
| Import/export DOCX/ODT | `python-docx` + `odfpy` (ODT) |
| Import PDF → texte pseudonymisé | `pdfplumber` |
| Interface web locale DSFR | `http.server` (stdlib) |

Les dépendances sont optionnelles : imports conditionnels, le script fonctionne sans si le format n'est pas utilisé.

### Mapping v3

Ajout du champ `format` :

```json
{
  "description": "Dossiers clients",
  "format": "csv",
  "options": {"delimiter": ";", "encoding": "utf-8", "header": true},
  "champs_sensibles": {
    "nom": {"type": "nom", "jeton": "NOM"}
  },
  "texte_libre": ["commentaire"]
}
```

Pour DOCX/PDF (tout le contenu est du texte libre) :

```json
{
  "format": "docx",
  "texte_libre": ["*"]
}
```

### Interface web locale DSFR

Interface conforme au Design System de l'État Français (DSFR), connectée au moteur Python via un serveur local. Le frontend original (glassmorphism) reste dans `public/` comme référence mais n'est plus utilisé.

**Architecture** :

```
┌──────────────────────────────────┐
│  Frontend DSFR                   │
│  (generique/interface/)          │
│  Composants DSFR, accessible     │
└──────────────┬───────────────────┘
               │ fetch() HTTP local
               ▼
┌──────────────────────────────────┐
│  generique/serveur.py            │
│  Serveur Python local (port 8090)│
│  Routes :                        │
│  - POST /pseudonymise            │
│  - POST /depseudonymise          │
│  - POST /score                   │
│  - GET  /mapping/generate        │
│  - GET  /stats                   │
└──────────────┬───────────────────┘
               │ appelle
               ▼
┌──────────────────────────────────┐
│  generique/pseudonymise.py       │
│  Moteur de pseudonymisation      │
│  (même code que le CLI)          │
└──────────────────────────────────┘
```

**Pages DSFR** :

| Page | Composants DSFR | Fonctionnalité |
|------|----------------|----------------|
| Pseudonymisation | Textarea, boutons radio (standard/fort), bouton principal, alerte résultat | Coller ou importer du texte, lancer la pseudonymisation |
| Correspondances | Tableau DSFR, pagination, recherche | Visualiser et exporter la table de correspondances |
| Restauration | Textarea, upload CSV correspondances, bouton | Dépseudonymiser un texte |
| Import fichier | Upload DSFR (petits fichiers) + chemin local (gros fichiers), sélection du mapping, barre de progression | Importer JSON/CSV/Excel/DOCX/PDF |
| Scoring | Tableau DSFR, indicateurs (badges), graphique distribution | Audit RGPD avant pseudonymisation |

**Génération** : les pages DSFR sont générées via le skill `/dsfr-components` du workspace Claude, qui produit du HTML conforme DSFR avec composants accessibles (formulaires, tableaux, alertes, upload, badges, pagination, navigation).

**Accessibilité** : l'interface DSFR est nativement conforme RGAA. Labels sur tous les champs, navigation clavier, contrastes conformes, annonces ARIA pour les résultats asynchrones.

**Lancement** :

```bash
python3 generique/serveur.py
# → Serveur local sur http://localhost:8090
# → Sert l'interface DSFR depuis generique/interface/
# → API de pseudonymisation sur les routes /pseudonymise, etc.
```

**Import de fichiers lourds (>50 Mo)** :

Le serveur est local — le fichier est déjà sur le disque. Pour les gros fichiers, le frontend envoie un **chemin local** au lieu d'uploader via HTTP :

```
Petit fichier (<50 Mo) :  [Navigateur] --upload multipart--> [Serveur] --resultat JSON--> [Navigateur]
Gros fichier  (>50 Mo) :  [Navigateur] --chemin local--> [Serveur lit/ecrit sur disque] --stats--> [Navigateur]
```

- `POST /api/pseudonymise-local` : accepte `{"path": "/chemin/fichier.json", "mapping": {...}}` ou `{"path": "...", "mapping_path": "/chemin/mapping.json"}`
- Le serveur lit le fichier directement sur disque, le traite, écrit le résultat sur disque
- Seuls les stats et correspondances transitent par HTTP (quelques Ko)
- Compatible avec `--chunk-size` pour les fichiers > 2 Go

**Sécurité** : le serveur écoute sur `127.0.0.1` uniquement (pas d'accès réseau). Si le serveur devait être exposé (ex: sur un réseau interne), ajouter un paramètre `--allowed-dirs` pour restreindre les chemins autorisés aux seuls répertoires de travail.

**Génération automatique de mapping** :

Un utilisateur qui découvre un fichier JSON ne sait pas quel mapping écrire. Le moteur CLI dispose déjà de `--mapping-generate` qui inspecte un fichier et propose un mapping squelette. L'interface web expose cette fonctionnalité :

```
1. L'utilisateur saisit le chemin du fichier (ou uploade un petit fichier)
2. Il clique "Analyser la structure"
3. Le serveur lit les 5 premiers enregistrements, detecte les champs sensibles
4. Un mapping pre-rempli apparait dans le textarea
5. L'utilisateur ajuste si besoin (ajouter/supprimer un champ, corriger un type)
6. Il lance le traitement
```

- `POST /api/mapping/generate` : accepte `{"path": "/chemin/fichier.json"}` ou un upload, retourne un mapping squelette
- Détection par heuristique : noms de champs contenant "nom", "prenom", "email", "tel", "adresse", "cp", "phone", "firstname", "lastname", "phone_number", etc. (français et anglais)
- Détection des champs contenant du JSON stringifié : tenter un `json.loads()` sur les valeurs string, proposer une structure unwrap uniquement si le parsing réussit et que le résultat est un dict ou une liste
- L'utilisateur n'a jamais à écrire du JSON à la main

**Le mapping généré est toujours proposé en preview** dans le textarea, jamais appliqué directement. L'utilisateur peut ajuster (ajouter/supprimer des champs, corriger un type, modifier la whitelist) avant de lancer le traitement. Un mapping mal généré ne peut pas déclencher de pseudonymisation accidentelle.

**Mode chemin local complet** :

En mode "Chemin local", deux champs texte :

| Champ | Role | Obligatoire |
|-------|------|-------------|
| Chemin du fichier | Fichier source a pseudonymiser | Oui |
| Chemin du mapping | Fichier mapping JSON existant sur le disque | Non (alternative au textarea) |

Si le chemin du mapping est fourni, il est lu sur disque par le serveur. Sinon, le textarea ou le bouton « Analyser la structure » sont utilisés.

**Avantages** :

- Conforme DSFR et RGAA (obligatoire pour le service public)
- Le moteur Python est plus puissant que le JS (dictionnaires en mémoire serveur, pas dans le navigateur)
- L'import de fichiers lourds ne bloque plus le navigateur (chemin local, zéro transfert HTTP)
- L'interface est utilisable par quelqu'un qui ne connaît pas le terminal (génération automatique du mapping)
- Tout reste local (localhost, aucune donnée ne sort)

### Critères de validation v3

| # | Critère |
|---|---------|
| 1 | CSV/TSV : import, pseudonymise par colonnes, export |
| 2 | Excel (XLS/XLSX/ODS) : idem |
| 3 | DOCX/ODT : extraction texte, pseudonymisation, réécriture |
| 4 | PDF : extraction texte, pseudonymisation, export texte |
| 5 | Interface DSFR : navigation entre les 5 pages fonctionne |
| 6 | Coller du texte → pseudonymisation via le serveur Python |
| 7 | Import d'un fichier lourd (>50 Mo) via chemin local sans freeze du navigateur |
| 8 | Tableau de correspondances DSFR avec pagination et recherche |
| 9 | Export multi-format depuis l'interface |
| 10 | Conformité RGAA de l'interface (audit avec axe-core) |
| 11 | Génération automatique de mapping : bouton « Analyser la structure » propose un mapping en preview |
| 12 | Chemin du mapping : le mode local accepte un chemin vers un fichier mapping existant |

---

## Risques (toutes versions)

| Risque | Version | Sévérité | Mitigation |
|--------|---------|----------|------------|
| Faux positifs dictionnaires (PETIT, BLANC, PIERRE) | v1 | Élevée | 3 listes de stopwords portées + whitelist mapping + top 20 au dry-run |
| Contexte institutionnel raté | v1 | Moyenne | `estContexteInstitution()` portée + liste de 50 mots de contexte |
| Normalisation noms incomplète | v1 | Moyenne | Tri alphabétique des mots (comme l'original) |
| Parseur notation pointée buggé | v2 | Moyenne | Tests unitaires sur `a.b`, `a.b[]`, `a.b[].c` |
| Performance 884k noms + 200 stopwords en mémoire | v1 | Faible | ~50-80 Mo RAM, `set()` Python O(1) |
| Collision jetons inter-fichiers | v2 | Moyenne | Table globale unique |
| Extraction PDF perd la mise en page | v3 | Moyenne | PDF → texte brut uniquement |
| DOCX avec tableaux/images | v3 | Moyenne | Paragraphes texte uniquement |
| Mapping auto-généré incorrect | v3 | Moyenne | Preview obligatoire avant traitement, jamais appliqué directement |
| Chemin local exposé si serveur sur réseau | v3 | Élevée | Binding `127.0.0.1` par défaut, `--allowed-dirs` si exposé |
| Correspondances volumineuses en mémoire navigateur | v3 | Faible | Suffisant pour 31k enr., à surveiller au-delà |

---

## Hors périmètre (toutes versions)

- Réécriture de PDF tagué (export texte uniquement)
- OCR images
- Application mobile
- Éditeur visuel de mapping (le textarea avec génération automatique couvre le besoin)
- Authentification / multi-utilisateurs (le serveur est mono-utilisateur, local uniquement)

---

## Couverture de l'original

| Fonctionnalité Pseudonymus v2 | v1 | v2 | v3 |
|-------------------------------|----|----|-----|
| Regex coeur (emails, NIR, IBAN, CB, tel, URL, adresses, salutations, titres, prénomNom) | Oui | Oui | Oui |
| Regex mode fort (CP, voieSans, dateNaiss, GPS, plaque, prénoms isolés, majLong, préfixes) | `--fort` | `--fort` | `--fort` |
| Regex tech (IPv4/v6, MAC, JWT, API keys) | — | `--tech` | `--tech` |
| Validation Luhn + NIR | Oui | Oui | Oui |
| Dictionnaires INSEE (884k noms + 184k prénoms) | Oui | Oui | Oui |
| Stopwords (3 listes, 310+ mots) | Oui | Oui | Oui |
| Contexte institutionnel | Oui | Oui | Oui |
| Contexte numérique négatif | Oui | Oui | Oui |
| Détection organisations | Oui | Oui | Oui |
| Détection villes | Oui | Oui | Oui |
| Normalisation noms (inversion) | Oui | Oui | Oui |
| Propagation heuristique | `--fort` | `--fort` | `--fort` |
| Patronymes à préfixe (BEN, EL, AL) | `--fort` | `--fort` | `--fort` |
| Scoring RGPD | `--score-only` | `--score-only` | `--score-only` |
| Dépseudonymisation | Oui | Oui | Oui |
| JSON plat | Oui | Oui | Oui |
| JSON imbriqué / stringifié | — | Oui | Oui |
| Multi-fichiers | — | `--input-dir` | `--input-dir` |
| Streaming gros fichiers | — | `--chunk-size` | `--chunk-size` |
| Génération de mapping | — | `--mapping-generate` | `--mapping-generate` |
| NLP (pré-filtre entités PER) | `--nlp` (spaCy fr, optionnel) | `--nlp` | `--nlp` |
| Heuristique tableur (en-têtes colonnes) | `--fort` | `--fort` | `--fort` |
| Import CSV/TSV | — | — | Oui |
| Import Excel (XLS/XLSX/ODS) | — | — | Oui |
| Import DOCX/ODT | — | — | Oui |
| Import PDF | — | — | Oui |
| Interface web locale DSFR (remplace le frontend glassmorphism) | — | — | Oui |

---

## Statut d'implementation

### v1 — Livree

**Commit** : `f9c8ba5` (Ajout script generique v1+v2 : iso-perimetre Pseudonymus v2)

Tout le perimetre v1 est implemente et teste (49 tests automatises) :
- Regex completes (coeur + fort + NLP optionnel)
- Dictionnaires INSEE (884k noms + 169k prenoms)
- 3 listes de stopwords + contexte institutionnel
- Normalisation noms, detection organisations/villes
- Scoring RGPD, dry-run ameliore
- Depseudonymisation
- Validation Luhn, NIR, SIRET

### v2 — Livree

**Commits** : `54535d6` a `d6e2d09`

Tout le perimetre v2 est implemente :
- Notation pointee (`Report.Firstname`, `Report.Details[].Value`)
- Unwrap JSON stringifie
- `--input-dir` (multi-fichiers, table globale)
- `--tech` (IPv4, IPv6, MAC, JWT, API keys)
- `--mapping-generate` (generation automatique de mapping)
- `--chunk-size` (streaming via ijson pour fichiers > 2 Go)

### v3 — Livree

**Commit** : `7e5742f` (Ajout v3 multi-format + serveur web local + interface DSFR)

#### Parseurs multi-format (`generique/formats.py`)

| Format | Chargement | Sauvegarde | Dependance |
|--------|-----------|------------|------------|
| CSV/TSV | OK | OK | `csv` (stdlib) |
| XLSX/XLS | OK | OK | `openpyxl` |
| ODS | OK | OK | `odfpy` |
| DOCX | OK | OK | `python-docx` |
| ODT | OK | OK | `odfpy` |
| PDF | OK | Export .txt | `pdfplumber` |

Toutes les dependances sont optionnelles (imports conditionnels).

#### Serveur web local (`generique/serveur.py`)

| Route | Methode | Fonction | Statut |
|-------|---------|----------|--------|
| `/api/pseudonymise-texte` | POST | Pseudonymiser du texte brut | OK |
| `/api/pseudonymise` | POST | Pseudonymiser un fichier (upload multipart) | OK |
| `/api/pseudonymise-local` | POST | Pseudonymiser un fichier via chemin local | OK |
| `/api/depseudonymise` | POST | Restaurer les jetons | OK |
| `/api/score` | POST | Scoring RGPD | OK |
| `/api/mapping/generate` | POST | Génération automatique de mapping | OK |
| `/api/stats` | GET | Statistiques dictionnaires | OK |
| `/api/health` | GET | Sante du serveur | OK |

#### Interface DSFR (`generique/interface/`)

5 pages testees avec Chrome DevTools :

| Page | Statut | Detail |
|------|--------|--------|
| Pseudonymisation | OK | Textarea, options standard/fort/tech/NLP, whitelist/blacklist, alerte resultat |
| Correspondances | OK | Tableau DSFR avec pagination, recherche, export CSV |
| Restauration | OK | Depseudonymisation via correspondances en memoire ou CSV |
| Import fichier | OK | Upload multi-format, mapping JSON, barre de progression |
| Scoring RGPD | OK | Detail par categorie (direct/finance/tech/indirect) et par type |

#### Critères de validation v3

| # | Critère | Statut |
|---|---------|--------|
| 1 | CSV/TSV : import, pseudonymise, export | OK |
| 2 | Excel (XLSX/ODS) : idem | OK |
| 3 | DOCX/ODT : extraction, pseudonymisation, réécriture | OK |
| 4 | PDF : extraction, pseudonymisation, export texte | OK |
| 5 | Interface DSFR : navigation 5 pages | OK |
| 6 | Pseudonymisation texte via serveur | OK |
| 7 | Import fichier lourd sans freeze | OK (118 Mo, 31 891 enr., 57s via chemin local) |
| 8 | Tableau correspondances avec pagination/recherche | OK |
| 9 | Export CSV depuis l'interface | OK |
| 10 | Conformité RGAA (audit axe-core) | OK (zéro violation accesslint) |
| 11 | Génération automatique de mapping | OK |
| 12 | Chemin du mapping en mode local | OK |

### Livrables finaux

| Fichier | Role |
|---------|------|
| `generique/convertir-donnees.py` | Conversion donnees JS vers JSON |
| `generique/pseudonymise.py` | Moteur principal (v1+v2+v3) |
| `generique/depseudonymise.py` | Depseudonymisation |
| `generique/formats.py` | Parseurs multi-format |
| `generique/serveur.py` | Serveur web local DSFR |
| `generique/interface/` | Frontend DSFR (3 fichiers) |
| `generique/test-options.py` | 49 tests automatises |
| `generique/data/` | 9 fichiers de reference (884k+ entrees) |
| `generique/README.md` | Guide utilisateur |
| `generique/exemples/` | Exemples de mappings |
