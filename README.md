# holberton-hackathonagentic

Agent RH avec effets de bord réels (calendrier, mail, base employés), plan
d'actions soumis à validation humaine avant toute exécution. Voir
[SPEC.md](SPEC.md) pour le problème et les user stories.

## Choix techniques

| Brique | Choix | Pourquoi |
|---|---|---|
| Backend / API | Python, FastAPI | Écosystème riche pour l'agentique, typage natif, cohérent avec Pydantic pour valider le plan d'actions. |
| Modèle | Anthropic, Messages API directe (tool use manuel) | Notre boucle planificateur/exécuteur est un pattern maison spécifique (voir AGENTS.md) — écrire la boucle à la main donne un contrôle total, plutôt que d'adapter le design aux hypothèses d'un SDK agentique sous 3 jours. |
| Front | HTML/JS simple, templates Jinja2 servis par FastAPI | Pas de build front à gérer, suffisant pour un écran de plan à base de listes/cases à cocher, plus rapide à livrer en 3 jours. |
| Stockage | SQLite | Un seul fichier, zéro configuration, cohérent avec les mocks calendrier/mail déjà prévus (voir SPEC.md, hors scope). |

## Quickstart

TODO — une fois le projet lancé (palier 2).

## Architecture

TODO — schéma détaillé en annexe, résumé ici (palier 1).

## Limites connues

TODO — au fil des paliers, voir aussi SPEC.md (hors scope).
