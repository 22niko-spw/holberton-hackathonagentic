# AGENTS.md

Outils, signatures et fonctionnement de l'agent.

## Pourquoi le modèle ne touche jamais aux effets de bord

Le sujet est clair : un agent qui exécute une action avant validation humaine
est éliminatoire, quel que soit le reste. On ne voulait pas s'en remettre à
une instruction dans le prompt système pour garantir ça — un prompt peut
être mal suivi, mal interprété, ou contourné par une entrée utilisateur
piégée.

À la place, `create_calendar_event`, `send_email`, `register_employee`,
`delete_employee` et `delete_calendar_event` ne sont **jamais donnés au
modèle** comme outils appelables. Le modèle peut seulement demander à ce
qu'une action soit ajoutée à un plan (via `propose_action`), et un morceau
de code séparé, qui ne repasse par aucun LLM, se charge de l'exécution une
fois qu'un humain a approuvé.

Deux conséquences concrètes :
- Même si le modèle "décide" d'appeler `send_email` directement, l'appel
  échoue : la fonction n'existe pas dans son contexte.
- Toute la logique de validation/refus/blocage se fait donc en dehors du
  modèle, sur des données structurées (une table `actions`), pas sur du
  texte généré.

## Cycle de vie d'une action

```
PROPOSEE --(RH approuve)--> APPROUVEE --(exécuteur)--> EXECUTEE
PROPOSEE --(RH refuse)-----> REFUSEE
   |
   v (si une autre action dépend de celle-ci)
BLOQUEE
```

Une action peut déclarer une dépendance (`depends_on`) vers une autre action
du même plan. Si l'action dont elle dépend est refusée, elle passe
automatiquement en `BLOQUEE` sans que le RH ait à la traiter une par une.
Exemple : si `register_employee` est refusée, l'email de bienvenue qui en
dépend n'a plus lieu d'être envoyé — il se bloque tout seul.

## Déroulé complet

1. Le RH formule une intention en langage naturel ("prépare l'arrivée de
   Panaki").
2. Le modèle reçoit l'intention et un accès en lecture (calendrier, données
   employés) pour construire son plan. À chaque étape, il peut soit lire des
   données, soit ajouter une action au plan avec `propose_action` — jamais
   exécuter directement.
3. La boucle s'arrête quand le modèle n'a plus besoin d'outils : le plan est
   considéré complet. Garde-fous : nombre max de tours, nombre max
   d'actions par plan, plan rejeté et renvoyé au modèle s'il ne respecte pas
   le format attendu.
4. Le plan (liste d'actions à l'état `PROPOSEE`, avec leurs dépendances)
   s'affiche au RH, ligne par ligne.
5. Le RH approuve ou refuse chaque ligne. Les actions dépendantes d'un refus
   basculent en `BLOQUEE` automatiquement.
6. Un exécuteur — du code classique, sans appel à un LLM — parcourt les
   actions à l'état `APPROUVEE` dans l'ordre de leurs dépendances, vérifie
   dans le journal si l'`action_id` a déjà été traité (idempotence), exécute
   sinon, puis journalise le résultat.

## Outils accessibles au modèle

### `list_employees`

```python
list_employees(name_contains: str | None = None) -> list[dict]
```

- **Effet de bord** : non (lecture seule).
- Annuaire interne : permet au modèle de retrouver l'`employee_id` d'un
  nom cité par le RH, ou de constater que la personne n'existe pas encore
  (un nouvel arrivant). Le modèle n'a pas le droit d'inventer un
  `employee_id` — il doit toujours passer par cet outil avant de citer
  quelqu'un dans un autre appel.

### `list_calendar_events`

```python
list_calendar_events(
    employee_id: str | None = None,
    title_contains: str | None = None
) -> list[dict]
```

- **Effet de bord** : non (lecture seule).
- Plafonné à 20 résultats. Sert à retrouver un `event_id` réel avant de
  proposer `delete_calendar_event` — même principe que `list_employees` :
  jamais d'identifiant deviné.

### `get_employee_availability`

```python
get_employee_availability(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 15
) -> dict[str, list[tuple[datetime, datetime]]]
```

- **Effet de bord** : non (lecture seule).
- Lit un calendrier mocké (SQLite/JSON prérempli) et renvoie, pour chaque
  employé, ses créneaux libres d'au moins `duration_minutes` sur
  `date_range`.
- Les heures de travail (ex. 9h-18h, jours ouvrés) sont codées en dur : pas
  de mock ni d'API externe pour ça. Limite connue, documentée dans le
  README.

### `find_common_slot`

```python
find_common_slot(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 30,
    max_candidates: int = 3
) -> list[tuple[datetime, datetime]] | None
```

- **Effet de bord** : non (lecture seule).
- Croise les disponibilités de tous les `employee_ids` (via
  `get_employee_availability`) et renvoie jusqu'à `max_candidates` créneaux
  communs, pour que le RH choisisse.
- Si rien n'est trouvé sur `date_range`, la recherche s'élargit d'elle-même
  de +7 jours, jusqu'à 3 tentatives (21 jours de plus au maximum), puis
  renvoie `None` si toujours rien.
- Reste volontairement simple : pas de fuseaux horaires, pas de récurrence,
  pas d'optimisation multi-critères (détaillé dans SPEC.md, hors scope).

### `propose_action`

```python
propose_action(
    tool: str,
    args: dict,
    reason: str,
    depends_on: int | None = None
) -> int  # action_id
```

- **Effet de bord** : aucun sur le monde réel. Ajoute une ligne à la table
  `actions` avec l'état `PROPOSEE`. C'est l'unique façon pour le modèle de
  faire figurer une action à effet de bord dans le plan — il ne peut pas
  aller plus loin que ça.
