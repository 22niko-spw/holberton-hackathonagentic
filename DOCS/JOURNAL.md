# JOURNAL.md

Historique de travail, session par session — pour retrouver le fil si l'IDE
redémarre ou si on reprend après une pause. Écrit avec Claude Code.

## 2026-08-19 — session complète (front, palier 3, palier 4)

### Front — création et mise en forme

- Création de `frontend/` (HTML/CSS/JS vanilla, pas de build) branché sur
  FastAPI à la place des templates Jinja2 d'origine.
- Logo de l'équipe intégré (header + favicon), redimensionné (1.6 Mo →
  ~100 Ko).
- Design épuré façon claude.ai : sidebar, cartes de validation lisibles
  (`describeAction()` traduit les args techniques en résumé humain au lieu
  de JSON brut — appliqué au chat **et** à l'onglet Historique).

### Palier 3 — le premier outil

- Trace d'exécution ajoutée (`agent.py`) : chaque appel d'outil est dans un
  `try/except`, alimente une liste `trace` au lieu de laisser planter la
  requête. Panneau "Trace d'exécution" côté front (masqué par défaut,
  activable dans Réglages).
- Garde-fou anti-JSON-géant : `MAX_RANGE_DAYS = 31` sur
  `get_employee_availability`/`find_common_slot`.
- `openai/gpt-oss-120b` choisi comme modèle par défaut (`llama-3.3-70b-versatile`
  a été retiré du catalogue Groq) ; repli sur `openai/gpt-oss-20b` en cas de
  quota gratuit épuisé (quota séparé, un peu moins précis sur les appels
  d'outils).

### Bug de date corrigé

Le prompt système ne disait jamais au modèle quelle était la date du jour :
une date donnée sans année (ex. "20 septembre") pouvait être résolue en
2024 au lieu de 2026, avec de vrais événements créés dans le passé. Fix :
`_system_prompt()` injecte la date courante à chaque requête, avec
consigne de résoudre vers la prochaine occurrence à venir.

### Nouveaux outils : suppression

- `list_calendar_events` (lecture, plafonnée à 20 résultats) : pour que le
  modèle retrouve un `event_id` sans jamais le deviner.
- `delete_employee` (cascade sur les événements de l'employé, sinon la
  contrainte de clé étrangère bloque) et `delete_calendar_event` — même
  gouvernance que le reste (`propose_action` → validation humaine →
  exécuteur), jamais appelés directement par le modèle.
- `send_email` rendu "débranchable" en direct (comme les outils de
  lecture) : `executor.py` vérifie `DISABLED_TOOLS` avant d'exécuter.

### Palier 4 — la boucle fermée (MVP)

Audit initial : l'itération multi-outils et le garde-fou (`MAX_TURNS`)
étaient déjà bons. Trou trouvé : un rechargement de page en plein milieu
d'un plan en attente le rendait invisible et impossible à approuver
(l'onglet Historique est en lecture seule).

- **Fix priorité 1** : les plans en attente survivent au F5.
- **Persistance complète (option B, choisie après discussion)** : la
  conversation elle-même est maintenant stockée en SQLite, pas seulement
  les actions.
  - Nouvelles tables `conversations` / `messages` (`backend/db.py`).
  - Nouveau module `backend/conversations.py` (créer/lire une conversation,
    charger l'historique pour l'agent).
  - `/chat` prend et renvoie `conversation_id` (au lieu du `history` envoyé
    par le client) ; nouvelle route `GET /conversations/{id}`.
  - Front : `conversationId` remplace l'ancien tableau `history` en
    mémoire ; le navigateur ne garde qu'un **pointeur** vers la conversation
    active (`localStorage`, pas le contenu).
  - Bug trouvé et corrigé en cours de route : "Nouvelle conversation" +
    F5 rouvrait l'ancienne conversation (le serveur n'avait rien de plus
    récent à proposer). Fix : le pointeur localStorage est effacé au clic
    sur "Nouvelle conversation", donc plus de retour arrière fantôme.

### Redesign UI (visuel + comportement)

- Sidebar transformée en tiroir escamotable, **fermé par défaut** sur
  toutes les tailles d'écran (avant : uniquement en mobile) — bouton
  hamburger toujours visible, repositionné en haut-gauche (fermé) / en
  haut-droite de la sidebar (ouverte).
- Icône engrenage (mauvaise icône corrigée en cours de route) : ouvre un
  popover regroupant "Outils de l'agent" + "Réglages" — corrigé un
  débordement du popover dans la zone de chat (mauvais ancrage/largeur).
- Bouton clair/sombre (soleil ↔ lune selon le thème actif, bug de
  l'attribut `hidden` sur `<svg>` contourné avec `style.display`).
- Composeur centré au milieu de l'écran tant qu'aucun message n'a été
  envoyé (façon ChatGPT), redescend en bas pleine largeur dès le premier
  message.
- Header : sous-titre à droite supprimé, onglets Chat/Calendrier/Historique
  vraiment centrés (ancrage indépendant du bouton hamburger).
- Écran d'accueil : texte remplacé par "Bienvenue" (gros, gras), espacement
  avec le composeur corrigé.

### État du dépôt à la fin de cette session

Branche `niko`. Dernier commit réel : `3a2179c` (README). **Tout ce qui
est listé ci-dessus depuis la suppression d'employé/événement est
encore non commité** au moment d'écrire ce journal — `git status` avant
de pousser quoi que ce soit.

### Pour la suite

- Badge "irréversible" + affichage explicite de `depends_on` sur les
  cartes (mentionné au palier 4, pas fait).
- Bonus streaming (+5, palier 4) — pas fait, gros morceau.
- `DOCS/AGENTS.md` documente encore l'ancienne liste d'outils (pas
  `list_employees`, `list_calendar_events`, ni les suppressions).
- `backend/groq_client.py` toujours mort (non importé nulle part).
