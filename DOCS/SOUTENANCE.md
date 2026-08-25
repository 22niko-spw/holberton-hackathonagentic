# SOUTENANCE.md

Préparation aux 2 minutes de questions (7 min au total : 5 démo + 2
questions, une question posée à chacun·e, personne ne répond à la place de
l'autre). Les 5 questions ci-dessous sont annoncées à l'avance — le jury en
posera une par personne, dans n'importe quel ordre.

Chaque réponse s'appuie sur un fait vérifiable du dépôt (fichier, ligne,
mesure), pas sur une impression. Suggestion de qui porte quoi entre
parenthèses, à ajuster entre vous — l'important est que chacun sache
répondre à n'importe laquelle si le jury choisit autrement.

---

## « Qu'est-ce qui casse en premier si je vous envoie cent utilisateurs ce soir ? »

*(cœur agentique, fait à deux — les deux doivent pouvoir répondre)*

Deux points précis, pas une réponse vague :

1. **`DISABLED_TOOLS` est en mémoire, par process** (`backend/agent.py`,
   confirmé dans `CLAUDE.md`) — avec plusieurs workers uvicorn, désactiver
   un outil depuis un onglet ne le désactive que sur le worker qui a reçu
   cette requête.
2. **Pas de rate-limiting ni de file d'attente sur `/chat`** — 100 messages
   simultanés tapent directement l'API OpenAI sans throttling côté serveur.
   Le premier symptôme concret serait des `429` OpenAI renvoyés en
   cascade, pas un crash de l'app elle-même.
3. SQLite encaisse mal l'écriture concurrente à charge, mais c'est le
   symptôme n°3, pas le premier — les deux points au-dessus cassent avant.

## « Montrez-moi la partie du code dont vous êtes le moins fier, et dites-moi pourquoi. »

*(niko — `get_employee_availability`/`find_common_slot`)*

Le message final que renvoie l'agent quand une plage de dates dépasse
`MAX_RANGE_DAYS` (31 jours). Le garde-fou technique marche : rejet propre,
puis réessai automatique sur des fenêtres plus petites, créneaux réels
trouvés. Mais le texte renvoyé au RH dit avoir cherché "sur les six
prochains mois" alors qu'il n'a en réalité regardé que les ~3 premières
semaines. Rien d'inventé dans les données (les créneaux sont réels), mais
une formulation qui surstate la portée de la recherche sans le signaler —
identifié en éval (cas 4/5 de `eval/cases.md`, score 4/5 et pas 5/5 à
cause de ça), documenté, pas corrigé. Le fix identifié : forcer le prompt
à dire explicitement "je n'ai regardé que les N premiers jours".

## « Sur quoi l'IA vous a-t-elle fait perdre le plus de temps ? »

*(cœur agentique, fait à deux)*

Le plan d'arrivée à 6 actions (2 réunions + 2 mails séparés). Le modèle
fusionnait systématiquement les deux mails distincts en un seul, de façon
reproductible sur 3 tests consécutifs, malgré 3 formulations de prompt
différentes testées (`JOURNAL.md`, Entrée 3). Décision prise de refuser de
continuer à chasser ce comportement plutôt que de s'enferrer dans un
prompt de plus en plus fragile pour un gain cosmétique — retour à un plan
à 5 actions, fusion assumée et documentée.

## « Si vous aviez trois jours de plus, quelle serait la première chose que vous feriez, et surtout pourquoi celle-là avant les autres ? »

*(Panaki — écran de plan / cartes d'action)*

Le badge "irréversible" + l'affichage explicite de `depends_on` sur les
cartes avant décision (limite connue, README + `JOURNAL.md`). Pas le bug
techniquement le plus grave du dépôt — mais la pièce la plus proche du
cœur de la promesse du produit : "l'humain garde le contrôle". Aujourd'hui
le RH approuve une carte sans savoir si l'action est réversible (un
rendez-vous) ou non (un email envoyé, un employé supprimé) avant de
cliquer. Toutes les autres limites connues (streaming, `groq_client.py`
mort, formulation trompeuse sur les dates) sont soit cosmétiques, soit
déjà contournées ; celle-ci touche directement à la gouvernance, qui est
l'argument central du pitch.

## « Combien coûte une exécution complète de votre agent ? »

*(cœur agentique, fait à deux)*

Avec `gpt-4o-mini` (`PRICING_PER_MILLION_TOKENS` dans `backend/agent.py` :
0,15 $/1M tokens input, 0,60 $/1M tokens output), un onboarding complet
tourne autour de 8 tours de boucle (commentaire dans le code sur
`MAX_TURNS`). Estimation : **de l'ordre de 0,3 à 0,5 centime de dollar**
par arrivée traitée de bout en bout. Le chiffre exact par requête est déjà
calculé en direct (`usage.total_cost_usd`, retourné par `/chat` et visible
dans Réglages → affichage des outils utilisés) — s'il y a le temps, montrer
ce chiffre en live pendant la démo est plus fort qu'une estimation à
l'oral.

---

## Rappel : ce qui tue une soutenance

Ne pas commencer par l'architecture. Personne ne l'a demandée — montrer le
problème, montrer qu'il est résolu, expliquer comment ensuite si le temps
le permet (voir `Présentation Tauturu hackathon Holberton.pdf`, qui suit
déjà cet ordre : problème → solution → démo → architecture).
