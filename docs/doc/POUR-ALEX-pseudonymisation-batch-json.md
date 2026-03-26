# Pseudonymisation batch d'un JSON SignalConso — Retour pédagogique

---

## 1. Approche choisie

Le problème de départ : un fichier JSON de 112 Mo contenant 31 891 réclamations consommateurs avec des noms, emails, téléphones, adresses en clair. L'objectif : pouvoir travailler dessus avec Claude sans jamais lui envoyer de données personnelles.

On a choisi de **porter les regex de Pseudonymus v2 (app navigateur) dans un script Python local**. Pourquoi ? Parce que Pseudonymus fait déjà exactement ce qu'on veut — détecter et remplacer les données personnelles — mais son interface navigateur ne peut pas avaler 112 Mo de JSON. C'est comme avoir une excellente recette mais une casserole trop petite : on garde la recette, on change la casserole.

Le script traite le fichier en 3 phases : champs structurés (remplacement direct), texte libre (regex + lookup noms), ré-sérialisation du JSON imbriqué. Deux modes au choix : pseudonymisation réversible (avec table de correspondances) ou anonymisation définitive.

---

## 2. Alternatives écartées

**Adapter Pseudonymus pour ingérer du JSON dans le navigateur.** C'était tentant — ne rien réécrire, juste ajouter un import JSON. Mais charger 112 Mo dans un onglet de navigateur, c'est demander à un vélo de tracter une remorque : ça marche en théorie, ça plante en pratique. Le moteur JS alloue des objets pour chaque élément du DOM, la mémoire explose, et le navigateur freeze. L'analyse connu-inconnu a tué cette option dès le départ.

**Pré-traitement en CSV aplati.** Extraire les champs sensibles dans un CSV, pseudonymiser, puis réinjecter. Plus simple à coder, mais on perd la structure JSON imbriquée (le JSON stringifié dans le JSON). La réinjection aurait été un cauchemar d'encodage. On a préféré garder la structure intacte.

**Utiliser une librairie NLP (spaCy, Presidio) pour la détection.** Presidio de Microsoft fait exactement de la détection d'entités nommées pour la pseudonymisation. Mais ça installe des modèles de 500 Mo, ça nécessite un setup complexe, et les regex de Pseudonymus sont déjà calibrées pour le français (noms INSEE, formats téléphones FR, NIR). Pourquoi sortir l'artillerie lourde quand un fusil de précision fait le travail ?

---

## 3. Architecture et articulation

Le script suit un pipeline linéaire, et l'ordre compte :

```
JSON source → double-parse → Phase 1 (structuré) → Phase 2 (texte libre) → ré-sérialisation → JSON sortie
```

**Le double-parse** est le point technique clé. Le JSON de SignalConso a une structure inhabituelle : chaque enregistrement contient un champ `RCLMFicheReportJsonSC` qui est lui-même une chaîne JSON. Il faut donc parser le JSON externe, puis parser cette chaîne pour accéder au `Report`. À la sortie, il faut re-sérialiser le Report en chaîne, puis le remettre dans l'enveloppe. C'est comme une poupée russe : il faut ouvrir les deux couches pour travailler, puis les refermer dans le bon ordre.

**L'ordre des regex dans la Phase 2** n'est pas arbitraire :
1. Emails d'abord — sinon une regex téléphone pourrait casser une adresse email
2. NIR avant téléphones — un NIR ressemble à une suite de chiffres qu'une regex téléphone pourrait capturer
3. Cartes bancaires avec validation Luhn — pour filtrer les faux positifs sur les numéros de commande

**La table de correspondances globale** (classe `TokenTable`) garantit la cohérence inter-enregistrements : si la même personne apparaît dans 3 réclamations, elle obtient le même jeton partout. Sans ça, on pourrait recouper les données par différence.

---

## 4. Outils et méthodes

**Python pur, zéro dépendance externe.** Le script n'utilise que la bibliothèque standard : `json`, `re`, `csv`, `argparse`, `uuid`. C'est un choix délibéré : pas de `pip install`, pas de virtualenv, ça tourne sur n'importe quel Mac avec Python 3. Pour un outil de sécurité des données, minimiser les dépendances, c'est minimiser la surface d'attaque.

