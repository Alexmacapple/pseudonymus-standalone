# Guide utilisateur — Pseudonymisation JSON SignalConso

---

## Pourquoi ce projet existe

On a un fichier JSON de 112 Mo contenant 31 891 réclamations consommateurs issues de SignalConso. Ce fichier contient des données personnelles : noms, prénoms, emails, téléphones, adresses, codes postaux, numéros de sécurité sociale, etc.

**Le problème** : on veut analyser ces données avec Claude (ou un autre LLM), mais on ne peut pas lui envoyer des données personnelles en clair. C'est une obligation RGPD et un choix de sécurité.

**La solution** : un script Python qui tourne en local, remplace toutes les données personnelles par des jetons (`[PRENOM_1]`, `[EMAIL_3]`, etc.), et produit un fichier nettoyé qu'on peut partager en toute sécurité.

**L'origine** : les regex de détection viennent de Pseudonymus v2, une application web qui fait la même chose dans le navigateur. Mais Pseudonymus ne peut pas avaler 112 Mo — on a donc porté sa logique dans un script Python capable de traiter le fichier en batch.

---

## Les 4 scripts

Le projet contient 4 scripts Python. Aucun n'a besoin d'installation (`pip install`) — ils utilisent uniquement la bibliothèque standard Python 3.

| Script | Rôle | Durée |
|--------|------|-------|
| `pseudonymise-json.py` | Script principal — pseudonymise ou anonymise le JSON | ~2 min |
| `verif-sample.py` | Vérification rapide — affiche 1 enregistrement | < 1 sec |
| `verif-complet.py` | Audit automatisé — vérifie 100 enregistrements au hasard | ~30 sec |
| `test-options.py` | Tests complets — vérifie toutes les options du script (35 tests) | ~5 min |

---

## Script 1 : `pseudonymise-json.py`

### À quoi il sert

C'est le script principal. Il lit le JSON SignalConso, détecte les données personnelles, les remplace, et produit un nouveau JSON nettoyé.

### Comment il a été construit

1. **Les regex viennent de Pseudonymus v2** (`public/assets/js/app.js`). Elles détectent les emails, téléphones, NIR, IBAN, cartes bancaires, adresses. On les a adaptées de JavaScript vers Python (les deux langages ont des dialectes regex légèrement différents — notamment les lookbehind).

2. **Le lookup noms** est une couche supplémentaire. Pour chaque enregistrement, le script cherche le prénom et le nom du déclarant directement dans le texte libre. Ça attrape les cas où quelqu'un écrit « Bonjour, je suis Marie Dupont et... » dans sa réclamation.

3. **La table de correspondances** associe chaque valeur originale à un jeton unique. Si le même email apparaît dans 50 réclamations, il obtient le même jeton partout — ce qui permet de garder les corrélations sans exposer l'identité.

### Comment il fonctionne (les 3 phases)

**Phase 1 — Champs structurés.** Le JSON contient des champs dédiés (Firstname, Lastname, Email, Phone, PostalCode, Gender, etc.). Le script les remplace directement.

**Phase 2 — Texte libre.** Les champs Question, Description et Details[].Value contiennent du texte rédigé par les consommateurs. Le script y cherche :
- Le prénom et le nom du déclarant (lookup direct, insensible à la casse)
- Les emails (y compris obfusqués : `nom [at] domaine [dot] fr`)
- Les numéros de sécurité sociale (NIR, avec validation de structure)
- Les IBAN
- Les numéros de carte bancaire (avec validation Luhn, excluant les SIRET de 9 et 14 chiffres)
- Les numéros de téléphone (formats français : 06, +33, 0033)
- Les adresses postales numérotées (« 43 rue Pierre Brossolette »)

L'ordre d'application des regex compte : les emails sont traités en premier pour ne pas être cassés par les regex suivantes, le NIR passe avant les téléphones pour éviter les collisions sur les suites de chiffres.

**Phase 3 — Ré-sérialisation.** Le JSON de SignalConso a une particularité : le champ `RCLMFicheReportJsonSC` contient une chaîne JSON dans du JSON (comme une poupée russe). Le script ouvre les deux couches, travaille, puis referme dans le bon ordre.

