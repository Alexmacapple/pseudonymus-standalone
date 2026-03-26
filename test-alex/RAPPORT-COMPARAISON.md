# Rapport de comparaison CLI vs interface web

**Date** : 2026-03-26
**Objectif** : Vérifier que le mode CLI et le mode web produisent des résultats identiques.

---

## Méthodologie

Chaque test exécute la même pseudonymisation via deux chemins :
- **CLI** : `python3 pseudonymise.py` avec les options appropriées
- **WEB** : `POST /api/pseudonymise-local` (ou `/api/pseudonymise-texte`) via le serveur sur le port 8090

Les fichiers de sortie sont comparés champ par champ, enregistrement par enregistrement.

---

## Résultats

| Test | Données | Mode | CLI | WEB | Verdict |
|------|---------|------|-----|-----|---------|
| 1 | JSON plat (5 enreg.) | `--pseudo` | 40 remplacements, score 16 | 40 remplacements, score 16 | **Identique** |
| 2 | JSON plat (5 enreg.) | `--anon` | 40 remplacements | 40 remplacements | **Identique** |
| 3 | JSON plat (5 enreg.) | `--fort --pseudo` | 43 remplacements, score 22 | 43 remplacements, score 22 | **Identique** |
| 4 | JSON imbriqué (5 enreg.) | `--pseudo` (unwrap) | 76 remplacements, score 26 | 76 remplacements, score 26 | **Identique** |
| 5 | Texte libre | pseudo-texte | 4 remplacements, score 14 | 4 remplacements, score 14 | **Identique** |

---

## Détail des comparaisons

### Test 1 — JSON plat, mode pseudo

- Fichier source : `donnees-json-plat.json` (5 enregistrements : Marie Dupont, Pierre Martin, Lea Petit, Ali Ben Ahmed, Eva Blanc)
- Mapping : `mapping-json-plat.json` (6 champs sensibles, 1 texte libre)
- Les 5 enregistrements et les 40 remplacements sont strictement identiques entre CLI et WEB
- Correspondances CSV : même contenu

### Test 2 — JSON plat, mode anon

- Mêmes données source et mapping
- Tous les champs anonymisés identiquement (`***`, `anonyme@example.com`, `00000`)
- Le texte libre contient les mêmes `[SUPPRIME]`

### Test 3 — JSON plat, mode fort

- Mode fort active la détection de prénoms isolés, patronymes préfixe et propagation
- 3 remplacements supplémentaires par rapport au mode standard (43 vs 40)
- Score RGPD plus élevé (22 vs 16)
- Résultats strictement identiques entre CLI et WEB

### Test 4 — JSON imbriqué (format SignalConso)

- Structure JSON-in-JSON avec unwrap + notation pointée
- 76 remplacements détectés dans les champs structurés et le texte libre imbriqué
- Le unwrap/re-wrap produit un résultat identique entre CLI et WEB

### Test 5 — Texte libre

- Texte contenant : nom complet, email, téléphone, IBAN
- 4 remplacements : `[PERSONNE_1]`, `[EMAIL_1]`, `[TEL_1]`, `[IBAN_1]`
- Score RGPD 14 (identique)
- Texte pseudonymisé strictement identique caractère par caractère

---

## Conclusion

**Parité CLI/WEB : 100 %.** Les deux modes utilisent le même moteur (`pseudonymise.py`) et produisent des résultats strictement identiques sur les 5 scénarios testés, incluant les modes standard, anonymisation, fort, JSON imbriqué et texte libre.
