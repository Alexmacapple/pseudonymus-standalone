# Agents disponibles

Sous-agents spécialisés pour le projet Pseudonymus standalone.
Voir [CLAUDE.md](CLAUDE.md) pour l'architecture, les conventions et les commandes du projet.

---

## test-runner

**Fichier** : `.claude/agents/test-runner-agent.md`

Exécute les deux suites de tests (49 moteur + 43 API) et vérifie la non-régression. À lancer après toute modification de code.

```
Seuil : 166/166, 0 FAIL, 0 SKIP
```

---

## audit-coherence

**Fichier** : `.claude/agents/audit-coherence-agent.md`

Vérifie la cohérence entre le back (Python), le front (JS/HTML), la doc (MD) et les tests. Détecte les références obsolètes, les routes API manquantes, les chemins cassés.

À lancer après un refactoring ou une réorganisation de fichiers.
