# PRD — Parite fonctionnelle CLI / interface web

**Statut** : Propose
**Date** : 2026-03-26
**Auteur** : Alex
**Priorite** : Moyenne
**Effort estime** : Modere (2-3h)
**Prerequis** : PRD internalisation generique/ (termine)

---

## Contexte

L'audit de parite CLI / interface a revele 2 ecarts fonctionnels. L'ecart initialement identifie sur `--nlp` et `--tech` dans la page Pseudonymisation texte est invalide : ces options sont deja presentes (HTML lignes 122-131, JS lignes 80-81).

L'objectif est que tout ce qu'un utilisateur peut faire en CLI soit faisable depuis l'interface web, sans recourir au terminal.

---

## Ecarts identifies

### Ecart 1 : `--dry-run` absent de l'interface

| Aspect | Detail |
|--------|--------|
| **CLI** | `python3 pseudonymise.py fichier.json --mapping m.json --dry-run` traite les 100 premiers enregistrements, affiche un rapport complet (remplacements, score RGPD, echantillons) et ne produit aucun fichier |
| **Interface** | La page Import fichier traite l'integralite du fichier. Pas d'option pour limiter ou previsualiser. |
| **Impact** | Sur un fichier de 500 000 enregistrements, l'utilisateur doit attendre le traitement complet pour verifier que son mapping est correct. Le dry-run permet de valider en quelques secondes. |

### Ecart 2 : `--input-dir` absent de l'interface

| Aspect | Detail |
|--------|--------|
| **CLI** | `python3 pseudonymise.py dummy --mapping m.json --input-dir /chemin/dossier/ --pseudo` traite tous les `.json` du dossier en sequence |
| **Interface** | La page Import fichier accepte un seul fichier a la fois |
| **Impact** | Un utilisateur avec 50 fichiers JSON doit les traiter un par un. Le traitement batch est une fonctionnalite de productivite importante. |

---

## Solution retenue

### Action 1 — Ajouter le dry-run a l'interface

#### Serveur (`serveur.py`)

Modifier `_handle_pseudonymise_local()` (ligne 209) pour accepter un parametre `dry_run` :

- Lire `dry_run = body.get('dry_run', False)` apres les autres parametres (ligne ~219)
- Si `dry_run` est vrai, limiter les donnees apres chargement : `data = data[:100]` (apres ligne 250)
- **Point de coupure** : apres la boucle de traitement (ligne 270), avant l'ecriture. Le code actuel enchaine :
  - Ligne 277 : `output_path = save_file(...)` — skipper
  - Lignes 280-284 : export CSV — skipper
  - Lignes 292-301 : creation zip — skipper
- En dry-run, sauter directement a la reponse JSON avec `output_path = None`, `csv_path = None`, `zip_path = None`
- Ajouter `"dry_run": true` dans la reponse

Modifier `_handle_pseudonymise()` (upload classique, ligne 123) — **comportement different** :

- Cette route ne produit deja aucun fichier sur disque (elle retourne `data: output` dans le JSON)
- Le dry-run consiste uniquement a limiter `data = data[:100]` avant la boucle (ligne 177)
- Pas de fichier a ne pas ecrire — le gain est purement sur le temps de traitement

#### Interface (`app.js` + `index.html`)

Sur la page Import fichier :

1. Ajouter un bouton "Previsualiser" (DSFR `fr-btn--secondary`) a cote de "Lancer le traitement"
2. Ce bouton envoie la meme requete avec `dry_run: true`
3. Afficher le resultat dans une zone dediee :
   - Nombre d'enregistrements testes (sur 100)
   - Nombre de remplacements
   - Score RGPD
   - Tableau des 10 premiers remplacements (type, original, jeton) pour verification visuelle
4. Ne pas afficher les boutons de telechargement en mode dry-run

#### Comportement attendu

```
Utilisateur clique "Previsualiser"
  -> Requete POST /api/pseudonymise-local {path, mapping, dry_run: true}
  -> Serveur traite 100 enregistrements, pas d'ecriture
  -> Interface affiche : "100 enregistrements testes, 347 remplacements, Score RGPD 42 (Eleve)"
  -> Tableau : 10 premiers remplacements pour verification
  -> Utilisateur valide le mapping, clique "Lancer le traitement" pour tout traiter
```

