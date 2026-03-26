# PRD : Pseudonymisation batch JSON SignalConso

**Date** : 2025-03-25
**Statut** : Validé
**Auteur** : Alex

---

## Contexte

Un fichier JSON de 112 Mo contenant 31 891 réclamations consommateurs SignalConso doit être pseudonymisé avant tout traitement par Claude ou tout partage. Les données personnelles sont présentes dans des champs structurés et dans du texte libre.

**Contrainte absolue** : zéro donnée sensible ne transite vers Claude ou un service externe. Tout le traitement de pseudonymisation s'exécute en local.

---

## Données source

| Propriété | Valeur |
|-----------|--------|
| Fichier | `virginie/CourrierSRCAvecParag_2025_7_5.json` |
| Taille | 112 Mo |
| Enregistrements | 31 891 |
| Structure | JSON array > objet (4 clés) > `RCLMFicheReportJsonSC` (JSON stringifié) > `Report` (18 clés) |

### Champs sensibles structurés

| Champ | Remplissage | Type de donnée |
|-------|-------------|----------------|
| DOAR_IDENT | 100% | Identifiant enveloppe (traçable) |
| Id (dans Report) | 100% | UUID de la réclamation (traçable) |
| Firstname | 100% | Prénom |
| Lastname | 100% | Nom de famille |
| Email | 100% | Adresse email |
| ConsumerPhone | 81% | Téléphone |
| Phone | 1% | Téléphone (rare) |
| PostalCode | 97% | Code postal |
| Gender | 100% | Male/Female (ré-identification croisée) |
| Siret | 92% | Identifiant entreprise |

### Texte libre

| Champ | Remplissage | Taille moyenne |
|-------|-------------|----------------|
| Question | 99% | 234 caractères (max 1000) |
| Description | 91% | Variable |
| Details[] | 100% | 80+ labels distincts, valeurs variables |

**Risque texte libre** : 7% des enregistrements contiennent le nom/prénom du déclarant dans le champ `Question`.

---

## Objectif

Produire un script Python local avec **deux modes** au choix :

### Mode `--pseudo` (pseudonymisation, par défaut)

- Remplace les données personnelles par des jetons (`[PRENOM_1]`, `[EMAIL_3]`...)
- Produit un tableau de correspondances CSV pour dépseudonymiser si besoin
- Réversible : on peut restaurer les données originales

### Mode `--anon` (anonymisation définitive)

- Supprime les données personnelles (remplacement par des valeurs génériques : `***`, `anonyme@example.com`, `00 00 00 00 00`)
- Pas de tableau de correspondances
- Irréversible : les données originales sont perdues

### Commun aux deux modes

1. Lit le JSON source
2. Traite les champs structurés (DOAR_IDENT, Id, Firstname, Lastname, Email, Phone, PostalCode, Gender)
3. Scanne le texte libre (Question, Description, Details[].Value) avec les regex adaptées depuis `app.js` de Pseudonymus + lookup du Firstname/Lastname de chaque enregistrement
4. Produit un JSON iso-structure en sortie

---

## Approche technique

### Script Python (`pseudonymise-json.py`)

**Entrée** : `virginie/CourrierSRCAvecParag_2025_7_5.json`

**Usage** :
```bash
# Dry-run : traite les 100 premiers enregistrements, affiche les stats
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --dry-run

# Pseudonymisation (réversible, avec tableau de correspondances)
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --pseudo

# Anonymisation (irréversible, pas de tableau)
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --anon
```

**Sortie mode `--pseudo`** :
- `virginie/CourrierSRCAvecParag_PSEUDO.json` (JSON pseudonymisé, même structure)
- `virginie/confidentiel/correspondances.csv` (tableau de correspondances, gitignored, chmod 600)

**Sortie mode `--anon`** :
- `virginie/CourrierSRCAvecParag_ANON.json` (JSON anonymisé, même structure)

**Sortie mode `--dry-run`** :
- Aucun fichier écrit
- Affiche sur stdout : nombre de remplacements par type, échantillon de 5 remplacements, alertes sur les cas ambigus

### Phase 1 : Champs structurés (remplacement direct)

| Champ | Jeton (pseudo) | Valeur (anon) |
|-------|----------------|---------------|
| DOAR_IDENT | `[ID_X]` | Compteur séquentiel (1, 2, 3...) |
| Id (UUID) | `[UUID_X]` | UUID v4 régénéré |
| Firstname | `[PRENOM_X]` | `***` |
| Lastname | `[NOM_X]` | `***` |
| Email | `[EMAIL_X]` | `anonyme@example.com` |
| Phone / ConsumerPhone | `[TEL_X]` | `00 00 00 00 00` |
| PostalCode | `[CP_X]` | `00000` |
| Gender | `[GENRE_X]` | `Non renseigné` |

- `X` = identifiant unique par valeur distincte (même email = même jeton partout)
- Le Siret est conservé tel quel (identifiant entreprise, pas donnée personnelle — sauf auto-entrepreneurs, à évaluer)

### Phase 2 : Texte libre (scan regex + lookup)

Pour chaque enregistrement, dans `Question`, `Description` et `Details[].Value` :

En mode `--anon`, les matches regex dans le texte libre sont remplacés par `[SUPPRIMÉ]` (uniforme, visible, explicite).
En mode `--pseudo`, ils sont remplacés par le jeton correspondant (`[TEL_X]`, `[EMAIL_X]`, etc.).

