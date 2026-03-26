# PRD v2 : Pseudonymisation batch JSON SignalConso

**Date** : 2025-03-25
**Statut** : Rétrospectif (réécriture post-implémentation)
**Auteur** : Alex

---

## Contexte

Un fichier JSON SignalConso de 112 Mo (31 891 réclamations consommateurs) doit être pseudonymisé avant tout traitement par un LLM ou partage externe.

**Contrainte absolue** : zéro donnée sensible ne transite vers un service externe. Tout s'exécute en local.

**Origine des regex** : Pseudonymus v2, une appli navigateur HTML/JS qui pseudonymise du texte par regex. L'appli ne peut pas ingérer 112 Mo — on porte sa logique dans un script Python.

---

## Données source

| Propriété | Valeur |
|-----------|--------|
| Fichier | `virginie/CourrierSRCAvecParag_2025_7_5.json` |
| Taille | 112 Mo |
| Enregistrements | 31 891 |
| Structure | JSON array > objet (4 clés) > `RCLMFicheReportJsonSC` (JSON stringifié) > `Report` (18 clés) |

### Champs à pseudonymiser

| Champ | Remplissage | Jeton |
|-------|-------------|-------|
| DOAR_IDENT | 100% | `[ID_X]` |
| Id (UUID dans Report) | 100% | `[UUID_X]` |
| Firstname | 100% | `[PRENOM_X]` |
| Lastname | 100% | `[NOM_X]` |
| Email | 100% | `[EMAIL_X]` |
| ConsumerPhone | 81% | `[TEL_X]` |
| Phone | 1% | `[TEL_X]` |
| PostalCode | 97% | `[CP_X]` |
| Gender | 100% | `[GENRE_X]` |

`X` = identifiant unique par valeur distincte (même email partout = même jeton).

Siret conservé tel quel (identifiant entreprise).

### Texte libre à scanner

| Champ | Remplissage |
|-------|-------------|
| Question | 99% |
| Description | 91% |
| Details[].Value | 100% |

7% des enregistrements contiennent le nom/prénom du déclarant dans le texte libre.

---

## Livrables

### Scripts

| Script | Rôle |
|--------|------|
| `pseudonymise-json.py` | Script principal (pseudo / anon / dry-run) |
| `verif-sample.py` | Vérification rapide (1er enregistrement) |
| `verif-complet.py` | Audit automatisé (100 enregistrements aléatoires) |
| `test-options.py` | Suite de 35 tests couvrant toutes les options |

### Documentation (dossier `alex/`)

| Fichier | Rôle |
|---------|------|
| `GUIDE-UTILISATEUR.md` | Documentation complète orientée utilisateur |
| `PRD-v2-retroengineering.md` | Ce PRD (spécification technique) |
| `POUR-ALEX-pseudonymisation-batch-json.md` | Retour pédagogique |

### Fichiers produits par le script

| Fichier | Sécurité |
|---------|----------|
| `virginie/*_PSEUDO.json` | Partageable |
| `virginie/*_ANON.json` | Partageable |
| `virginie/confidentiel/correspondances.csv` | Gitignored, chmod 600, ne jamais partager |

---

## Script principal : `pseudonymise-json.py`

### Interface

```bash
python3 pseudonymise-json.py <fichier.json> --dry-run|--pseudo|--anon
```

| Mode | Effet | Fichiers écrits |
|------|-------|-----------------|
| `--dry-run` | 100 premiers enregistrements, stats sur stderr | Aucun |
| `--pseudo` | Pseudonymisation réversible | JSON + CSV correspondances |
| `--anon` | Anonymisation irréversible | JSON uniquement |

Le mode `--pseudo` est le mode principal. Le mode `--anon` est une extension — les valeurs de remplacement sont :

| Champ | Valeur anon |
|-------|-------------|
| Firstname / Lastname | `***` |
| Email | `anonyme@example.com` |
| Phone | `00 00 00 00 00` |
| PostalCode | `00000` |
| Gender | `Non renseigné` |
| DOAR_IDENT | Compteur séquentiel |
| Id | UUID v4 régénéré |
| Texte libre (regex matches) | `[SUPPRIMÉ]` |

### Phase 1 : Champs structurés

Remplacement direct. Rien de subtil.

### Phase 2 : Texte libre

Pour chaque enregistrement, dans Question, Description et Details[].Value :

**Étape 1 — Lookup noms du déclarant**

Rechercher le Firstname et Lastname de l'enregistrement dans le texte (insensible à la casse, word-boundary).