### Action 2 — Ajouter le traitement par lot a l'interface

#### Serveur (`serveur.py`)

Ajouter une route `POST /api/pseudonymise-batch` :

```python
def _handle_pseudonymise_batch(self):
    """Traite tous les fichiers d'un dossier."""
    body = self._read_json_body()
    dir_path = body.get('path', '')      # chemin du dossier
    mapping = body.get('mapping', {})
    mapping_path = body.get('mapping_path', '')
    mode = body.get('mode', 'pseudo')
    fort = body.get('fort', False)
    nlp = body.get('nlp', False)
    tech = body.get('tech', False)
    dry_run = body.get('dry_run', False)
```

**Validation d'entree** :
- Si `dir_path` est vide : erreur 400 "Chemin de dossier requis"
- Si `not os.path.isdir(dir_path)` : erreur 404 "Dossier introuvable : {dir_path}"
- Si aucun fichier supporte dans le dossier : erreur 400 "Aucun fichier traitable dans {dir_path}"

**Mapping unique** : un seul mapping est applique a tous les fichiers du dossier (coherent avec le CLI `--input-dir`). Le mapping est fourni soit en JSON inline (`mapping`), soit par chemin disque (`mapping_path`).

Logique :
1. Lister les fichiers supportes dans le dossier (`.json`, `.csv`, `.xlsx`, etc.), en excluant les fichiers `_PSEUDO`, `_ANON` et les dossiers
2. Traiter chaque fichier sequentiellement avec la meme logique que `_handle_pseudonymise_local()`
3. **Gestion des erreurs par fichier** : si un fichier echoue (JSON invalide, format non supporte, erreur de traitement), le batch continue avec les fichiers suivants. Le fichier en erreur apparait dans le rapport avec `"statut": "erreur"` et le message d'erreur. Le batch ne s'arrete jamais sur une erreur individuelle.
4. **Nommage des CSV** : en batch, les correspondances sont ecrites dans `confidentiel/correspondances_{nom_fichier}.csv` (ex: `correspondances_clients-mars.csv`). Cela corrige un bug existant du CLI ou chaque fichier ecrase `correspondances.csv`.
5. Retourner un rapport **leger** — pas de `data` ni `correspondances` dans la reponse (les correspondances sont ecrites sur disque) :

```json
{
  "fichiers": [
    {"nom": "fichier1.json", "statut": "ok", "total": 500, "remplacements": 1234, "score": 42, "output_path": "...", "csv_path": "..."},
    {"nom": "fichier2.json", "statut": "ok", "total": 200, "remplacements": 456, "score": 28, "output_path": "...", "csv_path": "..."},
    {"nom": "fichier3.json", "statut": "erreur", "erreur": "JSON invalide : Expecting ',' line 42"}
  ],
  "resume": {
    "fichiers_traites": 2,
    "fichiers_en_erreur": 1,
    "total_enregistrements": 700,
    "total_remplacements": 1690
  }
}
```

#### Interface (`app.js` + `index.html`)

Sur la page Import fichier, en mode "Chemin local" :

1. Ajouter une checkbox "Traiter un dossier entier" dans la zone chemin local
2. Quand active, le champ de chemin accepte un chemin de dossier au lieu d'un fichier
3. Le bouton "Lancer le traitement" appelle `/api/pseudonymise-batch` au lieu de `/api/pseudonymise-local`
4. Afficher un message "Traitement en cours..." pendant la requete (pas de progression fichier par fichier — requete unique, resultat a la fin)
5. Afficher un tableau recapitulatif a la fin : nom du fichier, statut (ok/erreur), enregistrements, remplacements, score. Les fichiers en erreur sont affiches en rouge avec le message d'erreur.
6. Le bouton "Previsualiser" en mode batch envoie `dry_run: true` au batch. Le serveur traite le **premier fichier uniquement** (100 premiers enregistrements) pour valider le mapping. L'objectif du dry-run batch est de verifier que le mapping est compatible avec les fichiers du dossier, pas de previsualiser chaque fichier.

#### Comportement attendu — traitement complet