### Les 3 modes

**`--dry-run`** : traite les 100 premiers enregistrements et affiche un rapport (nombre de remplacements par type, échantillons). N'écrit aucun fichier. Sert à vérifier que les regex fonctionnent correctement avant de lancer le traitement complet.

**`--pseudo`** : pseudonymisation réversible. Remplace les données par des jetons (`[PRENOM_1]`, `[EMAIL_3]`...) et produit un fichier CSV de correspondances pour pouvoir revenir aux données originales si besoin.

**`--anon`** : anonymisation irréversible. Remplace les données par des valeurs génériques (`***`, `anonyme@example.com`, `00 00 00 00 00`). Pas de table de correspondances. Les données originales sont perdues définitivement.

### Tableau des remplacements

| Champ | Mode pseudo | Mode anon |
|-------|-------------|-----------|
| DOAR_IDENT | `[ID_X]` | Compteur (1, 2, 3...) |
| Id (UUID) | `[UUID_X]` | UUID v4 régénéré |
| Firstname | `[PRENOM_X]` | `***` |
| Lastname | `[NOM_X]` | `***` |
| Email | `[EMAIL_X]` | `anonyme@example.com` |
| Phone / ConsumerPhone | `[TEL_X]` | `00 00 00 00 00` |
| PostalCode | `[CP_X]` | `00000` |
| Gender | `[GENRE_X]` | `Non renseigné` |
| Données dans le texte libre | `[TEL_X]`, `[EMAIL_X]`, etc. | `[SUPPRIMÉ]` |

### Comment le lancer

```bash
cd /Users/alex/Claude/active/pseudonymus2

# Étape 1 : tester sur un échantillon (toujours commencer par là)
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --dry-run

# Étape 2 : pseudonymiser (réversible)
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --pseudo

# OU anonymiser (irréversible)
python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --anon
```

### Ce qu'il produit

| Mode | Fichier produit | Description |
|------|----------------|-------------|
| `--pseudo` | `virginie/CourrierSRCAvecParag_2025_7_5_PSEUDO.json` | JSON pseudonymisé (partageable) |
| `--pseudo` | `virginie/confidentiel/correspondances.csv` | Table de correspondances (confidentiel) |
| `--anon` | `virginie/CourrierSRCAvecParag_2025_7_5_ANON.json` | JSON anonymisé (partageable) |
| `--dry-run` | *(aucun fichier)* | Rapport affiché dans le terminal |

### Ce qu'il affiche pendant l'exécution

- Progression toutes les 1000 entrées : `[12000/31891]`
- En cas d'enregistrement malformé : message d'erreur avec l'index et l'identifiant, puis continuation
- En fin de traitement : rapport complet avec le nombre de remplacements par type et 5 échantillons par catégorie

### Le cas des prénoms courts

Un prénom de 3 lettres comme « Léa », « Eva » ou « Aya » peut matcher des mots courants dans le texte. Pour éviter les faux positifs, le script ne cherche ces prénoms que lorsqu'ils sont combinés avec le nom de famille. Par exemple, si le déclarant s'appelle « Eva Martin », le script cherchera « Eva Martin » et « Martin Eva » dans le texte, mais pas « Eva » tout seul.

Les prénoms de 4 lettres et plus sont cherchés individuellement.

### Sécurité du fichier de correspondances

Le fichier `virginie/confidentiel/correspondances.csv` est la clé de dépseudonymisation. Il contient toutes les données personnelles en clair, organisées ainsi :

```csv
type;jeton;valeur_originale
prenom;[PRENOM_1];farid
nom;[NOM_1];abdelkader
email;[EMAIL_1];motardzen1@gmail.com
tel;[TEL_1];09 75 73 94 62
```

Mesures de sécurité appliquées automatiquement par le script :
- Stocké dans un dossier séparé `virginie/confidentiel/` (pas à côté du JSON)
- Permissions `chmod 600` (seul le propriétaire peut lire/écrire)
- Un fichier `.gitignore` est créé dans le dossier pour empêcher tout commit accidentel

