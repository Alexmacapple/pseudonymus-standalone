# PRD — Internalisation complète du répertoire generique/

**Statut** : Proposé
**Date** : 2026-03-26
**Auteur** : Alex
**Priorité** : Haute
**Effort estimé** : Faible (< 1h)

---

## Contexte

Le répertoire `generique/` est le coeur autonome de Pseudonymus v3 : moteur de pseudonymisation Python, serveur HTTP, interface DSFR. Il fonctionne déjà de manière quasi-autonome, mais trois dépendances vers des répertoires externes (`public/`, `virginie/`) subsistent dans deux fichiers et dans la mécanique de test. Par ailleurs, trois fichiers structurants manquent pour qu'un développeur externe puisse cloner et lancer le projet. L'objectif est d'éliminer ces dépendances et combler ces manques pour que `generique/` soit un dépôt git 100% autonome, clonnable et exécutable sans aucun fichier externe.

---

## Analyse des dépendances

### Dépendance 1 : `convertir-donnees.py` vers `public/assets/js/vendor/`

| Aspect | Détail |
|--------|--------|
| **Fichier** | `generique/convertir-donnees.py` |
| **Lignes** | 16-18, 35, 55 |
| **Nature** | Le script lit `public/assets/js/vendor/noms.js` (16 Mo, 884 314 patronymes) et `public/assets/js/vendor/prenoms-fr.js` (1,8 Mo, 169 244 prénoms) pour générer `generique/data/noms.json` et `generique/data/prenoms.json` |
| **Impact** | Utilitaire de régénération uniquement. Les JSON cibles existent déjà dans `generique/data/` et sont chargés par `pseudonymise.py`. Le script ne sert qu'en cas de mise à jour des listes sources. |
| **Risque** | Nul sur le fonctionnement. Seule la régénération des données est impactée si on exécute ce script hors du repo complet. |

### Dépendance 2 : `test-options.py` vers `virginie/`

| Aspect | Détail |
|--------|--------|
| **Fichier** | `generique/test-options.py` |
| **Lignes** | 9, 169 |
| **Nature** | Le test 11 (mapping SignalConso) charge `virginie/CourrierSRCAvecParag_2025_7_5.json` pour créer un mini-jeu de 5 enregistrements et tester le mapping SignalConso. Le test est protégé par un `if os.path.exists()` avec skip gracieux. |
| **Impact** | Test optionnel uniquement. Les 12 autres tests fonctionnent sans ce fichier. |
| **Risque** | Nul. Le skip fonctionne correctement. |

### Dépendance 3 : `cwd=BASE` dans `test-options.py`

| Aspect | Détail |
|--------|--------|
| **Fichier** | `generique/test-options.py` |
| **Lignes** | 9, 32, 38 |
| **Nature** | Les fonctions `run()` et `run_depseudo()` lancent les sous-processus avec `cwd=BASE` (racine du projet). `BASE` est calculé via `os.path.dirname(os.path.dirname(__file__))`, ce qui ancre l'exécution hors de `generique/`. Tous les chemins relatifs passés en arguments aux 13 tests sont résolus depuis cette racine. |
| **Impact** | **Bloquant.** Supprimer `BASE` sans adapter `cwd` et les chemins d'arguments casse l'intégralité des tests. |
| **Risque** | Élevé si non traité. C'est une dépendance structurelle, pas juste un chemin de fichier. |

### Manque 1 : pas de `requirements.txt`

| Aspect | Détail |
|--------|--------|
| **Impact** | `formats.py` importe 4 packages tiers optionnels (`openpyxl`, `odfpy`, `python-docx`, `pdfplumber`) avec try/except et message d'erreur clair. Mais un développeur qui clone le dépôt ne sait pas quoi installer. |
| **Risque** | Friction au setup. Crash inattendu sur XLSX/DOCX/ODS/PDF sans message avant l'exécution. |

### Manque 2 : pas de `.gitignore` racine

