---
name: audit-coherence
description: Vérifie la cohérence entre le back (Python), le front (JS/HTML), la doc (MD) et les tests.
---

# Agent audit-coherence

Audite la cohérence globale du projet pseudonymus-standalone.

## Instructions

1. **Références croisées** : chercher dans tous les fichiers actifs (hors `prd/done/`) des références à :
   - `generique/` (ancien nom)
   - Chemins absolus `/Users/`
   - `docs/` (ancien répertoire)
   - `exemples/confidentiel` (ancien emplacement)

2. **Parité front/back** : comparer les routes API appelées dans `interface/app.js` avec celles définies dans `serveur.py`. Signaler tout écart.

3. **Documentation** : vérifier que README.md et CLAUDE.md sont cohérents entre eux et avec l'arborescence réelle.

4. **Tests** : vérifier que les chemins dans `tests/test-options.py` et `tests/test-v3.py` pointent vers les bons fichiers.

## Format de sortie

Tableau avec : fichier, ligne, incohérence, sévérité (critique/mineure/info).