```
Utilisateur saisit "/chemin/vers/donnees/" et active "Traiter un dossier"
  -> Requete POST /api/pseudonymise-batch {path: "/chemin/vers/donnees/", mapping, mode: "pseudo"}
  -> Serveur liste 12 fichiers, traite chacun, continue malgre les erreurs
  -> Interface affiche le tableau recap : 11 ok, 1 erreur
  -> Correspondances ecrites : confidentiel/correspondances_fichier1.csv, ..._fichier2.csv, etc.
```

#### Comportement attendu — previsualisation

```
Utilisateur clique "Previsualiser" en mode dossier
  -> Requete POST /api/pseudonymise-batch {path, mapping, dry_run: true}
  -> Serveur liste les fichiers, traite 100 enregistrements du premier fichier uniquement
  -> Interface affiche : "12 fichiers detectes. Previsualisation sur clients-janvier.json :
     100 enregistrements, 347 remplacements, Score RGPD 42 (Eleve)"
  -> Tableau des 10 premiers remplacements du premier fichier
```

---

## Fichiers impactes

| Fichier | Action |
|---------|--------|
| `serveur.py` | Ajout `dry_run` dans les handlers existants + nouvelle route `/api/pseudonymise-batch` + passage a `ThreadingHTTPServer` |
| `interface/index.html` | Bouton "Previsualiser" + zone resultat dry-run + option "Dossier" + tableau recap batch |
| `interface/app.js` | Logique dry-run + logique batch + progression fichier par fichier |
| `interface/style.css` | Eventuels styles pour la zone de previsualisation et le tableau batch |

---

## Prerequis technique : passage a `ThreadingHTTPServer`

**Probleme** : `HTTPServer` (ligne 728 de `serveur.py`) est mono-thread. Pendant un traitement batch de plusieurs minutes, le serveur ne repond plus a aucune requete (health check, interface, rafraichissement).

**Solution** : remplacer `HTTPServer` par `ThreadingHTTPServer` (stdlib, meme module `http.server`). Changement d'une seule ligne :

```python
# Avant
from http.server import HTTPServer, SimpleHTTPRequestHandler
server = HTTPServer((args.host, args.port), APIHandler)

# Apres
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
server = ThreadingHTTPServer((args.host, args.port), APIHandler)
```

**Thread-safety du moteur** : verifiee. Les globals (`PATRONYMES`, `PRENOMS`, etc.) sont des sets en lecture seule. Les objets d'etat (`TokenTable`, `Stats`, `RiskScorer`) sont crees par requete dans chaque handler (lignes 94-96, 170-172, 254-256). Aucun etat partage mutable entre requetes.

---

## Plan d'execution

1. **ThreadingHTTPServer** : remplacer `HTTPServer` par `ThreadingHTTPServer` (1 ligne)
2. **Dry-run serveur** : modifier `_handle_pseudonymise_local()` et `_handle_pseudonymise()` pour accepter `dry_run`
3. **Dry-run interface** : bouton "Previsualiser", zone de resultat, logique JS
4. **Tester dry-run** : verifier qu'aucun fichier n'est ecrit, que le rapport est correct
5. **Batch serveur** : ajouter `_handle_pseudonymise_batch()` et le routage
6. **Batch interface** : option dossier, appel API, progression, tableau recap
7. **Tester batch** : traiter un dossier avec 3+ fichiers, verifier le rapport
8. **Tests existants** : verifier que `test-options.py` et `test-v3.py` passent toujours (non-regression)

---

## Connus inconnus