| Aspect | Détail |
|--------|--------|
| **État actuel** | Seul `exemples/confidentiel/.gitignore` existe (contenu : `*`). Pas de `.gitignore` à la racine de `generique/`. |
| **Risque** | `.DS_Store`, `__pycache__/`, fichiers temporaires de test (`_test_sc_mini.json`) risquent d'être commités. Le dossier `confidentiel/` est protégé par son propre `.gitignore`, mais c'est fragile. |

### Manque 3 : pas de licence

| Aspect | Détail |
|--------|--------|
| **État actuel** | La racine du projet contient `licence.lic` (GPL v3). Mais `generique/` n'a aucun fichier de licence propre. |
| **Risque** | Un dépôt sans licence = droits d'auteur exclusifs par défaut. Aucun tiers ne peut légalement réutiliser le code. |

---

## Objectif

Rendre `generique/` intégralement autonome comme dépôt git indépendant :
- Zéro import, zéro chemin, zéro référence vers un fichier hors de `generique/`
- Tous les fichiers structurants d'un dépôt clonnable présents

**Critère de validation** : `grep -rn '\.\./' generique/*.py` ne retourne aucun résultat. Tous les tests passent depuis `generique/` seul. Un `git clone` + `pip install` + `python3 serveur.py` fonctionne sans documentation orale.

---

## Solution retenue

### Action 1 — Réécrire `convertir-donnees.py` en script autonome

**Avant** : Le script navigue vers `public/assets/js/vendor/` pour extraire noms et prénoms depuis des fichiers JS v2.

**Après** : Le script ne génère plus que les 7 fichiers de données statiques (stopwords, majuscules, villes, organisations, contexte, acronymes) dont les valeurs sont déjà en dur dans le script. Les fichiers `noms.json` et `prenoms.json` deviennent des données de référence immuables livrées avec `generique/data/` — ils ne sont plus régénérés.

**Modifications** :
1. Supprimer les lignes 16-18 (calcul de `BASE` et `JS_DIR`)
2. Remplacer `DATA_DIR` par un chemin relatif au script : `os.path.join(os.path.dirname(__file__), 'data')`
3. Supprimer les sections 1 (patronymes) et 2 (prénoms) qui lisent les JS externes (lignes 31-65)
4. Conserver les sections 3-8 (données hardcodées) telles quelles
5. Mettre à jour la docstring

**Justification** : Les fichiers `noms.json` (11,6 Mo) et `prenoms.json` (1,9 Mo) sont déjà générés et stables. Ils proviennent de listes publiques (INSEE/Open Data) et n'ont pas vocation à changer fréquemment. Si une mise à jour est nécessaire un jour, un script dédié pourra être écrit à ce moment.

### Action 2 — Internaliser le jeu de test SignalConso

**Avant** : Le test 11 charge un fichier de `virginie/` (données réelles confidentielles).

**Après** : Créer un fichier `generique/exemples/test-signalconso.json` contenant 5 enregistrements synthétiques au format SignalConso (mêmes champs, données fictives). Le test 11 pointe vers ce fichier interne.

**Modifications** :
1. Créer `generique/exemples/test-signalconso.json` avec 5 enregistrements synthétiques
2. Modifier `test-options.py` ligne 169 : remplacer le chemin `virginie/` par le chemin local
3. Supprimer le `if os.path.exists()` conditionnel : le test ne doit plus être optionnel, les données sont toujours présentes

**Structure exacte d'un enregistrement synthétique** (JSON-in-JSON, requis pour le unwrap) :

```json
{
  "DOAR_IDENT": 10000001,
  "RCLMFicheReportJsonSC": "{\"Report\":{\"Id\":\"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\",\"Gender\":\"Female\",\"Category\":\"Catégorie fictive\",\"Subcategories\":[\"Sous-cat 1\"],\"Details\":[{\"Label\":\"Date du constat :\",\"Value\":\"01/01/2025\"},{\"Label\":\"Description :\",\"Value\":\"Texte libre avec le nom Dupont et le prénom Marie.\"},{\"Label\":\"Votre question :\",\"Value\":\"Question fictive mentionnant jean.martin@email.fr\"}],\"Siret\":\"12345678901234\",\"PostalCode\":\"75001\",\"Firstname\":\"Marie\",\"Lastname\":\"Dupont\",\"Email\":\"marie.dupont@example.fr\",\"ContactAgreement\":false,\"Description\":\"Description libre\",\"Question\":\"Question libre\",\"Phone\":\"01 23 45 67 89\",\"ConsumerPhone\":\"06 12 34 56 78\"}}"
}
```