Règle des noms courts : les prénoms de moins de 4 lettres (`Léa`, `Eva`, `Aya`) ne sont matchés que combinés avec le nom de famille. Raison : un prénom court isolé matche trop de mots courants.

**Étape 2 — Regex (adaptées depuis `public/assets/js/app.js` l.11-84)**

Les regex Python concrètes :

```python
# Emails
RX_EMAIL = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
RX_EMAIL_OBFUSCATED = re.compile(
    r'\b[a-zA-Z0-9_.+-]+\s*(?:@|\[at\]|\(at\)|\[arobase\])'
    r'\s*[a-zA-Z0-9-]+\s*(?:\.|\[dot\]|\(dot\)|point)\s*[a-zA-Z0-9-.]+\b',
    re.IGNORECASE)

# NIR (Sécu) — lookbehind fixe (1 char) adapté du JS
RX_NIR = re.compile(
    r'(?<!\d)([12])[\s.\-]*(\d{2})[\s.\-]*(\d{2})[\s.\-]*'
    r'(\d{2}|2[AB])[\s.\-]*(\d{3})[\s.\-]*(\d{3})'
    r'(?:[\s.\-]*(\d{2}))?(?!\d)', re.IGNORECASE)

# IBAN
RX_IBAN = re.compile(
    r'\b[A-Z]{2}\d{2}[\s\-]?[0-9A-Z]{4}[\s\-]?[0-9A-Z]{4}'
    r'[\s\-]?[0-9A-Z]{4}[\s\-]?[0-9A-Z]{4}'
    r'[\s\-]?[0-9A-Z]{0,4}[\s\-]?[0-9A-Z]{0,3}\b', re.IGNORECASE)

# Cartes bancaires (13-19 chiffres, validation Luhn)
RX_CB = re.compile(r'\b(?:\d[\s\-]*?){13,19}\b')

# Téléphones
RX_TEL = re.compile(r'(?<!\d)(?:\+33|0)[1-9](?:[\s.\-]*\d{2}){4}(?!\d)')
RX_TEL_FUZZY = re.compile(
    r'(?<!\d)(?:(?:\+|00)33|0)\s*[1-9](?:[\s._\-]*\d){8}(?!\d)')

# Adresses numérotées uniquement
RX_VOIE_NUM = re.compile(
    r"\b\d+\s+(?:rue|avenue|boulevard|chemin|impasse|allée|route|bis|ter)"
    r"\s+[A-Za-zÀ-ÖØ-öø-ÿ'\-\s]{3,}", re.IGNORECASE)
```

Appliquées dans cet ordre :

| Ordre | Type | Regex | Raison de l'ordre |
|-------|------|-------|-------------------|
| 1 | Emails | `RX_EMAIL`, `RX_EMAIL_OBFUSCATED` | En premier pour ne pas casser les adresses |
| 2 | NIR | `RX_NIR` + validation structure | Avant téléphones (collisions numériques) |
| 3 | IBAN | `RX_IBAN` | |
| 4 | Cartes bancaires | `RX_CB` + validation Luhn | |
| 5 | Téléphones | `RX_TEL`, `RX_TEL_FUZZY` | |
| 6 | Adresses numérotées | `RX_VOIE_NUM` uniquement | |

**Validation Luhn — exclusion des SIRET** : la regex CB matche des séquences de 13-19 chiffres. Les SIRET (14 chiffres) et SIREN (9 chiffres) passent souvent Luhn par coïncidence. Le validateur exclut les séquences de 9 et 14 chiffres avant de tester Luhn :

```python
def luhn_check(s):
    digits = re.sub(r'\D', '', s)
    if len(digits) < 9:
        return False
    if len(digits) in (9, 14):  # Exclusion SIREN/SIRET
        return False
    # ... validation Luhn standard
```

**Regex exclue** : `RX_VOIE_SANS` (adresses sans numéro). Produit 37% de faux positifs sur du texte courant (« allée dans un magasin »). Retirée volontairement.

**Portage JS → Python** : les lookbehind variables JS ne sont pas supportés en Python `re`. Les regex sont adaptées depuis `app.js` lignes 11-84, pas copiées.

### Phase 3 : Ré-sérialisation

Le JSON a une structure en poupées russes : `RCLMFicheReportJsonSC` est une chaîne JSON dans un objet JSON. Le script :

1. Parse l'enveloppe (`json.loads`)
2. Parse la chaîne interne (`json.loads(rec['RCLMFicheReportJsonSC'])`)
3. Pseudonymise le Report
4. Re-sérialise le Report en chaîne (`json.dumps`)
5. Réinsère dans l'enveloppe