**Le module `re` de Python** pour le portage des regex. Attention : Python `re` ne supporte pas les lookbehind de longueur variable comme JavaScript. La regex `telFuzzy` de Pseudonymus utilisait `(?<!\d)` qui en JS peut précéder des patterns de longueur variable — en Python, le lookbehind doit être de taille fixe. On a adapté (pas copié) les regex.

**L'analyse connu-inconnu** (skill `/connu-inconnu`) a été utilisée deux fois : d'abord pour évaluer la faisabilité, puis pour auditer le PRD. C'est comme faire relire un plan par quelqu'un qui cherche ce qui manque, pas ce qui est bien. Ça a révélé les identifiants traçables (`DOAR_IDENT`, `Id`) qu'on avait oublié initialement.

**Le dry-run** traite 100 enregistrements et affiche des stats sans écrire de fichier. C'est l'équivalent d'un vol d'essai avant le décollage : on vérifie que les moteurs tournent avant de s'engager sur 31 891 enregistrements.

---

## 5. Compromis

**Précision vs rappel dans le texte libre.** On a choisi de ne matcher les prénoms courts (< 4 lettres) que combinés avec le nom de famille. « Léa » toute seule dans un texte pourrait être un mot courant — on accepte de rater quelques occurrences isolées plutôt que de créer des faux positifs partout. C'est un compromis explicite : mieux vaut laisser passer 2% de vrais noms que de casser 10% du texte.

**Adresses sans numéro sacrifiées.** La regex `RX_VOIE_SANS` (« rue Victor Hugo » sans numéro) produisait 37% de faux positifs (« allée dans un magasin »). On l'a retirée pour ne garder que `RX_VOIE_NUM` (« 43 rue Pierre Brossolette »). Une adresse sans numéro dans une réclamation consommateur est rare et peu identifiante.

**Siret conservé tel quel.** Le SIRET identifie une entreprise, pas une personne. Sauf pour les auto-entrepreneurs où SIRET = identifiant personnel indirect. On a documenté le risque et choisi de ne pas traiter pour l'instant — c'est dans le hors-périmètre explicite du PRD plutôt que dans un angle mort silencieux.

**JSON en mémoire complète vs streaming.** On charge les 112 Mo d'un coup avec `json.load()`, ce qui consomme ~400-600 Mo de RAM. Sur un Mac Mini 8 Go c'est jouable. L'alternative streaming (`ijson`) aurait été plus économe mais plus complexe à coder pour la ré-sérialisation. Le compromis : simplicité de code contre consommation mémoire.

---

## 6. Erreurs et impasses

**La regex d'adresses sans numéro.** C'est l'erreur la plus instructive. Le premier dry-run a montré 8 détections d'adresses dont 3 faux positifs flagrants : « allée dans un autre magasin », « allée sur le site de la mairie ». La regex matchait tout mot de voie suivi de 3+ caractères. On a d'abord proposé de la restreindre aux mots suivants commençant par une majuscule — mais après réflexion, même ça n'aurait pas suffi (« allée Victor » dans un contexte non-adresse). La bonne réponse était de la retirer, pas de la complexifier.

**Oubli des identifiants traçables.** Le premier PRD ne traitait que les données personnelles évidentes (nom, email, téléphone). L'analyse connu-inconnu a révélé que `DOAR_IDENT` et `Id` (UUID) sont des identifiants permettant de remonter à la source dans la base SignalConso. Sans les pseudonymiser, on livre une clé de jointure avec la base d'origine. C'est comme changer les serrures en laissant le double sous le paillasson.

**Le Gender oublié.** Même logique : Male/Female n'est pas sensible isolément, mais combiné avec un code postal et une catégorie de réclamation, ça réduit le pool de candidats possibles. L'évaluation itérative du PRD l'a rattrapé.

---

## 7. Pièges à éviter

**Ne jamais copier des regex entre langages sans les tester.** JS et Python ont des dialectes regex différents. Le lookbehind variable de JS passe silencieusement en Python 3.7+ mais peut avoir des comportements subtils différents. Toujours tester chaque regex sur un corpus de cas limites après le portage.

