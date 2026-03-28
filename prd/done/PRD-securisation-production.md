# PRD : Securisation pour la production

**Date** : 2026-03-28
**Statut** : Livre (2026-03-28)
**Auteur** : Alex
**Priorite** : Critique -- bloqueur mise en production
**Contexte** : Audit SWOT du depot, 5 failles identifiees
**Estimation** : ~2h (1h code, 1h tests)

---

## Probleme

Le serveur est expose via Tailscale (`https://mac-studio-alex.tail0fc408.ts.net:10443/`) mais le code serveur n'a aucune protection contre :
- la lecture arbitraire de fichiers (`/api/download` sans validation)
- les attaques cross-origin (CORS ouvert a `*`)
- les uploads geants (pas de limite Content-Length)
- les fichiers temporaires predictibles (`tempfile.mktemp()`)
- la fuite d'information via les messages d'erreur Python

Le dossier `confidentiel/` contient les correspondances de pseudonymisation (cle de reidentification). Un acces a ce dossier via `/api/download` constitue une violation RGPD.

---

## Corrections

### 1. Securiser `/api/download` (CRITIQUE) ~30 min

**Fichier** : `serveur.py`, methode `_handle_download`

**Avant** : accepte tout chemin absolu sans validation.

**Apres** : restreindre aux fichiers generes par le serveur. Maintenir une liste blanche de chemins autorises (les `output_path` et `zip_path` retournes par les endpoints de traitement).

```python
# Attribut sur le serveur (pas sur le handler)
# Dans le bloc de demarrage du serveur :
server._download_whitelist = set()

def _handle_download(self, parsed):
    qs = parse_qs(parsed.query)
    file_path = qs.get('path', [''])[0]

    if not file_path:
        self._json_error(400, 'Chemin requis')
        return

    # Resoudre le chemin reel (elimine ../ et symlinks)
    real_path = os.path.realpath(file_path)

    # Verifier que le fichier est dans la whitelist
    if real_path not in self.server._download_whitelist:
        self._json_error(403, 'Acces refuse')
        return

    if not os.path.isfile(real_path):
        self._json_error(404, 'Fichier introuvable')
        return

    # ... reste du code (lecture + envoi)
```

**Endpoints a modifier** (ajout a la whitelist apres generation) :

| Endpoint | Chemins a whitelister |
|----------|----------------------|
| `_handle_pseudonymise_local` | `output_path`, `csv_path`, `zip_path` |
| `_handle_pseudonymise_batch` | `output_path` et `csv_path` de chaque fichier |

```python
# Exemple dans _handle_pseudonymise_local, apres creation du zip :
if output_path:
    self.server._download_whitelist.add(os.path.realpath(output_path))
if zip_path:
    self.server._download_whitelist.add(os.path.realpath(zip_path))
if csv_path and os.path.exists(csv_path):
    self.server._download_whitelist.add(os.path.realpath(csv_path))
```

**Tests** (4 tests) :
```python
# 1. Path traversal bloque
r = api_get('/api/download?path=/etc/passwd')
test('Download /etc/passwd bloque', r.get('erreur') and '403' in str(r) or 'refuse' in r.get('erreur', '').lower())

# 2. Acces confidentiel bloque
r = api_get('/api/download?path=' + os.path.join(PROJECT_DIR, 'confidentiel/correspondances.csv'))
test('Download confidentiel bloque', 'refuse' in r.get('erreur', '').lower())

# 3. Path traversal relatif bloque
r = api_get('/api/download?path=../../etc/passwd')
test('Download traversal relatif bloque', 'refuse' in r.get('erreur', '').lower())

# 4. Test d'integration : traitement local puis download du zip
#    (enchaine pseudonymise-local + download dans le meme test)
r_local = api_post('/api/pseudonymise-local', {
    'path': test_file_path, 'mapping': mapping, 'mode': 'pseudo',
    'fort': False, 'nlp': False, 'tech': False
})
zip_path = r_local.get('zip_path', '')
if zip_path:
    r_dl = api_get('/api/download?path=' + zip_path)
    test('Download zip apres traitement', 'erreur' not in r_dl or r_dl.get('erreur') is None)
```

---

### 2. Restreindre CORS (CRITIQUE) ~15 min

**Fichier** : `serveur.py`, partout ou `Access-Control-Allow-Origin` est envoye

**Avant** : `Access-Control-Allow-Origin: *` envoye systematiquement.

**Apres** : uniquement si l'Origin est autorisee.

