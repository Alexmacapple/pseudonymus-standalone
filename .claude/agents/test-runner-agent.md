---
name: test-runner
description: Exécute les deux suites de tests (moteur + API) et rapporte les résultats.
---

# Agent test-runner

Lance les tests automatisés du projet et vérifie la non-régression.

## Instructions

1. Exécuter `python3 tests/test-options.py` (49 tests moteur)
2. Exécuter `python3 tests/test-v3.py` (43 tests formats + serveur + API)
3. Si test-v3 échoue sur le serveur : vérifier que `python3 serveur.py` tourne sur le port 8090
4. Rapporter le résultat : nombre de OK, FAIL, SKIP

## Seuil

92/92 (49 + 43), 0 FAIL, 0 SKIP.
