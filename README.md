# holberton-hackathonagentic

Agent RH à effets de bord — écriture réelle en base employés, calendrier et
mail mockés localement (assumé et documenté) — avec un plan d'actions soumis
à validation humaine avant toute exécution. Voir [SPEC.md](DOCS/SPEC.md)
pour le problème et les user stories.

## Choix techniques

| Brique | Choix | Pourquoi |
|---|---|---|
| Backend / API | Python, FastAPI | Écosystème riche pour l'agentique, typage natif, cohérent avec Pydantic pour valider le plan d'actions. |
| Modèle | Groq (Llama), API compatible OpenAI, tool use manuel | Quota gratuit suffisant pour un hackathon sans budget dédié, et inférence rapide pour une démo fluide. Notre boucle planificateur/exécuteur est un pattern maison spécifique (voir AGENTS.md) — écrire la boucle à la main donne un contrôle total, plutôt que d'adapter le design aux hypothèses d'un SDK agentique sous 3 jours. |
| Front | HTML/JS/CSS vanilla, servis en statique par FastAPI | Pas de build front à gérer, plus rapide à livrer en 3 jours ; suffisant pour une sidebar, un chat, une vue calendrier et un écran d'approbation ligne par ligne. |
| Stockage | SQLite | Un seul fichier, zéro configuration, cohérent avec les mocks calendrier/mail déjà prévus (voir SPEC.md, hors scope). |

## Quickstart

```
git clone <repo>
cd holberton-hackathonagentic
python3 -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner GROQ_API_KEY
uvicorn backend.main:app --reload --port 8000
# ouvrir http://localhost:8000
```

`GROQ_MODEL` par défaut : `openai/gpt-oss-120b` (tool calling supporté). En
cas de quota Groq gratuit épuisé, `openai/gpt-oss-20b` fonctionne aussi
(quota séparé, légèrement moins précis sur les appels d'outils).

## Architecture

Le front envoie le message du RH à `/chat`. FastAPI passe la main à la
boucle planificateur (`backend/agent.py`), qui appelle Groq avec ses outils
de lecture/proposition (`list_employees`, `get_employee_availability`,
`find_common_slot`, `propose_action` — voir DOCS/AGENTS.md) jusqu'à ce que
le plan soit complet. Chaque action à effet de bord proposée est écrite en
SQLite à l'état `PROPOSEE`, jamais exécutée par le modèle lui-même.

Le plan s'affiche ligne par ligne dans le chat ; le RH approuve ou refuse
chaque action. `backend/executor.py` exécute alors réellement l'action
(écriture en base, fichier dans `outbox/`), de façon idempotente, et une
confirmation s'affiche. Un refus bloque en cascade toute action qui en
dépendait. Historique complet consultable dans l'onglet "Historique"
(`GET /actions`).

Chaque outil de lecture, plus `send_email`, peut être désactivé à la volée
depuis le volet "Outils de l'agent" de la sidebar (`GET/POST /tools`) — pour
la démo, sans toucher au code ni redémarrer le serveur : l'agent explique
l'échec au lieu de planter ou d'inventer un résultat.

Schéma détaillé en annexe : [DOCS/architecture.md](DOCS/architecture.md).

## Limites connues

- Heures de travail codées en dur (9h-18h, jours ouvrés) dans
  `get_employee_availability` — pas de mock ni d'API externe pour ça.
- `get_employee_availability`/`find_common_slot` refusent une `date_range`
  de plus de 31 jours (erreur explicite plutôt qu'un pavé de créneaux).
- Pas de fichier `.ics` généré pour les événements de calendrier (optionnel
  dans AGENTS.md, non fait).
- Le coût affiché par requête (`usage.total_cost_usd`) n'est calculé que
  pour `openai/gpt-oss-120b` (tarif connu) ; `null` pour les autres modèles
  plutôt que d'inventer un prix.
- Calendrier et mail mockés localement, assumé et documenté (voir SPEC.md,
  hors scope).
