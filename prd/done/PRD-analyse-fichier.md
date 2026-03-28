# PRD : Analyse de fichier avant traitement

**Date** : 2026-03-27
**Statut** : Livre (2026-03-28)
**Auteur** : Alex
**Contexte** : Interface web de pseudonymisation (`interface/`)

---

## Probleme

Aujourd'hui, un utilisateur qui reçoit un fichier ne peut pas l'explorer avant de le pseudonymiser. Il doit :

1. Fournir un mapping (ou en générer un automatiquement)
2. Lancer une prévisualisation (dry-run)
3. Alors seulement il voit le contenu et le risque RGPD

Un DPO ou un agent public a besoin de **comprendre ce que contient un fichier** et **évaluer son niveau de risque** avant de décider quoi en faire. Aujourd'hui, le scoring RGPD ne fonctionne que sur du texte collé, pas sur un fichier structuré.

---

## Utilisateurs cibles

- DPO qui reçoivent des fichiers et doivent évaluer le risque RGPD
- Agents publics qui manipulent des données personnelles sans connaître la structure du fichier
- Equipes data qui veulent inspecter un export avant traitement

---

## Solution

### Nouvel onglet "Analyse"

Position dans le menu : entre "Import fichier" et "Scoring RGPD".
Ancre : `#analyse`

### Workflow utilisateur

1. L'utilisateur charge un fichier (upload ou chemin local, tous formats supportés)
2. Le moteur charge les 20 premiers enregistrements
3. Chaque enregistrement est affiché dans une **card DSFR**
4. Chaque card affiche :
   - Numéro de fiche (Fiche 1, Fiche 2...)
   - Tous les champs avec leurs valeurs (tronquées à 200 caractères pour le texte long)
   - Un **badge RGPD** avec le score et le niveau de risque (NUL, FAIBLE, MODERE, ELEVE, CRITIQUE)
   - Un **bouton Copier** pour copier le contenu de la card dans le presse-papier
5. Un résumé global en haut : nombre d'enregistrements, score moyen, champs détectés

### Scoring sans mapping

Le scoring se fait **sans mapping** : pour chaque enregistrement, toutes les valeurs texte sont concaténées et passées au moteur de scoring en mode standard. Le moteur détecte automatiquement les emails, téléphones, IBAN, noms avec contexte, etc.

Option : l'utilisateur peut activer le mode "Fort" pour une détection plus agressive.

### Format de copie

Le bouton "Copier" copie le contenu de la card en **texte brut lisible** :

```
--- Fiche 3 --- Score RGPD : 42 (MODERE)
nom : Dupont
prenom : Marie
email : marie.dupont@example.fr
telephone : 06 12 34 56 78
commentaire : Contacter Marie Dupont pour le dossier 2024-1234.
```

Ce format est collable dans un email, un rapport ou un document.

---

## Spécifications techniques

### API

**Nouvel endpoint** : `POST /api/analyze`

Entrée (JSON) :
```json
{"path": "/chemin/vers/fichier.json", "fort": false, "limit": 20}
```

Entrée (multipart) : fichier uploadé + paramètres `fort`, `limit`

Sortie :
```json
{
  "fiches": [
    {
      "index": 1,
      "champs": [
        {"cle": "nom", "valeur": "Dupont"},
        {"cle": "email", "valeur": "marie@test.com"},
        {"cle": "commentaire", "valeur": "Texte long tronqué..."}
      ],
      "score": {
        "total": 42,
        "niveau": "MODERE",
        "details": {"direct": 3, "finance": 0, "tech": 0, "indirect": 1}
      }
    }
  ],
  "resume": {
    "total_enregistrements": 31891,
    "echantillon": 20,
    "score_moyen": 38,
    "score_max": 85,
    "niveau_max": "ELEVE"
  }
}
```

### Methode de scoring par enregistrement

Pour chaque enregistrement (dict) :
1. Concaténer toutes les valeurs qui sont des chaînes de caractères (séparées par `\n`)
2. Passer le texte concaténé à `engine.pseudonymise_texte()` avec un `RiskScorer` dédié
3. Récupérer le score et le niveau

Pour les formats documents (DOCX, PDF, TXT, MD) qui produisent un seul enregistrement avec un champ `texte` long : tronquer l'affichage à 500 caractères dans la card mais scorer le texte complet.

### Interface (HTML)

```
#analyse
├── h1 "Analyse de fichier"
├── p "Explorez le contenu d'un fichier et évaluez son niveau de risque RGPD."
├── h2 "Fichier à analyser"
│   ├── fieldset (upload / chemin local) — réutiliser le même pattern que Import
│   ├── checkbox "Mode fort"
│   └── bouton "Analyser"
├── div#analyse-resume (masqué par défaut)
│   ├── h2 "Résumé"
│   └── tiles DSFR (enregistrements, score moyen, score max)
└── div#analyse-fiches (masqué par défaut)
    ├── h2 "Détail des enregistrements"
    └── grille de cards DSFR (fr-col-12 fr-col-md-6)
```

