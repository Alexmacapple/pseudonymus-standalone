#!/bin/bash
# Installation de Pseudonymus standalone
# Usage : bash install.sh

set -e

echo "=== Installation de Pseudonymus ==="
echo ""

# Vérifier Python 3.8+
if ! command -v python3 &> /dev/null; then
    echo "Erreur : Python 3 non trouvé. Installez Python 3.8 ou supérieur."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYTHON_VERSION détecté"

# Créer le venv s'il n'existe pas
if [ ! -d ".venv" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv .venv
fi

echo "Installation des dépendances..."
.venv/bin/pip install --quiet --upgrade pip

# Dépendances optionnelles (formats bureautiques + NLP + streaming)
.venv/bin/pip install --quiet openpyxl odfpy python-docx pdfplumber ijson

echo ""
echo "=== Dépendances installées ==="
.venv/bin/python3 -c "
deps = [
    ('openpyxl', 'XLSX/XLS'),
    ('odf', 'ODS/ODT'),
    ('docx', 'DOCX'),
    ('pdfplumber', 'PDF'),
    ('ijson', 'Streaming (> 2 Go)'),
]
for mod, fmt in deps:
    try:
        __import__(mod)
        print(f'  OK  {fmt}')
    except ImportError:
        print(f'  --  {fmt} (non installé)')
"

# SpaCy (optionnel, plus lourd)
echo ""
read -p "Installer spaCy pour la détection NLP ? (o/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Oo]$ ]]; then
    echo "Installation de spaCy + modèle français..."
    .venv/bin/pip install --quiet spacy
    .venv/bin/python3 -m spacy download fr_core_news_sm
    echo "  OK  NLP (spaCy)"
fi

# Créer le dossier confidentiel
mkdir -p confidentiel
echo ""

# Vérifier les tests
echo "=== Vérification ==="
.venv/bin/python3 tests/test-options.py 2>&1 | tail -1
.venv/bin/python3 tests/test-v3.py 2>&1 | tail -1

echo ""
echo "=== Installation terminée ==="
echo ""
echo "Lancer le serveur :"
echo "  .venv/bin/python3 serveur.py --port 8090"
echo ""
echo "Ouvrir dans le navigateur :"
echo "  http://127.0.0.1:8090"
echo ""
echo "CLI :"
echo "  .venv/bin/python3 pseudonymise.py fichier.json --mapping mapping.json --pseudo"
