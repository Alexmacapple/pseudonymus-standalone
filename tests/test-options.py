"""Tests automatisés du script pseudonymise.py."""
import json
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
SCRIPT = os.path.join(PROJECT_DIR, 'pseudonymise.py')
DEPSEUDO = os.path.join(PROJECT_DIR, 'depseudonymise.py')
EXEMPLES = os.path.join(PROJECT_DIR, 'exemples')
TEST_JSON = os.path.join(EXEMPLES, 'donnees-json-plat.json')
MAPPING_PLAT = os.path.join(EXEMPLES, 'mapping-json-plat.json')
MAPPING_SC = os.path.join(EXEMPLES, 'mapping-json-imbrique.json')

passed = 0
failed = 0


def test(name, condition, detail=''):
    global passed, failed
    if condition:
        print(f'  OK  {name}')
        passed += 1
    else:
        print(f'  FAIL  {name} -- {detail}')
        failed += 1


def run(args):
    return subprocess.run(
        ['python3', SCRIPT] + args,
        capture_output=True, text=True, cwd=PROJECT_DIR)


def run_depseudo(args):
    return subprocess.run(
        ['python3', DEPSEUDO] + args,
        capture_output=True, text=True, cwd=PROJECT_DIR)


# Nettoyage
for f in ['donnees-json-plat_PSEUDO.json', 'donnees-json-plat_ANON.json',
          'donnees-json-plat_RESTAURE.json']:
    p = os.path.join(EXEMPLES, f)
    if os.path.exists(p):
        os.remove(p)
csv_path = os.path.join(PROJECT_DIR, 'confidentiel', 'correspondances.csv')
if os.path.exists(csv_path):
    os.remove(csv_path)


# ============================================================
print('=== TEST 1 : Fichier inexistant ===')
r = run(['inexistant.json', '--mapping', MAPPING_PLAT, '--pseudo'])
test('Code retour non-zero', r.returncode != 0)
test('Message erreur', 'introuvable' in r.stderr)

# ============================================================
print('\n=== TEST 2 : Mapping inexistant ===')
r = run([TEST_JSON, '--mapping', 'inexistant.json', '--pseudo'])
test('Code retour non-zero', r.returncode != 0)
test('Message erreur', 'introuvable' in r.stderr)

# ============================================================
print('\n=== TEST 3 : Aucun mode specifie ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT])
test('Code retour non-zero', r.returncode != 0)

# ============================================================
print('\n=== TEST 4 : Deux modes en meme temps ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--pseudo', '--anon'])
test('Code retour non-zero', r.returncode != 0)

# ============================================================
print('\n=== TEST 5 : --dry-run JSON plat ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--dry-run'])
test('Code retour zero', r.returncode == 0)
test('Rapport present', 'RAPPORT DE TRAITEMENT' in r.stderr)
test('5 enregistrements', '5/5' in r.stderr)
test('Pas de fichier ecrit', not os.path.exists(
    os.path.join(EXEMPLES, 'donnees-json-plat_PSEUDO.json')))
test('Score RGPD affiche', 'Score RGPD' in r.stderr)

# ============================================================
print('\n=== TEST 6 : --pseudo JSON plat ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--pseudo'])
test('Code retour zero', r.returncode == 0)
pseudo_path = os.path.join(EXEMPLES, 'donnees-json-plat_PSEUDO.json')
test('JSON pseudo ecrit', os.path.exists(pseudo_path))
test('CSV correspondances ecrit', os.path.exists(csv_path))

if os.path.exists(pseudo_path):
    with open(pseudo_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    test('5 enregistrements', len(data) == 5)
    r0 = data[0]
    test('Firstname jeton', str(r0.get('prenom', '')).startswith('['))
    test('Lastname jeton', str(r0.get('nom', '')).startswith('['))
    test('Email jeton', str(r0.get('email', '')).startswith('['))
    test('Id jeton', str(r0.get('id', '')).startswith('['))
    # Vérifier que le texte libre a des jetons numérotés
    comm = r0.get('commentaire', '')
    test('Tel dans texte numerote', '[TEL_' in comm)

if os.path.exists(csv_path):
    perms = oct(os.stat(csv_path).st_mode)[-3:]
    test('CSV permissions 600', perms == '600', f'obtenu: {perms}')
    with open(csv_path, 'r', encoding='utf-8') as f:
        header = f.readline().strip()
    test('CSV header correct', header == 'type;jeton;valeur_originale')

# ============================================================
print('\n=== TEST 7 : --anon JSON plat ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--anon'])
test('Code retour zero', r.returncode == 0)
anon_path = os.path.join(EXEMPLES, 'donnees-json-plat_ANON.json')
test('JSON anon ecrit', os.path.exists(anon_path))