**Règles** : ne jamais envoyer ce fichier à Claude, ne jamais le partager, ne jamais le commiter.

---

## Script 2 : `verif-sample.py`

### À quoi il sert

Vérification rapide en 2 secondes. Affiche les champs sensibles du premier enregistrement du JSON pseudonymisé pour vérifier visuellement que les jetons sont bien en place.

### Comment le lancer

```bash
python3 verif-sample.py
```

### Ce qu'il affiche

```
Firstname: [PRENOM_1]
Lastname: [NOM_1]
Email: [EMAIL_1]
ConsumerPhone: [TEL_1]
PostalCode: [CP_1]
Gender: [GENRE_1]
Id: [UUID_1]
Question: bonjour, orange me réclame  300 euros pour non restituions de...
```

**Si un champ affiche un nom, un email ou un téléphone en clair au lieu d'un jeton, la pseudonymisation a échoué.**

---

## Script 3 : `verif-complet.py`

### À quoi il sert

Audit automatisé. Tire 100 enregistrements au hasard dans le JSON pseudonymisé et vérifie qu'aucune donnée personnelle n'a survécu.

### Comment il a été construit

Le script utilise une seed fixe (`random.seed(42)`) pour que les mêmes 100 enregistrements soient tirés à chaque exécution — ce qui rend les résultats reproductibles.

Il vérifie deux choses :
1. **Champs structurés** : chaque champ sensible doit contenir un jeton (`[PRENOM_X]`), une valeur anonyme (`***`) ou être vide. Toute autre valeur est signalée comme fuite.
2. **Texte libre** : aucune adresse email en clair ne doit subsister dans les champs Question et Description (sauf `example.com` qui est la valeur de remplacement en mode anon).

### Comment le lancer

```bash
python3 verif-complet.py
```

### Ce qu'il affiche si tout va bien

```
Critère 1 : 31891 enregistrements (attendu : 31891)
Critère 7 : inspection de 100 enregistrements aléatoires
Aucune fuite détectée sur les champs structurés et emails texte libre.

Échantillon visuel (5 enregistrements) :
============================================================
[20952] DOAR=[ID_20953]
  Firstname: [PRENOM_204]
  Lastname: [NOM_15205]
  Email: [EMAIL_20102]
  ...
```

### Ce qu'il affiche si une fuite est détectée

```
FUITES DÉTECTÉES : 3
  [1234] Firstname = Jean
  [5678] Email = jean@gmail.com
```

Le script retourne un code de sortie 1 en cas de fuite. Investiguer avant de partager le JSON.

---

## Script 4 : `test-options.py`

### À quoi il sert

Suite de tests automatisés qui vérifie que toutes les options du script principal fonctionnent correctement. C'est le filet de sécurité : si on modifie le script, on relance les tests pour s'assurer qu'on n'a rien cassé.

### Ce qu'il teste (35 tests)

| Catégorie | Tests |
|-----------|-------|
| Fichier inexistant | Erreur correcte, message explicite |
| Aucun mode spécifié | Erreur correcte, message d'usage |
| Deux modes en même temps | Erreur correcte, exclusion mutuelle |
| `--dry-run` | Pas de fichier écrit, rapport affiché, 100 enregistrements |
| `--pseudo` | JSON + CSV produits, jetons en place, permissions 600, header CSV correct |
| `--anon` | JSON produit, `***` en place, compteur DOAR_IDENT, UUID régénéré, Gender anonymisé |

### Comment le lancer

```bash
python3 test-options.py
```

**Attention** : ce script relance le traitement complet en mode pseudo et anon. Compter environ 5 minutes d'exécution.

### Ce qu'il affiche

```
=== TEST 1 : Fichier inexistant ===
  OK  Code retour non-zero
  OK  Message erreur sur stderr

=== TEST 2 : Aucun mode specifie ===
  OK  Code retour non-zero
  OK  Message usage sur stderr

...

============================================================
RESULTATS : 35 OK / 0 FAIL / 35 total
Tous les tests passent.
```

---

## Procédure complète pas à pas

Voici l'ordre exact des opérations pour pseudonymiser le fichier :

