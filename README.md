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
| Front | HTML/JS simple, templates Jinja2 servis par FastAPI | Pas de build front à gérer, suffisant pour un écran de plan à base de listes/cases à cocher, plus rapide à livrer en 3 jours. |
| Stockage | SQLite | Un seul fichier, zéro configuration, cohérent avec les mocks calendrier/mail déjà prévus (voir SPEC.md, hors scope). |

## Quickstart

```
git clone <repo>
cd holberton-hackathonagentic
python3 -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner GROQ_API_KEY
uvicorn backend.main:app --reload
# ouvrir http://localhost:8000
```

## Architecture

Le front (Jinja2) envoie le message du RH à `/chat`. FastAPI passe la main à
la boucle planificateur (`backend/agent.py`), qui appelle Groq avec les 3
outils de lecture/proposition (voir DOCS/AGENTS.md) jusqu'à ce que le plan
soit complet. Chaque action à effet de bord proposée est écrite dans SQLite
à l'état `PROPOSEE`, jamais exécutée par le modèle lui-même. Schéma détaillé
en annexe : [DOCS/architecture.md](DOCS/architecture.md).

## Limites connues

- Heures de travail codées en dur (9h-18h, jours ouvrés) dans
  `get_employee_availability` — pas de mock ni d'API externe pour ça.
- Pas encore d'écran d'approbation : le plan proposé s'affiche en JSON brut,
  pas de validation ligne par ligne pour l'instant (prévu au palier 4).
- Pas de fichier `.ics` généré pour les événements de calendrier (optionnel
  dans AGENTS.md, non fait).
- Calendrier et mail mockés localement, assumé et documenté (voir SPEC.md,
  hors scope).