Points critiques :
- `RCLMFicheReportJsonSC` est une **chaîne JSON sérialisée** (JSON dans du JSON), pas un objet
- Le mapping utilise `unwrap` + `parse: "json_string"` pour désérialiser avant traitement
- Les champs imbriqués utilisent la notation pointée (`Report.Firstname`, `Report.Details[].Value`)
- Les 5 enregistrements doivent contenir des prénoms/noms/emails/UUID variés dans les champs structurés ET dans le texte libre (`Details[].Value`, `Question`, `Description`) pour valider la détection croisée

### Action 3 — Réécrire `cwd` et les chemins de `test-options.py`

**Avant** : `BASE` pointe vers la racine du projet. `run()` et `run_depseudo()` utilisent `cwd=BASE`. Les arguments passent des chemins relatifs à cette racine (ex: `generique/exemples/test-clients.json`).

**Après** : `cwd` pointe vers `generique/` (le répertoire du script). Tous les chemins d'arguments deviennent relatifs à `generique/`.

**Modifications** :
1. Remplacer `BASE = os.path.dirname(os.path.dirname(...))` par `SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))` (ligne 9)
2. Remplacer `cwd=BASE` par `cwd=SCRIPT_DIR` dans `run()` (ligne 32) et `run_depseudo()` (ligne 38)
3. Adapter les chemins d'arguments des scripts appelés : `SCRIPT` et `DEPSEUDO` sont déjà relatifs au script (ligne 7-8, utilisant `os.path.dirname(__file__)`), donc compatibles
4. Vérifier que les chemins passés en arguments CLI dans les 13 tests sont relatifs à `generique/` (ex: `exemples/test-clients.json` au lieu de `generique/exemples/test-clients.json`)
5. Aligner la variable `sc_source` du test 11 sur le nouveau chemin interne

### Action 4 — Créer `requirements.txt`

Fichier à la racine de `generique/` avec deux sections :

```
# Aucune dépendance pour le coeur (JSON, CSV, serveur HTTP, interface)
# Dépendances optionnelles selon les formats utilisés :

openpyxl>=3.0        # Excel XLSX
odfpy>=1.4           # OpenDocument ODS/ODT
python-docx>=0.8     # Word DOCX
pdfplumber>=0.9      # PDF (lecture seule)
```

**Note** : Le coeur (pseudonymisation JSON/CSV, serveur, interface) fonctionne avec zéro dépendance externe — uniquement la stdlib Python 3.8+. Les 4 packages ci-dessus ne sont nécessaires que pour les formats bureautiques.

### Action 5 — Créer `.gitignore`

```
# Données sensibles
confidentiel/correspondances.csv

# Python
__pycache__/
*.pyc
*.pyo

# Fichiers temporaires
_test_*.json
*.tmp

# OS
.DS_Store
```

**Note** : `exemples/confidentiel/.gitignore` (contenu : `*`) est conservé comme double protection.

### Action 6 — Copier la licence

Copier `licence.lic` (GPL v3) depuis la racine du projet vers `generique/LICENSE`.

---

## Fichiers impactés

| Fichier | Action |
|---------|--------|
| `generique/convertir-donnees.py` | Réécriture : suppression des imports JS externes |
| `generique/test-options.py` | Modification : `cwd`, chemins, test 11 internalisé |
| `generique/exemples/test-signalconso.json` | Création : 5 enregistrements synthétiques JSON-in-JSON |
| `generique/requirements.txt` | Création : dépendances optionnelles documentées |
| `generique/.gitignore` | Création : exclusions Python, OS, données sensibles |
| `generique/LICENSE` | Copie : GPL v3 depuis la racine |

