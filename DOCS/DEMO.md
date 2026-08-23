# DEMO.md

Happy path de la démo finale, rejoué tel quel au palier 4 et en soutenance.
Volontairement limité à ce qu'exige le MVP — pas de fonctions bonus
(annulation, replanification) dans ce scénario, voir AGENTS.md pour ces cas.

1. J'ouvre Tauturu. Écran d'accueil centré, un seul champ. Je saisis :
   "Prépare l'arrivée de Panaki, développeur backend, qui commence le 1er Septembre."

2. L'agent vérifie d'abord que Panaki n'existe pas déjà (`list_employees`),
   puis propose UNE SEULE carte : enregistrer Panaki. Le message explique
   pourquoi ça s'arrête là pour l'instant — tant que cette fiche n'existe
   pas réellement en base, l'agent ne peut ni consulter ses disponibilités,
   ni lui envoyer de mail, ni le convier à une réunion.

3. J'approuve l'enregistrement. Sans rien retaper, un nouveau message
   agent apparaît tout de suite dans le fil : l'agent a lui-même repris la
   main et propose maintenant 4 cartes d'un coup — réunion d'intégration
   avec le manager (Adam), mail de bienvenue à Panaki seul, réunion
   collective avec toute l'équipe, mail à toute l'équipe qui annonce
   l'arrivée et invite à cette réunion. Chaque carte affiche l'outil, un
   résumé structuré (qui, quand, objet/titre) et la raison invoquée.

4. J'approuve la réunion collective. Et refuse la carte du mail d'équipe en dépend : sans recharger, la page perd ses boutons.

5. J'approuve les deux cartes restantes (réunion manager, mail de
   bienvenue à Panaki). Chaque approbation exécute réellement l'action
   (pas d'étape "lancer l'exécution" séparée). Je bascule sur l'onglet
   Calendrier : la réunion d'intégration y apparaît.

6. Onglet Historique : les 5 actions de la session, avec leur statut final
   (4 exécutées, 1 refusée) et l'horodatage de chacune.

**Limites connues à anticiper pendant la démo :**
- Pas de badge "irréversible" ni d'affichage du `depends_on` sur les
  cartes avant décision — la dépendance ne se révèle qu'au moment où elle
  bloque quelque chose.
- Le nombre et l'ordre exact des 4 actions proposées à l'étape 3 peuvent
  varier légèrement d'une exécution à l'autre (modèle non-déterministe) —
  si le mail d'équipe manque à l'appel, retaper "Continue." le fait
  apparaître.