```
1. Se placer dans le dossier du projet
   cd /Users/alex/Claude/active/pseudonymus2

2. Tester sur un échantillon
   python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --dry-run
   → Lire le rapport. Vérifier que les stats sont cohérentes.
     Pas de faux positifs aberrants ? Pas d'erreurs de parse ?

3. Lancer la pseudonymisation
   python3 pseudonymise-json.py virginie/CourrierSRCAvecParag_2025_7_5.json --pseudo
   → Attendre ~2 minutes. Progression affichée toutes les 1000 entrées.

4. Vérification rapide
   python3 verif-sample.py
   → Les champs affichent des jetons ? OK.

5. Audit complet
   python3 verif-complet.py
   → "Aucune fuite détectée" ? OK.
   → "FUITES DÉTECTÉES" ? Investiguer avant de partager.

6. Le fichier virginie/CourrierSRCAvecParag_2025_7_5_PSEUDO.json est prêt.
   Le CSV de correspondances reste en local (ne jamais partager).
```

---

## Ce qui n'est PAS traité (et pourquoi)

| Élément | Raison |
|---------|--------|
| Noms de tiers dans le texte libre | Seuls les noms du déclarant sont lookupés. Détecter les noms de tiers nécessiterait un modèle NLP complet — trop de faux positifs avec des regex seules |
| Adresses sans numéro (« rue Victor Hugo ») | La regex produisait 37% de faux positifs (« allée dans un magasin »). Retirée volontairement |
| Pièces jointes (`Files[]`) | Le JSON contient les métadonnées des PJ (nom de fichier, taille) mais pas leur contenu. Les noms de fichiers pourraient contenir des noms de personnes — non traité |
| SIRET d'auto-entrepreneurs | Le SIRET identifie une entreprise, mais pour un auto-entrepreneur c'est un identifiant personnel indirect. Non traité par défaut |
| Ré-identification par croisement | CP + catégorie + date peut réduire l'anonymat. C'est inhérent à la pseudonymisation — seule l'anonymisation complète (mode `--anon`) y remédie partiellement |

---

## Structure du fichier JSON

Pour comprendre les scripts, il faut connaître la structure du JSON SignalConso :

```
[                                          ← Array de 31 891 objets
  {
    "DOAR_IDENT": 10786453,               ← Identifiant enveloppe (traçable)
    "RCLMFicheReportJsonSC": "{ ... }",   ← JSON stringifié (poupée russe)
    "TypeTraitementIdent": 5,
    "TypeTraitementLibelle": "Compléments"
  },
  ...
]
```

Le champ `RCLMFicheReportJsonSC` est une chaîne JSON qui, une fois parsée, contient :

```
{
  "Report": {
    "Id": "89e4000b-...",              ← UUID (traçable)
    "Firstname": "farid",              ← Prénom
    "Lastname": "abdelkader",          ← Nom
    "Email": "motardzen1@gmail.com",   ← Email
    "Phone": null,                     ← Téléphone (rare)
    "ConsumerPhone": "09 75 73 94 62", ← Téléphone consommateur
    "PostalCode": "94110",             ← Code postal
    "Gender": "Male",                  ← Genre
    "Category": "Téléphonie / ...",    ← Catégorie (conservée)
    "Question": "bonjour, orange...",  ← Texte libre (scanné)
    "Description": "https://...",      ← Description (scannée)
    "Details": [                       ← Détails (scannés)
      {"Label": "Date du constat :", "Value": "05/09/2023"},
      {"Label": "Votre question :", "Value": "bonjour, orange..."}
    ],
    "Siret": "38012986645100",         ← SIRET (conservé)
    ...
  },
  "Files": [...],                      ← Métadonnées PJ (non traitées)
  "ErrorMessage": null
}
```

Le script doit donc :
1. Parser le JSON externe
2. Parser la chaîne `RCLMFicheReportJsonSC`
3. Travailler sur le `Report`
4. Re-sérialiser le `Report` en chaîne
5. Remettre la chaîne dans l'enveloppe

C'est le double-parse décrit en Phase 3.