```python
def _send_cors_headers(self):
    origin = self.headers.get('Origin', '')
    if not origin:
        return  # Pas d'Origin = pas de CORS

    allowed = [
        f'http://127.0.0.1:{self.server.server_port}',
        f'http://localhost:{self.server.server_port}',
    ]
    # Ajouter l'origine Tailscale si configuree
    tailscale_origin = os.environ.get('PSEUDONYMUS_ALLOWED_ORIGIN', '')
    if tailscale_origin:
        allowed.append(tailscale_origin)

    if origin in allowed:
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
```

Remplacer tous les appels directs `self.send_header('Access-Control-Allow-Origin', '*')` par `self._send_cors_headers()`.

**Variable d'environnement** : `PSEUDONYMUS_ALLOWED_ORIGIN` pour les deployements non-localhost. A documenter dans CLAUDE.md et README.md apres implementation.

**Tests** (3 tests) :
```python
# Les tests CORS necessitent d'envoyer un header Origin manuellement
import http.client

def api_get_with_origin(path, origin):
    conn = http.client.HTTPConnection('127.0.0.1', 8090, timeout=5)
    headers = {'Origin': origin} if origin else {}
    conn.request('GET', path, headers=headers)
    resp = conn.getresponse()
    cors = resp.getheader('Access-Control-Allow-Origin')
    resp.read()
    return cors

# 1. Origin localhost autorisee
cors = api_get_with_origin('/api/health', 'http://127.0.0.1:8090')
test('CORS localhost autorise', cors == 'http://127.0.0.1:8090')

# 2. Origin malveillante bloquee
cors = api_get_with_origin('/api/health', 'https://evil.com')
test('CORS evil.com bloque', cors is None)

# 3. Pas d'Origin = pas de header CORS
cors = api_get_with_origin('/api/health', None)
test('CORS sans origin', cors is None)
```

---

### 3. Limiter Content-Length (HAUTE) ~10 min

**Fichier** : `serveur.py`, methodes `_read_json_body` et `_read_multipart`

**Avant** : lit tout le body sans limite.

**Apres** : factoriser dans une methode `_read_body()` avec limite.

```python
MAX_BODY_SIZE = 400 * 1024 * 1024  # 400 Mo

def _read_body(self):
    """Lit le body HTTP avec limite de taille."""
    length = int(self.headers.get('Content-Length', 0))
    if length > MAX_BODY_SIZE:
        return None  # L'appelant doit gerer le cas None
    if length == 0:
        return b''
    return self.rfile.read(length)

def _read_json_body(self):
    raw = self._read_body()
    if raw is None:
        self._json_error(413, 'Contenu trop volumineux (limite : 400 Mo)')
        return None
    return json.loads(raw.decode('utf-8'))

def _read_multipart(self):
    raw = self._read_body()
    if raw is None:
        return None, {'_error': '413'}
    # ... reste du parsing multipart avec raw
```

**Tous les appelants** de `_read_json_body()` et `_read_multipart()` doivent gerer le cas `None` (retour anticipé avec 413).

**Tests** (2 tests) :
```python
# 1. Content-Length excessif rejete (sans envoyer les donnees)
conn = http.client.HTTPConnection('127.0.0.1', 8090, timeout=5)
conn.request('POST', '/api/pseudonymise-texte', b'{}',
    {'Content-Type': 'application/json', 'Content-Length': '500000000'})
resp = conn.getresponse()
test('Content-Length excessif 413', resp.status == 413 or resp.status == 500)
resp.read()

# 2. Upload normal passe
r = api_post('/api/pseudonymise-texte', {'texte': 'Bonjour Marie'})
test('Upload normal OK', 'erreur' not in r or r.get('texte_pseudonymise'))
```

---

### 4. Remplacer `tempfile.mktemp()` (HAUTE) ~5 min

**Fichier** : `serveur.py`, methode `_handle_mapping_generate_post`

**Avant** :
```python
tmp_path = tempfile.mktemp(suffix=ext)
with open(tmp_path, 'wb') as tmp:
    tmp.write(file_data)
```

**Apres** :
```python
tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
tmp.write(file_data)
tmp.close()
tmp_path = tmp.name
```

Meme pattern que `_handle_pseudonymise` (ligne 155) qui utilise deja `NamedTemporaryFile` correctement.

**Pas de test specifique** : correction mecanique, le comportement fonctionnel ne change pas. Les tests existants de mapping/generate couvrent deja le flux.

---

### 5. Masquer les erreurs Python (MOYENNE) ~15 min

**Fichier** : `serveur.py`, tous les blocs `except Exception as e`

**Avant** :
```python
except Exception as e:
    traceback.print_exc()
    self._json_error(500, str(e))
```

**Apres** :
```python
except Exception as e:
    traceback.print_exc()  # log interne (stderr)
    self._json_error(500, 'Erreur interne du serveur')
```