### Card DSFR par fiche

```html
<div class="fr-card fr-card--no-arrow">
    <div class="fr-card__body">
        <div class="fr-card__content">
            <h3 class="fr-card__title">
                Fiche 1
                <span class="fr-badge fr-badge--warning">MODERE (42)</span>
            </h3>
            <div class="fr-card__desc">
                <p><strong>nom</strong> : Dupont</p>
                <p><strong>email</strong> : marie@test.com</p>
                <p><strong>commentaire</strong> : Texte long tronqué...</p>
            </div>
            <div class="fr-card__end">
                <button class="fr-btn fr-btn--sm fr-btn--tertiary">Copier</button>
            </div>
        </div>
    </div>
</div>
```

Badge RGPD selon le niveau :
- NUL (0) : `fr-badge--success`
- FAIBLE (<10) : `fr-badge--info`
- MODERE (<50) : `fr-badge--warning`
- ELEVE (<100) : `fr-badge--error`
- CRITIQUE (100+) : `fr-badge--error` + texte "CRITIQUE"

---

## Fichiers à modifier

| Fichier | Modification |
|---------|-------------|
| `interface/index.html` | Nouvelle section `#page-analyse`, entrée nav |
| `interface/app.js` | Entrée `PAGE_TITLES`, handler du bouton Analyser, rendu cards, bouton copier |
| `serveur.py` | Nouvel endpoint `POST /api/analyze`, route dans `do_POST` |
| `formats.py` | Aucune modification (réutilisation de `load_file`) |

---

## Risques et points d'attention

### Chevauchement avec les pages existantes

Trois endroits scorent du contenu : Scoring RGPD (texte collé), Analyse (fichier brut), Preview dans Import (fichier + mapping). Pour éviter la confusion :
- **Fusionner Scoring RGPD dans Analyse** : le scoring texte devient un mode "Coller du texte" dans la page Analyse. Ca réduit le menu de 7 à 6 entrées.
- Le Preview dans Import reste distinct car son objectif est différent (vérifier le mapping, pas explorer les données).

### Scoring sans mapping = bruit

Concaténer toutes les valeurs et scorer produit des faux positifs. Un champ `"statut": "MARTIN"` sera flaggé comme patronyme. Mitigations :
- Afficher un avertissement : "Le scoring sans mapping est indicatif. Certains mots peuvent être détectés à tort."
- En v2, proposer un scoring par champ individuel avec le type détecté.

### JSON imbriqué (unwrap)

Pour un fichier type SignalConso, le champ `RCLMFicheReportJsonSC` contient du JSON stringifié brut. Sans unwrap, la card affiche une chaîne illisible. Mitigation :
- Détecter automatiquement les champs contenant du JSON stringifié et les afficher dépliés dans la card (réutiliser la logique de `_analyze_nested` de `/api/mapping/generate`).

### Parcours utilisateur incomplet

Après analyse, l'utilisateur voit des scores élevés mais pas de bouton pour passer à l'action. Mitigation v1 :
- Ajouter un `fr-callout` en bas de la page Analyse : "Pour pseudonymiser ce fichier, rendez-vous dans l'onglet Import fichier" avec un lien vers `#import-fichier`.

### Volume de cards sur mobile

20 cards = beaucoup de scroll sur mobile. Mitigation :
- Afficher les cards repliées par défaut (titre + badge uniquement), dépliables au clic (pattern accordéon).

---

## Hors perimètre (v1)

- Bouton "Pseudonymiser ce fichier" qui bascule vers Import avec le fichier pré-chargé (v2)
- Export PDF du rapport d'analyse (v2)
- Scoring par champ individuel au lieu du scoring global par enregistrement (v2)
- Pagination au-delà de 20 enregistrements (v2)
- Fusion effective de la page Scoring RGPD dans Analyse (v1.1 -- à valider)

---

## Verification

1. Charger un fichier JSON structuré → 20 cards avec scores
2. Charger un fichier CSV → colonnes comme clés, scores par ligne
3. Charger un fichier DOCX → 1 card avec texte tronqué, score sur le texte complet
4. Charger un fichier TXT → 1 card avec texte tronqué
5. Bouton Copier → coller dans un éditeur, vérifier le format
6. Mode fort activé → scores plus élevés (plus de détections)
7. Accessibilité : navigation clavier, lecteur d'écran annonce les scores
8. Tests : `python3 tests/test-options.py` + `python3 tests/test-v3.py` → 0 FAIL
