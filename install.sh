#!/bin/bash
# Installation de Pseudonymus standalone
# Usage : bash install.sh
#
# Pre-requis : Python 3.8+
# Installe : venv + toutes les dependances + verification

set -e

echo ""
echo "========================================="
echo "  Installation de Pseudonymus"
echo "========================================="
echo ""

# --- Verifier Python 3.8+ ---
if ! command -v python3 &> /dev/null; then
    echo "Erreur : Python 3 non trouve."
    echo "Installez Python 3.8 ou superieur :"
    echo "  macOS : brew install python3"
    echo "  Linux : sudo apt install python3 python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')")
PYTHON_OK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 8) else 0)")

if [ "$PYTHON_OK" != "1" ]; then
    echo "Erreur : Python $PYTHON_VERSION detecte, version 3.8+ requise."
    exit 1
fi
echo "Python $PYTHON_VERSION detecte"

# --- Verifier que venv est disponible ---
if ! python3 -m venv --help &> /dev/null; then
    echo "Erreur : le module venv n'est pas disponible."
    echo "Installez-le :"
    echo "  Linux : sudo apt install python3-venv"
    exit 1
fi

# --- Creer le venv ---
if [ ! -d ".venv" ]; then
    echo "Creation de l'environnement virtuel..."
    python3 -m venv .venv
    echo "  OK"
else
    echo "Environnement virtuel existant"
fi

echo ""
echo "--- Installation des dependances ---"
echo ""
.venv/bin/pip install --quiet --upgrade pip

# Dependances pour tous les formats bureautiques + streaming
.venv/bin/pip install --quiet openpyxl odfpy python-docx pdfplumber ijson

# Verification
.venv/bin/python3 -c "
deps = [
    ('json',        'JSON',             True),
    ('csv',         'CSV / TSV',        True),
    ('openpyxl',    'XLSX / XLS',       False),
    ('odf',         'ODS / ODT',        False),
    ('docx',        'DOCX',             False),
    ('pdfplumber',  'PDF',              False),
    ('ijson',       'Streaming > 2 Go', False),
]
for mod, fmt, builtin in deps:
    try:
        __import__(mod)
        tag = 'natif' if builtin else 'installe'
        print(f'  OK  {fmt} ({tag})')
    except ImportError:
        print(f'  !!  {fmt} (echec installation)')
"

# --- SpaCy (optionnel) ---
echo ""
read -p "Installer spaCy pour la detection NLP avancee ? (~150 Mo) (o/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Oo]$ ]]; then
    echo "Installation de spaCy + modele francais..."
    .venv/bin/pip install --quiet spacy
    .venv/bin/python3 -m spacy download fr_core_news_sm --quiet
    echo "  OK  NLP (spaCy + fr_core_news_sm)"
else
    echo "  --  NLP non installe (optionnel)"
fi

# --- Creer le dossier confidentiel ---
mkdir -p confidentiel
chmod 700 confidentiel

# --- Lancer les tests ---
echo ""
echo "--- Verification ---"
echo ""

FAIL=0

echo "Tests moteur :"
RESULT=$(.venv/bin/python3 tests/test-options.py 2>&1 | tail -1)
echo "  $RESULT"
echo "$RESULT" | grep -q "0 FAIL" || FAIL=1

echo "Tests formats + API :"
echo "  (necessitent le serveur sur le port 8090)"

# Demarrer le serveur temporairement pour les tests
.venv/bin/python3 serveur.py --port 8090 &
SERVER_PID=$!
sleep 3

if curl -s http://127.0.0.1:8090/api/health | grep -q '"ok"'; then
    RESULT=$(.venv/bin/python3 tests/test-v3.py 2>&1 | tail -1)
    echo "  $RESULT"
    echo "$RESULT" | grep -q "0 FAIL" || FAIL=1
else
    echo "  !! Serveur non accessible, tests API ignores"
    FAIL=1
fi

# Arreter le serveur de test
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null

echo ""
echo "========================================="
if [ "$FAIL" = "0" ]; then
    echo "  Installation reussie"
else
    echo "  Installation terminee avec des avertissements"
fi
echo "========================================="
echo ""
echo "Lancer le serveur :"
echo "  .venv/bin/python3 serveur.py"
echo ""
echo "Ouvrir dans le navigateur :"
echo "  http://127.0.0.1:8090"
echo ""
echo "CLI :"
echo "  .venv/bin/python3 pseudonymise.py fichier.json --mapping mapping.json --pseudo"
echo ""