**Regles** :
- Erreurs **500** (exceptions non prevues) : message generique `'Erreur interne du serveur'`
- Erreurs **400** (validation) : message clair sans chemin systeme → conservees telles quelles
- Erreurs **404** : ne pas inclure le chemin absolu

Remplacer dans les messages 404 :
```python
# Avant
self._json_error(404, f'Fichier introuvable : {file_path}')

# Apres
self._json_error(404, f'Fichier introuvable : {os.path.basename(file_path)}')
```

**Audit des messages 400 existants** (tous OK, pas de fuite) :
- `'Chemin de fichier requis'` → OK
- `'Le fichier doit contenir un array JSON non vide'` → OK
- `'Veuillez fournir un texte'` → OK
- `'Chemin requis'` → OK

**Tests** (3 tests) :
```python
# 1. Erreur 500 ne contient pas de chemin systeme
r = api_post('/api/pseudonymise-local', {
    'path': '/tmp/fichier-inexistant-xyz.json',
    'mapping': {}, 'mode': 'pseudo'
})
err_msg = r.get('erreur', '')
test('Erreur 500 generique', '/tmp/' not in err_msg and '/Users/' not in err_msg)

# 2. Erreur 404 sans chemin absolu
r = api_post('/api/pseudonymise-local', {
    'path': '/chemin/tres/long/vers/fichier.json',
    'mapping': {}, 'mode': 'pseudo'
})
test('Erreur 404 sans chemin absolu', '/chemin/tres' not in r.get('erreur', ''))

# 3. Erreur 400 toujours claire
r = api_post('/api/pseudonymise-local', {'path': '', 'mapping': {}})
test('Erreur 400 message clair', 'requis' in r.get('erreur', '').lower())
```

---

## Points d'attention

- **Whitelist en memoire** : la liste des fichiers telechargeables est reinitialise au redemarrage du serveur. Les fichiers generes avant le redemarrage ne sont plus telechargeables (il faut relancer le traitement). Comportement acceptable et documente.
- **Fichiers statiques** : `SimpleHTTPRequestHandler.translate_path()` sanitize deja les chemins (`GET /../../etc/passwd` est bloque nativement). Pas de correction necessaire.
- **CORS sans Origin** : si la requete n'a pas de header `Origin`, ne pas envoyer `Access-Control-Allow-Origin` du tout.
- **Variable d'environnement CORS** : `PSEUDONYMUS_ALLOWED_ORIGIN` a documenter dans CLAUDE.md et README.md apres implementation.
- **Appelants de `_read_body()`** : tous les endpoints POST doivent gerer le cas `None` (retour 413). A verifier sur chaque endpoint lors de l'implementation.

---

## Fichiers modifies

| Fichier | Modification | Complexite |
|---------|-------------|------------|
| `serveur.py` | 5 corrections (download, CORS, content-length, mktemp, erreurs) | Moyenne |
| `tests/test-v3.py` | 12 tests de securite | Faible |
| `CLAUDE.md` | Documenter `PSEUDONYMUS_ALLOWED_ORIGIN` | Faible |
| `README.md` | Documenter `PSEUDONYMUS_ALLOWED_ORIGIN` | Faible |

---

## Verification

### Tests automatises (12 tests)

| # | Test | Resultat attendu |
|---|------|-----------------|
| 1 | `GET /api/download?path=/etc/passwd` | 403 Acces refuse |
| 2 | `GET /api/download?path=confidentiel/correspondances.csv` | 403 Acces refuse |
| 3 | `GET /api/download?path=../../serveur.py` | 403 Acces refuse |
| 4 | Traitement local puis download du zip | 200 OK |
| 5 | CORS avec Origin `http://127.0.0.1:8090` | Header CORS present |
| 6 | CORS avec Origin `https://evil.com` | Pas de header CORS |
| 7 | CORS sans Origin | Pas de header CORS |
| 8 | Content-Length 500 Mo | 413 |
| 9 | Upload normal 1 Mo | 200 |
| 10 | Erreur 500 sans chemin systeme | Message generique |
| 11 | Erreur 404 sans chemin absolu | Basename uniquement |
| 12 | Erreur 400 message clair | Texte utilisateur |

### Verification manuelle

```bash
# Path traversal
curl -s "http://127.0.0.1:8090/api/download?path=/etc/passwd" | jq .erreur
# Attendu : "Acces refuse"

# CORS
curl -s -H "Origin: https://evil.com" -I http://127.0.0.1:8090/api/health | grep -i access-control
# Attendu : rien

# Content-Length excessif
curl -s -H "Content-Length: 500000000" -X POST http://127.0.0.1:8090/api/pseudonymise-texte | jq .erreur
# Attendu : "Contenu trop volumineux"
```

### Non-regression

- Tests existants : 166/166 toujours OK
- Total apres implementation : ~178 tests
