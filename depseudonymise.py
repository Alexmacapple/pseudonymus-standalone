#!/usr/bin/env python3
"""
Dépseudonymise un JSON en remplaçant les jetons par les valeurs originales.

Usage :
    python3 depseudonymise.py data/fichier_PSEUDO.json --correspondances confidentiel/correspondances.csv
"""

import argparse
import csv
import json
import os
import re
import sys


def main():
    parser = argparse.ArgumentParser(description='Depseudonymise un JSON.')
    parser.add_argument('input', help='Fichier JSON pseudonymise')
    parser.add_argument('--correspondances', required=True, help='Fichier CSV de correspondances')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f'Erreur : fichier introuvable : {args.input}', file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.correspondances):
        print(f'Erreur : correspondances introuvables : {args.correspondances}', file=sys.stderr)
        sys.exit(1)

    # Charger la table de correspondances
    table = {}
    with open(args.correspondances, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)  # Skip header
        for row in reader:
            if len(row) >= 3:
                jeton = row[1]
                original = row[2]
                table[jeton] = original

    print(f'{len(table)} correspondances chargees.', file=sys.stderr)

    # Charger le JSON
    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remplacer tous les jetons (du plus long au plus court pour éviter les collisions)
    for jeton in sorted(table.keys(), key=len, reverse=True):
        content = content.replace(jeton, table[jeton])

    # Parser et réécrire
    data = json.loads(content)

    base_name = os.path.splitext(args.input)[0]
    # Retirer le suffixe _PSEUDO si présent
    base_name = re.sub(r'_PSEUDO$', '', base_name)
    output_path = f'{base_name}_RESTAURE.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=None)

    print(f'Fichier restaure : {output_path} ({len(data)} enregistrements)', file=sys.stderr)


if __name__ == '__main__':
    main()