1. **Lookup direct** : rechercher le Firstname et Lastname de l'enregistrement (insensible à la casse) et remplacer par le jeton correspondant (pseudo) ou `[SUPPRIMÉ]` (anon). **Stratégie noms courts** : les prénoms de moins de 4 lettres (`Léa`, `Eva`, `Aya`) ne sont matchés que s'ils apparaissent combinés avec le nom de famille, pour éviter les faux positifs sur des mots courants
2. **Regex Pseudonymus** (adaptées depuis `app.js` — attention : les lookbehind variables JS ne sont pas supportés en Python `re`, certaines regex devront être réécrites et non simplement copiées), appliquées dans cet ordre :
   1. Emails (`RX.email`, `RX_SENSITIVE.emailObfuscated`) — en premier pour ne pas casser les adresses avec les regex suivantes
   2. NIR (`RX_SENSITIVE.nir` + validation) — avant téléphones pour éviter les collisions de patterns numériques
   3. IBAN (`RX_SENSITIVE.iban`)
   4. Cartes bancaires (`RX_SENSITIVE.cb` + validation Luhn)
   5. Téléphones (`RX.tel`, `RX_SENSITIVE.telFuzzy`)
   6. Adresses (`RX.voieNum`, `RX.voieSans`)

### Phase 3 : Ré-sérialisation

- Double-parse : `json.loads(enveloppe)` puis `json.loads(RCLMFicheReportJsonSC)`
- Après pseudonymisation : `json.dumps(report)` puis réinsertion dans l'enveloppe
- Attention aux caractères spéciaux (guillemets, newlines, unicode)
- **Gestion des erreurs** : si un enregistrement est malformé (double-parse échoué), le script le skip, le logge sur stderr avec son index et son `DOAR_IDENT`, et continue. Un compteur d'erreurs est affiché en fin de traitement
- **Progression** : affichage d'un compteur sur stderr toutes les 1000 entrées (`[12000/31891]`) pour rendre l'attente supportable sur un traitement de 2-3 minutes

### Tableau de correspondances (mode `--pseudo` uniquement)

Fichier CSV en UTF-8 avec séparateur `;` (pour éviter les conflits avec les virgules dans les valeurs).

```csv
type;jeton;valeur_originale
id;[ID_1];10786453
uuid;[UUID_1];89e4000b-5d4d-4077-92fe-812e2c298046
prenom;[PRENOM_1];farid
nom;[NOM_1];abdelkader
email;[EMAIL_1];motardzen1@gmail.com
tel;[TEL_1];09 75 73 94 62
cp;[CP_1];94110
genre;[GENRE_1];Male
```

**Sécurité du fichier de correspondances** :

Le CSV est la clé de dépseudonymisation — il contient toutes les données personnelles en clair.

- Stocké dans un dossier séparé `virginie/confidentiel/` (pas à côté du JSON pseudonymisé)
- Ajouté au `.gitignore` — ne jamais commiter
- Ne jamais partager avec Claude ni un service externe
- Permissions restrictives : `chmod 600`
- Pas de chiffrement nécessaire tant que le fichier reste sur la machine locale d'Alex

---

## Risques identifiés

| Risque | Sévérité | Mitigation |
|--------|----------|------------|
| Noms dans le texte libre | Élevée | Lookup direct Firstname/Lastname + regex noms |
| Cohérence inter-enregistrements | Élevée | Table de correspondances globale (même personne = même jeton) |
| Double-parse JSON corrompu | Moyenne | Validation structure avant/après, comptage enregistrements |
| Faux positifs regex (codes postaux dans des numéros de commande) | Moyenne | Ne scanner les CP que dans le texte libre si contexte adresse |
| Noms de tiers dans le texte libre | Faible | Les regex génériques (salutation, titre) couvrent partiellement |
| Noms de personnes dans `Files[].FileName` | Faible | Hors périmètre documenté — les métadonnées de PJ peuvent contenir des noms (ex: `facture_dupont.pdf`) |

---

## Hors périmètre

- Pseudonymisation des pièces jointes (`Files[]` contient des métadonnées, pas le contenu)
- Adaptation de l'interface navigateur Pseudonymus (approche script uniquement)
- Ré-identification par croisement contextuel (CP + catégorie + date)
- Traitement des SIRET d'auto-entrepreneurs
- Script de dépseudonymisation (le CSV de correspondances le permet, mais l'outil inverse sera écrit ultérieurement si besoin)

---

## Critères de validation

1. Le JSON de sortie a la même structure et le même nombre d'enregistrements (31 891 moins les éventuels enregistrements malformés skippés, loggés sur stderr)
2. Aucun champ Firstname, Lastname, Email, Phone, ConsumerPhone, Gender, Id, DOAR_IDENT ne contient de valeur originale
3. Le texte libre ne contient plus les noms/prénoms du déclarant
4. **Mode pseudo** : le tableau de correspondances permet la dépseudonymisation
5. **Mode anon** : aucune valeur originale n'est récupérable, pas de fichier de correspondances produit
6. Le `--dry-run` sur 100 enregistrements affiche les stats sans écrire de fichier
7. Un échantillon aléatoire de 100 enregistrements est inspecté manuellement pour vérifier l'absence de fuites
8. Le script s'exécute en < 5 minutes sur la machine locale

---

## Séquence de travail

1. Alex valide ce PRD
2. Claude écrit le script `pseudonymise-json.py` (sans lire les données)
3. Alex lance `--dry-run` et vérifie les stats
4. Alex lance le mode choisi (`--pseudo` ou `--anon`)
5. Alex inspecte un échantillon du JSON de sortie
6. Alex partage le JSON pseudonymisé/anonymisé avec Claude
7. Claude peut travailler sur les données nettoyées
