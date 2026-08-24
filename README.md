# Tauturu

Agent RH à effets de bord — écriture réelle en base employés, calendrier et
mail mockés localement (assumé et documenté) — avec un plan d'actions soumis
à validation humaine avant toute exécution. Voir [SPEC.md](DOCS/SPEC.md)
pour le problème et les user stories.

## Choix techniques

| Brique | Choix | Pourquoi |
|---|---|---|
| Backend / API | Python, FastAPI | Écosystème riche pour l'agentique, typage natif, cohérent avec Pydantic pour valider le plan d'actions. |
| Modèle | OpenAI (`gpt-4o-mini` par défaut), Groq (`openai/gpt-oss-120b`) en repli documenté | Les deux exposent une API de tool calling compatible OpenAI, donc la même boucle leur parle sans changer de format (voir Quickstart pour basculer). Notre boucle planificateur/exécuteur est un pattern maison spécifique (voir AGENTS.md) — écrire la boucle à la main donne un contrôle total, plutôt que d'adapter le design aux hypothèses d'un SDK agentique sous 3 jours. |
| Front | HTML/JS/CSS vanilla, servis en statique par FastAPI | Pas de build front à gérer, plus rapide à livrer en 3 jours ; suffisant pour une sidebar, un chat, une vue calendrier et un écran d'approbation ligne par ligne. |
| Stockage | SQLite | Un seul fichier, zéro configuration, cohérent avec les mocks calendrier/mail déjà prévus (voir SPEC.md, hors scope). Sert aussi à la persistance des conversations (palier 4). |

## Quickstart

```
git clone <repo>
cd holberton-hackathonagentic
python3 -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner une clé API (voir ci-dessous)
uvicorn backend.main:app --reload --port 8000
# ouvrir http://localhost:8000
```

Le code appelle OpenAI par défaut (`backend/agent.py` lit
`OPENAI_API_KEY` / `OPENAI_MODEL`, défaut `gpt-4o-mini`) :

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Groq (`openai/gpt-oss-120b`, testé et utilisé plus tôt dans le projet) reste
une alternative viable si le quota OpenAI est épuisé — mais c'est un
changement de code, pas juste de `.env` : `backend/agent.py` importe
explicitement `from openai import OpenAI`, il faut le remplacer par
`from groq import Groq` et adapter le client (le format d'appel,
compatible OpenAI côté Groq, reste identique). `GROQ_API_KEY`/`GROQ_MODEL`
dans `.env.example` documentent ce repli. Aucune clé n'est jamais exposée
côté front (`frontend/` ne fait que parler à notre propre API).

## Qualité / durcissement (palier 5)

- `eval/cases.md` : 5 cas rejoués à la main contre l'app réelle (happy
  path, personne inconnue, injection de prompt, plage de dates absurde,
  outil désactivé), avec attendu vs obtenu et score actuel.
- `make eval` (ou `python3 eval/run_eval.py`) : les mêmes cas rejoués en
  une commande contre l'app en tournant, score chiffré affiché.
- `make test` (ou `pytest tests/`) : vérifie qu'une erreur d'outil remonte
  dans la trace au lieu de faire planter la boucle ou d'inventer un
  résultat.
- Dégradation testée en conditions réelles : quota/clé API invalide →
  message d'erreur clair renvoyé au RH, jamais de crash ni de blocage.

## Architecture

Le front envoie le message du RH à `/chat` avec un `conversation_id` (la
conversation elle-même est persistée côté serveur en SQLite, voir
`backend/conversations.py` — le navigateur ne garde qu'un pointeur en
`localStorage`). FastAPI passe la main à la boucle planificateur
(`backend/agent.py`), qui appelle le LLM avec ses outils de
lecture/proposition (`list_employees`, `list_calendar_events`,
`get_employee_availability`, `find_common_slot`, `propose_action` — voir
[AGENTS.md](AGENTS.md)) jusqu'à ce que le plan soit complet. Chaque action à effet
de bord proposée est écrite en SQLite à l'état `PROPOSEE`, jamais exécutée
par le modèle lui-même.

Le plan s'affiche ligne par ligne dans le chat ; le RH approuve ou refuse
chaque action. `backend/executor.py` exécute alors réellement l'action
(écriture en base, fichier dans `outbox/`), de façon idempotente, et une
confirmation s'affiche. Un refus bloque en cascade toute action qui en
dépendait — la mise à jour est immédiate dans l'interface, sans recharger
la page. Historique complet consultable dans l'onglet "Historique"
(`GET /actions`).

Cas particulier : approuver `register_employee` relance automatiquement le
planificateur pour proposer la suite du plan (réunions, mails) sans que le
RH ait à retaper quoi que ce soit — l'`employee_id` n'existe qu'une fois
cette action exécutée, donc le reste du plan ne peut être construit qu'à
ce moment-là (voir AGENTS.md).

Chaque outil de lecture, plus `send_email`, peut être désactivé à la volée
depuis le volet "Outils de l'agent" de la sidebar (`GET/POST /tools`) — pour
la démo, sans toucher au code ni redémarrer le serveur : l'agent explique
l'échec au lieu de planter ou d'inventer un résultat.

Schéma détaillé en annexe : [DOCS/architecture.md](DOCS/architecture.md).

## Limites connues

- Heures de travail codées en dur (9h-18h, jours ouvrés) dans
  `get_employee_availability` — pas de mock ni d'API externe pour ça.
- `get_employee_availability`/`find_common_slot` refusent une `date_range`
  de plus de 31 jours (erreur explicite plutôt qu'un pavé de créneaux) —
  mais si le RH redemande une plage plus large, l'agent réessaie avec des
  fenêtres plus petites et peut présenter le résultat comme s'il avait
  couvert toute la plage demandée alors qu'il n'a cherché que sur les
  premiers jours (voir `eval/cases.md`, cas 4).
- Pas de fichier `.ics` généré pour les événements de calendrier (optionnel
  dans AGENTS.md, non fait).
- Le coût affiché par requête (`usage.total_cost_usd`) n'est calculé que
  pour `gpt-4o-mini` (tarif connu) ; `null` pour les autres modèles plutôt
  que d'inventer un prix.
- Calendrier et mail mockés localement, assumé et documenté (voir SPEC.md,
  hors scope).
- Pas de badge "irréversible" ni d'affichage du `depends_on` sur les
  cartes avant décision — la dépendance ne se révèle qu'au moment où elle
  bloque quelque chose.
- Le nombre exact d'actions proposées par l'agent pour un même plan peut
  varier légèrement d'un run à l'autre (modèle non-déterministe) — voir
  `eval/cases.md`.
