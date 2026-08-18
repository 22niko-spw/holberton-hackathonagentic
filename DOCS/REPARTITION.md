# REPARTITION.md

Répartition du travail entre niko et Panaki.

## Principe

Pas de split front/back figé sur toute la durée : le sujet prévient
explicitement qu'un binôme où l'un code et l'autre regarde se fait repérer
au palier 3, et le checkpoint alterne qui répond. On répartit donc par
**tranches verticales** (chaque outil = son back + son affichage front), pour
que chacun ait codé du front et du back, et on fait le cœur agentique **à
deux**, parce que c'est la pièce la plus risquée et la plus interrogée à
l'oral.

## Fait à deux (cœur agentique)

- Squelette FastAPI + connexion Groq
- Boucle planificateur (appel modèle, `propose_action`, garde-fous)
- Boucle exécuteur (idempotence via `action_id`, journal d'audit)
- Écran de plan / approbation (le composant central, action par action)

## Réparti par outil (back + front de l'outil)

| niko | Panaki |
|---|---|
| `get_employee_availability` | `create_calendar_event` |
| `find_common_slot` | `send_email` |
| `register_employee` | Écran journal + affichage des états (`PROPOSEE`/`APPROUVEE`/`REFUSEE`/`BLOQUEE`) |

## Rotation des checkpoints

Le sujet impose d'alterner qui répond à l'oral d'un checkpoint à l'autre.

| Palier | Répond |
|---|---|
| 1 · Cadrage | fait à deux |
| 2 · Socle | Panaki |
| 3 · Premier outil | niko |
| 4 · Boucle fermée (MVP) | Panaki |
| 5 · Durcissement | niko |
| 6 · Livraison | Panaki |
| Soutenance | les deux parlent (imposé par le barème) |

Peu importe qui a écrit la ligne de code interrogée : celui désigné doit
pouvoir l'expliquer. D'où le choix de coder le cœur à deux et de garder
chaque tranche assez petite pour que l'autre l'ait relue.
