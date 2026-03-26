# PRD : Navigation par ancres et fil d'Ariane DSFR

**Date** : 2026-03-26
**Statut** : Livré
**Auteur** : Alex
**Contexte** : Interface web de pseudonymisation (`generique/interface/`)

---

## Problème

L'interface actuelle utilise un système de navigation JavaScript pur (`data-page` + `classList.toggle`). Les pages sont des `<section>` masquées/affichées par JS. Conséquences :

- **Pas de support navigateur** : les boutons Précédent/Suivant du navigateur ne fonctionnent pas
- **Pas de liens bookmarkables** : on ne peut pas partager ou sauvegarder un lien direct vers une page
- **Pas de fil d'Ariane** : l'utilisateur ne sait pas où il se trouve dans l'arborescence
- **Accessibilité** : les lecteurs d'écran ne détectent pas le changement de contexte

---

## Solution

### Routage par ancres (`hash`)

Chaque page est identifiée par un fragment d'URL :

| Page | URL | Ancre |
|------|-----|-------|
| Pseudonymisation | `/` ou `/#pseudonymisation` | `#pseudonymisation` |
| Correspondances | `/#correspondances` | `#correspondances` |
| Restauration | `/#restauration` | `#restauration` |
| Import fichier | `/#import-fichier` | `#import-fichier` |
| Scoring RGPD | `/#scoring-rgpd` | `#scoring-rgpd` |
| Documentation | `/#documentation` | `#documentation` |

**Comportement** :

1. Au chargement, lire le `window.location.hash` et afficher la page correspondante
2. Si pas de hash, afficher `#pseudonymisation` (page par défaut)
3. Écouter `hashchange` pour naviguer quand l'utilisateur clique ou utilise Précédent/Suivant
4. Les liens de navigation utilisent `href="#ancre"` au lieu de `href="#"` + JS
5. Le titre de la page (`<title>`) est mis à jour dynamiquement

### Fil d'Ariane DSFR

Composant `fr-breadcrumb` conforme au Design System de l'État :

```html
<nav role="navigation" class="fr-breadcrumb" aria-label="vous êtes ici :">
    <button class="fr-breadcrumb__button" aria-expanded="false" aria-controls="breadcrumb">
        Voir le fil d'Ariane
    </button>
    <div class="fr-collapse" id="breadcrumb">
        <ol class="fr-breadcrumb__list">
            <li>
                <a class="fr-breadcrumb__link" href="#pseudonymisation">Accueil</a>
            </li>
            <li>
                <a class="fr-breadcrumb__link" aria-current="page">Page courante</a>
            </li>
        </ol>
    </div>
</nav>
```

- Placé entre le header et le contenu principal (`<main>`)
- Mis à jour dynamiquement à chaque changement de page
- Premier niveau : toujours "Accueil" pointant vers `#pseudonymisation`
- Deuxième niveau : nom de la page courante avec `aria-current="page"`
- Sur la page d'accueil (Pseudonymisation), un seul niveau affiché

### Page Documentation

Nouvelle page `#documentation` avec :

- Présentation de l'outil (objectif, traitement local)
- Formats supportés (tableau)
- Options de détection (standard, fort, tech, NLP)
- Structure du mapping (explication des champs)
- Exemples de mapping (JSON plat, SignalConso)
- Commandes CLI équivalentes

---

## Fichiers impactés

| Fichier | Modification |
|---------|-------------|
| `generique/interface/index.html` | Ajout fil d'Ariane, liens `href="#ancre"`, section Documentation |
| `generique/interface/app.js` | Routeur hash, mise à jour breadcrumb et title |

---

## Critères de validation

| # | Critère |
|---|---------|
| 1 | Navigation par hash : `/#correspondances` affiche la page Correspondances |
| 2 | Boutons Précédent/Suivant du navigateur fonctionnent |
| 3 | Lien direct bookmarkable : ouvrir `http://localhost:8090/#scoring-rgpd` affiche le Scoring |
| 4 | Fil d'Ariane DSFR affiché sous le header, mis à jour à chaque navigation |
| 5 | Page Documentation présente avec contenu utile |
| 6 | `aria-current="page"` sur le bon élément du breadcrumb |
| 7 | Title de la page mis à jour (ex: "Scoring RGPD - Pseudonymisation") |
| 8 | Aucune régression sur les fonctionnalités existantes |
| 9 | Audit accesslint : zéro violation |