---

## Plan d'exécution

1. Créer `generique/requirements.txt`, `generique/.gitignore`, `generique/LICENSE`
2. Créer `generique/exemples/test-signalconso.json` (5 enregistrements JSON-in-JSON, structure documentée ci-dessus)
3. Réécrire `test-options.py` : `SCRIPT_DIR` remplace `BASE`, `cwd=SCRIPT_DIR`, chemins relatifs adaptés, test 11 pointe vers le fichier interne, skip supprimé
4. Réécrire `convertir-donnees.py` : suppression sections noms/prénoms + `DATA_DIR` relatif au script
5. Exécuter `python3 generique/test-options.py` — tous les tests doivent passer, aucun SKIP
6. Exécuter `python3 generique/test-v3.py` — non-régression
7. Vérifier `grep -rn '\.\./\|virginie\|public/\|cwd=BASE' generique/*.py` — aucun résultat
8. Test d'isolation : copier `generique/` dans `/tmp/`, lancer `python3 serveur.py` et `python3 test-options.py` depuis la copie

---

## Hors périmètre

- Modification de `pseudonymise.py`, `serveur.py`, `formats.py`, `depseudonymise.py` (déjà autonomes)
- Modification de l'interface DSFR (déjà autonome)
- Mise à jour des listes noms/prénoms (hors scope, données stables)
- Suppression des répertoires `public/`, `virginie/`, `specifique/` (décision séparée)

---

## Connus inconnus

| Risque | Sévérité | Mitigation |
|--------|----------|------------|
| Les chemins relatifs des 13 tests après changement de `cwd` | Bloquante | `SCRIPT` et `DEPSEUDO` utilisent déjà `os.path.dirname(__file__)` (lignes 7-8), donc OK. Les chemins en arguments CLI (`TEST_JSON`, `MAPPING_PLAT`, etc., lignes 11-13) utilisent `EXEMPLES` qui est aussi relatif à `__file__`. Seul `cwd` doit changer. Vérifier en exécutant les 13 tests. |
| Fidélité des données synthétiques SignalConso | Moyenne | La structure JSON-in-JSON est documentée ci-dessus avec un exemple complet. Les assertions du test 11 vérifient : code retour 0, `5/5`, détection prenom/nom/email/uuid, absence de `ERREUR`. Les données synthétiques doivent contenir ces 4 types dans les bons champs. |
| Assertions de comptage hardcodées (test 13) | Faible | Le test 13 vérifie `884314 patronymes` et `169244 prenoms`. Ces valeurs correspondent aux fichiers `data/noms.json` et `data/prenoms.json` déclarés immuables. Risque accepté. |

---

## Critères d'acceptation

### Zéro dépendance externe

- [ ] `grep -rn '\.\./\|virginie\|public/\|cwd=BASE' generique/*.py` ne retourne aucun résultat
- [ ] `python3 generique/test-options.py` : 100% des tests passent (aucun SKIP)
- [ ] `python3 generique/test-v3.py` : non-régression OK
- [ ] `python3 generique/convertir-donnees.py` : régénère les 7 fichiers de données statiques sans erreur

### Dépôt clonnable

- [ ] `generique/requirements.txt` présent avec les 4 dépendances optionnelles
- [ ] `generique/.gitignore` présent (exclut `__pycache__/`, `.DS_Store`, données sensibles)
- [ ] `generique/LICENSE` présent (GPL v3)

### Test d'isolation

- [ ] Copier `generique/` seul dans `/tmp/test-isolation/`, lancer `python3 serveur.py --port 9999` : le serveur démarre et sert l'interface
- [ ] Depuis cette copie, `python3 test-options.py` : tous les tests passent
- [ ] Depuis cette copie, `python3 pseudonymise.py exemples/test-clients.json --mapping exemples/mapping-clients.json --dry-run` : fonctionne