**Le JSON stringifié dans du JSON est un piège d'encodage.** Les guillemets, les retours à la ligne (`\n`), les caractères unicode dans le JSON interne doivent survivre au double-parse + double-sérialisation. Si tu fais `json.dumps` sans `ensure_ascii=False`, les accents français sont échappés en `\uXXXX` et le fichier de sortie est illisible.

**Le dry-run n'est pas optionnel.** Sur 31 891 enregistrements, un faux positif à 1% = 318 textes corrompus. Le dry-run sur 100 enregistrements a détecté le problème des adresses avant qu'il ne touche le dataset complet. Ne jamais lancer un traitement batch sans tester sur un échantillon d'abord.

**Le CSV de correspondances est la donnée la plus sensible du projet.** Plus que le JSON original, parce qu'il contient toutes les données personnelles concentrées dans un seul fichier facile à lire. Le gitignorer, le chmod 600, le stocker séparément — ce n'est pas de la paranoïa, c'est le minimum.

---

## 8. Regard expert

**Le PRD itératif était la vraie valeur ajoutée.** Un développeur pressé aurait écrit le script directement. Le cycle PRD → évaluation → correction → réévaluation a pris du temps mais a rattrapé les identifiants traçables, le Gender, la gestion d'erreurs, le dry-run, la sécurité du CSV, la stratégie noms courts. Chacun de ces points aurait été un bug ou une fuite de données découvert après coup.

**La contrainte « zéro donnée vers Claude » a structuré toute l'architecture.** C'est elle qui a imposé le script local, le dry-run, la séquence humain-dans-la-boucle. Sans cette contrainte, on aurait peut-être envoyé le JSON à Claude en lui demandant de pseudonymiser — et on aurait envoyé 31 891 données personnelles à un service externe. La contrainte de sécurité n'est pas un frein, c'est un guide de conception.

**L'ordre d'application des regex est un problème de pipeline, pas de regex.** Un expert en NLP le sait : quand tu appliques des transformations séquentielles sur du texte, chaque transformation modifie l'entrée de la suivante. Si tu remplaces les emails après les téléphones, le `@` d'une adresse email pourrait avoir été grignoté. L'ordre n'est pas un détail d'implémentation, c'est une décision d'architecture.

---

## 9. Leçons transférables

**Tout traitement de données sensibles devrait commencer par un PRD, pas par du code.** Pas parce que le PRD est un document administratif, mais parce qu'il force à répondre à « quoi exactement ? » avant « comment ? ». Les identifiants traçables, le Gender, le CSV de correspondances — rien de tout ça ne serait sorti d'une session de codage directe.

**L'analyse connu-inconnu est un outil de pensée, pas de gestion de projet.** Elle ne produit pas un plan d'action, elle produit une carte des angles morts. L'utiliser sur un PRD, c'est comme faire un contrôle technique sur une voiture qu'on vient de construire : le but n'est pas de dire qu'elle roule, mais de trouver ce qui ne roule pas.

**Le dry-run est un pattern universel.** Que tu migres une base de données, que tu envoies un mailing à 30 000 personnes ou que tu pseudonymises un JSON, le principe est le même : tester sur un échantillon, vérifier les résultats, puis lancer. Le coût d'un dry-run est dérisoire. Le coût de ne pas en faire est potentiellement catastrophique.

**Les faux positifs sont plus dangereux que les faux négatifs dans la pseudonymisation du texte libre.** Un faux négatif (un nom non détecté) laisse une fuite ponctuelle. Un faux positif (un mot courant remplacé par un jeton) corrompt le texte et rend les données inutilisables pour l'analyse. Mieux vaut être conservateur dans les regex et compenser par le lookup direct des noms connus.

**Quand une regex produit plus de 30% de faux positifs, la retirer est meilleur que la raffiner.** C'est contre-intuitif — on a envie de « réparer » la regex. Mais chaque raffinement ajoute de la complexité et des cas limites. Parfois la bonne réponse est de reconnaître qu'un pattern n'est pas assez discriminant et de l'abandonner.
