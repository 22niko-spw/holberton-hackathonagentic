# DEMO.md

Happy path de la démo finale (6 étapes), rejoué tel quel au palier 4 et en
soutenance.

1. J'ouvre l'application. Un seul champ au centre de l'écran. Je saisis :
   "Prépare l'arrivée de Panaki, développeur backend, qui commence lundi."

2. Le plan se construit ligne par ligne sous mes yeux. L'agent consulte
   d'abord les disponibilités de l'équipe via `find_common_slot`, puis
   propose 5 actions, toutes décochées : enregistrer Panaki, poser la
   réunion d'intégration avec son manager, envoyer un mail de bienvenue à
   Panaki, annoncer son arrivée à l'équipe, réserver un créneau de
   présentation avec les RH. Chaque ligne affiche l'outil concerné, ses
   arguments, la raison invoquée, et si elle est réversible.

3. La ligne "mail de bienvenue" est marquée IRRÉVERSIBLE en rouge, avant
   tout clic. La ligne "annonce à l'équipe" indique qu'elle dépend de la
   précédente : on ne prévient pas l'équipe d'un mail de bienvenue qui n'est
   jamais parti. J'utilise la barre d'ajout : "prévois aussi un rappel
   d'intégration à un mois." Le planificateur repart avec le plan courant en
   contexte et ajoute une 6ᵉ ligne, marquée comme venant de moi, décochée
   comme les autres.

4. J'approuve l'enregistrement de Panaki, la réunion d'intégration, le
   créneau RH et le rappel à un mois. Je refuse le mail de bienvenue. La
   ligne "annonce à l'équipe" bascule automatiquement en bloquée, avec le
   motif affiché : elle dépendait d'une action refusée.

5. Je lance l'exécution. Les quatre actions approuvées partent l'une après
   l'autre. L'événement de réunion d'intégration apparaît réellement dans le
   calendrier mocké. Le journal se remplit en direct, horodaté. Je clique
   une deuxième fois sur exécuter : rien ne repart en double, la clé
   d'idempotence (`action_id` déjà présent dans le journal) a fait son
   travail.

6. Depuis le journal, j'annule la dernière action exécutée (le rappel à un
   mois). La compensation s'exécute, l'événement correspondant disparaît
   réellement du calendrier, et le journal enregistre l'annulation sans
   effacer l'entrée d'origine — on n'annule que la dernière action, pas en
   cascade (voir SPEC.md, hors scope).

**Cas d'échec de la minute 5** : le refus du mail de bienvenue qui bloque
automatiquement l'annonce à l'équipe. Ce n'est pas un bug, c'est le
garde-fou des dépendances qui fonctionne.