- `tool` doit correspondre à l'un des cinq noms de la section suivante :
  `create_calendar_event`, `send_email`, `register_employee`,
  `delete_employee`, `delete_calendar_event`.
- `depends_on` pointe vers l'`action_id` d'une action du même plan devant
  être exécutée avant celle-ci.
- Cas `register_employee` : si `email` est absent de `args`, il est généré
  automatiquement (`prénom@lebras.com`, voir `tools._default_email`) —
  mécanique et déterministe, pas laissé au modèle. `department`/`manager_id`
  ont aussi des valeurs par défaut côté prompt (`'Produit'`/`'adam'`).

## Actions à effet de bord (exécuteur uniquement)

Ces fonctions ne sont jamais données au modèle comme outils. Il ne peut que
les citer par leur nom dans un `propose_action`.

### `create_calendar_event`

```python
create_calendar_event(
    action_id: str,
    employee_ids: list[str],
    start: datetime,
    end: datetime,
    title: str,
    description: str = ""
) -> str  # event_id
```

- **Effet de bord** : oui — écriture dans la base SQLite mockée, plus un
  fichier `.ics` optionnel.
- Idempotence : l'exécuteur vérifie dans le journal d'audit si `action_id` a
  déjà été traité avant d'écrire quoi que ce soit ; si oui, il renvoie
  l'`event_id` déjà enregistré au lieu d'en recréer un.

### `send_email`

```python
send_email(
    action_id: str,
    employee_ids: list[str],
    subject: str,
    body: str
) -> str  # chemin du fichier dans outbox/
```

- **Effet de bord** : oui, mais rien n'est réellement envoyé — un fichier
  est écrit dans `outbox/` (ex. `outbox/2026-08-18_bienvenue-panaki.txt`)
  avec `to`/`subject`/`body`. Service de messagerie mocké, assumé et
  documenté (voir SPEC.md, hors scope).
- Les adresses sont résolues en interne à partir des `employee_ids`, jamais
  passées directement : un ID inconnu fait lever une erreur plutôt que de
  produire une adresse inventée.
- Même mécanisme d'idempotence que `create_calendar_event`.

### `register_employee`

```python
register_employee(
    action_id: str,
    name: str,
    email: str,
    role: str,
    department: str,
    manager_id: str,
    start_date: date
) -> str  # employee_id
```

- **Effet de bord** : oui — écriture réelle en base SQLite, pas de mock ici.
- Même mécanisme d'idempotence que les deux outils précédents.

### `delete_employee`

```python
delete_employee(action_id: str, employee_id: str) -> dict  # {employee_id, name}
```

- **Effet de bord** : oui, et irréversible — supprime l'employé et, en
  cascade, tous ses événements de calendrier (sinon la contrainte de clé
  étrangère sur `calendar_events.employee_id` bloquerait la suppression).
- Même mécanisme d'idempotence que les autres.

### `delete_calendar_event`

```python
delete_calendar_event(action_id: str, event_id: int) -> dict  # {event_id, title}
```

- **Effet de bord** : oui, irréversible. Le modèle doit avoir appelé
  `list_calendar_events` avant de proposer cette action — jamais
  d'`event_id` deviné.

## Prompts système

`SYSTEM_PROMPT` dans `backend/agent.py` (une seule longue constante,
réinjectée à chaque requête via `_system_prompt()` avec la date du jour).
Sections, dans l'ordre :

1. Cadrage général : agir de façon autonome, poser le moins de questions
   possible.
2. **Résoudre les personnes** — toujours vérifier un nom via
   `list_employees` avant de l'utiliser ; jamais d'identifiant inventé ;
   valeurs par défaut pour `department`/`manager_id`/`email` d'un nouvel
   arrivant, jamais redemandées au RH si absentes.
3. **Planifier** — trouver soi-même un créneau via `find_common_slot`,
   proposer une heure concrète, confirmer avant `propose_action`.
4. **Arrivée d'un nouvel employé** — le plan complet compte 5 actions,
   mais l'`employee_id` n'existe qu'une fois `register_employee` exécuté
   (validation humaine comprise) : impossible de le construire en un seul
   tour. Le prompt impose explicitement l'ordre d'appel de
   `propose_action` (jamais décrire une action en texte sans l'avoir
   réellement proposée — piège rencontré et corrigé pendant le
   développement, voir JOURNAL.md) et le sens des dépendances entre
   actions.
5. **Effets de bord** — schéma exact des `args` attendus par outil, pour
   éviter que le modèle invente des noms de clés.
6. **Suppressions** — jamais d'`employee_id`/`event_id` deviné, toujours
   `list_employees`/`list_calendar_events` d'abord.
7. **Erreurs** — si un outil renvoie une erreur, l'expliquer au RH, ne
   jamais inventer de résultat à la place.

## Traces

Chaque appel d'outil pendant un tour de boucle est capturé dans une liste
`trace` (voir `run_planner` dans `backend/agent.py`) :
`{tool, args, ok, error, duration_ms}`. Une erreur d'outil ne fait jamais
planter la boucle : elle est renvoyée telle quelle au modèle comme
résultat de l'appel, avec consigne explicite de ne pas l'ignorer ni
inventer un résultat à la place (voir `eval/cases.md` et
`tests/test_agent_loop.py`, qui vérifient ce comportement précis).

Chaque appel LLM (pas seulement chaque outil) est aussi mesuré
(`llm_calls` : tokens prompt/completion, durée, coût estimé si le tarif du
modèle est connu) et agrégé dans `usage`. Les deux sont renvoyés par
`/chat` et affichables côté front (masqué par défaut, activable dans
Réglages → "Afficher les outils utilisés").