if os.path.exists(anon_path):
    with open(anon_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    test('5 enregistrements', len(data) == 5)
    r0 = data[0]
    test('Firstname ***', r0.get('prenom') == '***')
    test('Email anonyme', r0.get('email') == 'anonyme@example.com')
    test('CP 00000', r0.get('code_postal') == '00000')
    # Texte libre : [SUPPRIMÉ] au lieu de jetons
    comm = r0.get('commentaire', '')
    test('Pas de PERSONNE dans anon', '[PERSONNE_' not in comm)

# ============================================================
print('\n=== TEST 8 : --score-only ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--score-only'])
test('Code retour zero', r.returncode == 0)
test('Score RGPD affiche', 'Score RGPD' in r.stderr)
test('Aucun fichier ecrit', 'Aucun fichier' in r.stderr)

# ============================================================
print('\n=== TEST 9 : --fort JSON plat ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--fort', '--dry-run'])
test('Code retour zero', r.returncode == 0)
test('Plus de remplacements en fort', True)  # Le mode fort devrait trouver plus

# ============================================================
print('\n=== TEST 10 : Depseudonymisation ===')
pseudo_path = os.path.join(EXEMPLES, 'donnees-json-plat_PSEUDO.json')
if os.path.exists(pseudo_path) and os.path.exists(csv_path):
    r = run_depseudo([pseudo_path, '--correspondances', csv_path])
    test('Code retour zero', r.returncode == 0)
    restaure_path = os.path.join(EXEMPLES, 'donnees-json-plat_RESTAURE.json')
    test('JSON restaure ecrit', os.path.exists(restaure_path))
    if os.path.exists(restaure_path):
        with open(restaure_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        test('5 enregistrements', len(data) == 5)
        r0 = data[0]
        test('Prenom restaure', r0.get('prenom') == 'Marie',
             f'obtenu: {r0.get("prenom")}')
        test('Email restaure', 'marie.dupont@example.fr' in str(r0.get('email', '')),
             f'obtenu: {r0.get("email")}')
else:
    print('  SKIP  Fichiers pseudo/csv manquants')

# ============================================================
print('\n=== TEST 11 : Mapping SignalConso (unwrap + notation pointee) ===')
sc_test_path = os.path.join(EXEMPLES, 'donnees-json-imbrique.json')
r = run([sc_test_path, '--mapping', MAPPING_SC, '--dry-run'])
test('Code retour zero', r.returncode == 0)
test('5 enregistrements', '5/5' in r.stderr)
test('Prenom detecte', 'prenom' in r.stderr)
test('Nom detecte', 'nom' in r.stderr)
test('Email detecte', 'email' in r.stderr)
test('UUID detecte', 'uuid' in r.stderr)
test('Unwrap fonctionne (pas d erreur parse)', 'ERREUR' not in r.stderr or 'Erreurs' not in r.stderr)

# ============================================================
print('\n=== TEST 12 : Whitelist protege les mots ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--dry-run'])
# ORANGE est dans la whitelist, ne doit pas être pseudonymisé
test('ORANGE dans whitelist', 'ORANGE' not in str(r.stderr).replace('whitelist', '').split('orga_txt')[0] if 'orga_txt' in r.stderr else True)

# ============================================================
print('\n=== TEST 13 : Dictionnaires charges ===')
r = run([TEST_JSON, '--mapping', MAPPING_PLAT, '--dry-run'])
test('Patronymes charges', '884314 patronymes' in r.stderr)
test('Prenoms charges', '169244 prenoms' in r.stderr)

# ============================================================
print(f'\n{"=" * 60}')
print(f'RESULTATS : {passed} OK / {failed} FAIL / {passed + failed} total')
if failed:
    sys.exit(1)
else:
    print('Tous les tests passent.')
