# DEMO.md

Happy path de la démo finale (6 étapes), rejoué tel quel au palier 4 et en
soutenance. Volontairement limité à ce qu'exige le MVP — pas de fonctions
bonus (annulation, replanification) dans ce scénario, voir AGENTS.md pour
ces cas.

1. J'ouvre l'application. Un seul champ au centre de l'écran. Je saisis :
   "Prépare l'arrivée de Panaki, développeur backend, qui commence lundi."

2. Le plan se construit sous mes yeux. L'agent consulte d'abord les
   disponibilités via `find_common_slot`, puis propose 4 actions, toutes
   décochées : enregistrer Panaki, poser la réunion d'intégration avec son
   manager, envoyer un mail de bienvenue à Panaki, annoncer son arrivée à
   l'équipe. Chaque ligne affiche l'outil concerné, ses arguments, la raison
   invoquée, et si elle est réversible.

3. La ligne "mail de bienvenue" est marquée IRRÉVERSIBLE en rouge, avant
   tout clic. La ligne "annonce à l'équipe" indique qu'elle dépend de la
   précédente : on ne prévient pas l'équipe d'un mail de bienvenue qui n'est
   jamais parti.

4. J'approuve l'enregistrement de Panaki et la réunion d'intégration. Je
   refuse le mail de bienvenue. La ligne "annonce à l'équipe" bascule
   automatiquement en bloquée, avec le motif affiché : elle dépendait d'une
   action refusée.

5. Je lance l'exécution. Les deux actions approuvées partent l'une après
   l'autre. La fiche de Panaki apparaît réellement en base, l'événement de
   réunion d'intégration apparaît réellement dans le calendrier mocké. Le
   journal se remplit en direct, horodaté.

6. Je consulte le journal : deux actions exécutées, une refusée, une
   bloquée. La trace complète du plan, de la décision humaine et du
   résultat est disponible en un coup d'œil.

**Cas d'échec de la minute 5** : le refus du mail de bienvenue qui bloque
automatiquement l'annonce à l'équipe. Ce n'est pas un bug, c'est le
garde-fou des dépendances qui fonctionne.