| Risque | Severite | Mitigation | Statut |
|--------|----------|------------|--------|
| Progression batch en temps reel | Moyenne | Requete unique, resultat a la fin. `ThreadingHTTPServer` garantit que l'interface reste reactive (health check, navigation). Si le besoin de progression se confirme, evolution vers une requete par fichier cote JS. | Decision prise |
| Timeout sur gros dossiers | Moyenne | Un dossier de 50 fichiers lourds peut prendre plusieurs minutes. Le timeout HTTP par defaut du navigateur est de ~300s. Surveiller et ajouter un timeout configurable si necessaire. | A surveiller |
| Dry-run : comportement different entre upload et local | Moyenne | La route upload (`/api/pseudonymise`) ne produit aucun fichier — le dry-run limite juste `data[:100]`. La route local (`/api/pseudonymise-local`) ecrit fichier + CSV + zip — le dry-run doit tout skipper. Les deux cas retournent le meme format de reponse JSON. Documenter la difference dans le code. | Decision prise |
| Dry-run sur upload : transfert complet avant limitation | Faible | Le fichier est deja transfere en memoire lors de l'upload HTTP. Le dry-run limite le traitement a 100 enregistrements mais le transfert complet a deja eu lieu. Acceptable — le gain est sur le temps de traitement, pas sur le transfert. | Risque accepte |
| Reponse batch legere | Moyenne | Le batch ecrit les correspondances sur disque (CSV par fichier) et ne retourne que le resume. Pas de `data` ni `correspondances` dans la reponse. | Decision prise |
| Nommage CSV en batch | Moyenne | Le CLI ecrit toujours `confidentiel/correspondances.csv` — en `--input-dir`, chaque fichier ecrase le precedent (bug existant). Le batch serveur corrige ce probleme : `confidentiel/correspondances_{nom_fichier}.csv`. | Decision prise |
| Path traversal sur `/api/download` | Hors scope | La route `_handle_download` (ligne 558) accepte n'importe quel chemin sans validation. Risque preexistant aggrave par le batch. A traiter dans un PRD securite dedie. | Hors scope |

---

## Hors perimetre

- `--chunk-size` (streaming) : fonctionnalite avancee pour fichiers > 2 Go, non pertinente en interface web
- Progression en temps reel via WebSocket : complexite disproportionnee pour le gain
- Upload multi-fichiers via drag-and-drop : le mode chemin local couvre le besoin batch
- Securisation de `/api/download` (path traversal) : risque preexistant, a traiter dans un PRD securite dedie

---

## Criteres d'acceptation

### Dry-run

- [ ] Bouton "Previsualiser" visible sur la page Import fichier
- [ ] Clic sur "Previsualiser" en mode local : traite 100 enregistrements max, aucun fichier ecrit sur disque
- [ ] Clic sur "Previsualiser" en mode upload : traite 100 enregistrements max, aucun fichier ecrit
- [ ] Zone de resultat affiche : nombre d'enregistrements, remplacements, score RGPD, 10 premiers remplacements
- [ ] Les boutons "Telecharger" ne sont pas affiches en mode dry-run

### Traitement par lot

- [ ] Option "Traiter un dossier" visible en mode chemin local
- [ ] Validation serveur : erreur claire si le chemin n'est pas un dossier ou si aucun fichier supporte
- [ ] Le serveur liste et traite tous les fichiers supportes du dossier (en excluant `_PSEUDO`/`_ANON`)
- [ ] Les erreurs sur un fichier n'arretent pas le batch — fichier en erreur dans le recap avec message
- [ ] Correspondances nommees par fichier : `confidentiel/correspondances_{nom_fichier}.csv`
- [ ] Tableau recapitulatif en fin de traitement : nom, statut, enregistrements, remplacements, score par fichier
- [ ] Previsualiser en mode dossier : dry-run sur le premier fichier uniquement + listing des fichiers detectes

### Tests automatises a ajouter dans `tests/test-v3.py`

- [ ] `POST /api/pseudonymise-local` avec `dry_run: true` : retourne des resultats, aucun fichier `_PSEUDO` ecrit sur disque
- [ ] `POST /api/pseudonymise` (upload) avec `dry_run: true` : retourne `data` limitee a 100 enregistrements max
- [ ] `POST /api/pseudonymise-batch` avec un dossier contenant 2+ fichiers JSON : retourne un rapport avec un element par fichier
- [ ] `POST /api/pseudonymise-batch` avec `dry_run: true` : traite uniquement le premier fichier, liste tous les fichiers detectes
- [ ] `POST /api/pseudonymise-batch` avec un chemin invalide : retourne erreur 404
- [ ] `POST /api/pseudonymise-batch` avec un dossier vide : retourne erreur 400

### Non-regression

- [ ] `python3 tests/test-options.py` : 49/49
- [ ] `python3 tests/test-v3.py` : tous les tests passent (anciens + nouveaux)
- [ ] `/api/health` repond pendant un traitement batch (ThreadingHTTPServer)