`ensure_ascii=False` obligatoire pour préserver les accents français.

### Gestion des erreurs

- Enregistrement malformé : skip + log sur stderr (index + DOAR_IDENT) + continuation
- Compteur d'erreurs affiché en fin de traitement
- Progression affichée toutes les 1000 entrées (`[12000/31891]`)

### Table de correspondances (mode `--pseudo`)

Fichier CSV UTF-8, séparateur `;`, dans `virginie/confidentiel/`.

```csv
type;jeton;valeur_originale
prenom;[PRENOM_1];farid
nom;[NOM_1];abdelkader
email;[EMAIL_1];motardzen1@gmail.com
```

Sécurité : gitignored, chmod 600, jamais partagé. Pas de chiffrement nécessaire tant que le fichier reste en local.

---

## Scripts de vérification

### `verif-sample.py`

Affiche les champs sensibles du premier enregistrement du JSON pseudonymisé. Vérification visuelle en 2 secondes : si les champs affichent des jetons, c'est bon.

### `verif-complet.py`

Tire 100 enregistrements aléatoires (seed fixe pour reproductibilité) et vérifie automatiquement :
- Champs structurés : jeton, valeur anonyme ou vide (pas de donnée en clair)
- Texte libre : aucune adresse email en clair
- Affiche un échantillon visuel de 5 enregistrements
- Code de sortie 1 si fuite détectée

### `test-options.py`

Suite de 35 tests automatisés couvrant toutes les options :
- Erreurs d'usage (fichier inexistant, aucun mode, deux modes)
- `--dry-run` (pas de fichier écrit, rapport, 100 enregistrements)
- `--pseudo` (JSON + CSV produits, jetons en place, permissions 600, header CSV)
- `--anon` (JSON produit, valeurs anonymes, compteur DOAR_IDENT, UUID régénéré, Gender)

Relancer après toute modification du script pour vérifier la non-régression.

---

## Risques connus et acceptés

| Risque | Sévérité | Décision |
|--------|----------|----------|
| Noms de tiers dans le texte libre | Moyenne | Non traité — seuls les noms du déclarant sont lookupés. Les regex salutation/titre de Pseudonymus ne sont pas portées (trop de faux positifs) |
| Prénoms courts isolés non détectés | Faible | Accepté — mieux vaut rater 2% de vrais noms que casser 10% du texte |
| `Files[].FileName` peut contenir des noms | Faible | Hors périmètre — les métadonnées PJ ne sont pas traitées |
| Ré-identification par croisement contextuel | Faible | Hors périmètre — CP + catégorie + date peut réduire l'anonymat, mais c'est inhérent à la pseudonymisation (vs anonymisation) |
| SIRET d'auto-entrepreneurs | Faible | Non traité — à évaluer si le dataset contient des auto-entrepreneurs |

---

## Hors périmètre explicite

- Pseudonymisation des pièces jointes
- Adaptation de l'interface navigateur Pseudonymus
- Script de dépseudonymisation (le CSV le permet, à écrire si besoin)
- Regex adresses sans numéro (`RX_VOIE_SANS`)
- Regex salutations et titres dans le texte libre

---

## Critères de validation

| # | Critère | Outil de vérification |
|---|---------|----------------------|
| 1 | Même nombre d'enregistrements (moins les skippés) | `verif-complet.py` |
| 2 | Champs structurés : jetons ou vides, jamais en clair | `verif-complet.py` |
| 3 | Texte libre : noms/prénoms du déclarant absents | Dry-run (stats lookup) |
| 4 | Texte libre : pas d'email en clair | `verif-complet.py` |
| 5 | Table de correspondances fonctionnelle | Inspection manuelle |
| 6 | Dry-run sans écriture de fichier | Dry-run |
| 7 | Exécution < 5 minutes | Chrono |

---

## Procédure de bout en bout

```
1. python3 pseudonymise-json.py fichier.json --dry-run
   → Vérifier le rapport : faux positifs ? erreurs ? stats cohérentes ?

2. python3 pseudonymise-json.py fichier.json --pseudo
   → Attendre la fin (progression affichée toutes les 1000 entrées)

3. python3 verif-sample.py
   → Vérifier visuellement que les jetons sont en place

4. python3 verif-complet.py
   → 0 fuite = OK. Fuites détectées = investiguer avant de partager.

5. python3 test-options.py
   → 35/35 OK = le script fonctionne correctement sur tous les modes.
   (Optionnel — à lancer après toute modification du script)

6. Le JSON _PSEUDO.json est prêt à être partagé.
   Le CSV de correspondances reste en local.
```
