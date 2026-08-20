import json
import os
import time
from datetime import date

from dotenv import load_dotenv
from groq import Groq

from backend.db import get_connection
from backend.tools import (
    find_common_slot,
    get_employee_availability,
    list_calendar_events,
    list_employees,
    propose_action,
)

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_TURNS = 10  # le plan complet "arrivée" (2 résolutions de nom + 1 créneau + 4 propose_action) en prend déjà 7
MAX_ACTIONS_PER_PLAN = 8

# Outils qu'on peut "débrancher" en direct (démo / checkpoint palier 3),
# sans toucher au code ni redémarrer le serveur. État en mémoire (process
# unique) : suffisant pour une démo, pas conçu pour tenir plusieurs workers.
TOGGLEABLE_TOOLS = [
    "list_employees",
    "get_employee_availability",
    "find_common_slot",
    "list_calendar_events",
    "send_email",
]
DISABLED_TOOLS: set[str] = set()

# Tarifs Groq, USD / 1M tokens (console.groq.com/docs/model, relevé le 2026-08-19).
# Absent du dict => cout non calcule (affiche a None cote front) plutot que d'inventer un prix.
PRICING_PER_MILLION_TOKENS = {
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
}

_WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

SYSTEM_PROMPT = (
    "Tu es l'agent RH de l'entreprise. Ton but est de faire gagner du temps "
    "au RH : agis de façon autonome et pose le MOINS de questions possible. "
    "Ne redemande jamais une information que tu peux retrouver toi-même "
    "avec tes outils.\n\n"
    "RÉSOUDRE LES PERSONNES — n'utilise jamais un nom cité par l'utilisateur "
    "sans le vérifier. Appelle d'abord list_employees(name_contains=...) : "
    "- trouvé => utilise directement son employee_id, ne redemande jamais "
    "son email ou un identifiant à l'utilisateur, tu l'as déjà.\n"
    "- introuvable => c'est un nouvel arrivant, pas encore dans le système. "
    "Commence par proposer register_employee (via propose_action). "
    "N'invente jamais l'email, le rôle, le service ou le manager d'un "
    "nouvel arrivant : si l'utilisateur ne les a pas donnés, demande "
    "uniquement les champs manquants réellement nécessaires à "
    "register_employee, en une seule question groupée — jamais une par "
    "une, et jamais de concept qui n'existe pas dans le système (il n'y a "
    "pas de 'calendrier de service', juste un agenda par employé).\n\n"
    "PLANIFIER — une fois les identifiants résolus, utilise toi-même "
    "get_employee_availability et find_common_slot pour trouver un "
    "créneau. Ne demande jamais à l'utilisateur de choisir parmi des "
    "contraintes abstraites : propose UN créneau concret et précis "
    "('le 24/08 à 9h'), puis demande une confirmation simple avant "
    "d'appeler propose_action.\n\n"
    "ARRIVÉE D'UN NOUVEL EMPLOYÉ — le plan complet comprend à terme 4 "
    "actions : (1) register_employee, (2) une réunion d'intégration avec "
    "son manager (trouve un créneau via find_common_slot), (3) un email de "
    "bienvenue au nouvel arrivant (send_email), (4) une annonce de son "
    "arrivée à toute l'équipe (send_email, avec depends_on pointant vers "
    "l'action_id du mail de bienvenue). Mais l'employee_id d'un nouvel "
    "arrivant n'existe qu'une fois register_employee EXÉCUTÉ (après "
    "validation humaine) — avant ça, get_employee_availability, "
    "find_common_slot et send_email le rejetteraient comme inconnu. Donc "
    "en deux temps, jamais en un seul tour : "
    "1) si la personne n'existe pas encore (list_employees ne la trouve "
    "pas), propose UNIQUEMENT register_employee, puis explique clairement "
    "au RH que le reste (réunion, mails) suivra une fois cette action "
    "approuvée — ne les invente pas avant. "
    "2) si le RH répond ensuite (ex. 'continue', 'et la suite ?'), "
    "N'APPELLE JAMAIS register_employee une seconde fois pour la même "
    "personne sans vérifier d'abord : rappelle SYSTÉMATIQUEMENT "
    "list_employees(name_contains=...) en tout premier — si elle apparaît "
    "maintenant, utilise son employee_id réel pour enchaîner avec les "
    "actions (2), (3) et (4) ; si elle n'apparaît toujours pas, l'action "
    "register_employee précédente n'a pas encore été approuvée, dis-le au "
    "RH au lieu d'en reproposer une autre.\n\n"
    "EFFETS DE BORD — tu ne peux ni écrire d'événement, ni envoyer "
    "d'email, ni enregistrer ou supprimer un employé, ni supprimer un "
    "événement toi-même : ces fonctions ne te sont pas données. Pour "
    "qu'une de ces actions ait lieu, appelle propose_action avec le nom "
    "de l'outil visé, ses arguments et la raison. Un humain valide "
    "ensuite chaque action avant exécution. Le champ 'args' doit "
    "respecter EXACTEMENT ce schéma selon l'outil visé, sans inventer "
    "d'autres noms de clés :\n"
    "- create_calendar_event: {employee_ids: [id, ...], start: "
    "'AAAA-MM-JJTHH:MM:SS', end: 'AAAA-MM-JJTHH:MM:SS', title, "
    "description (optionnel)}\n"
    "- send_email: {employee_ids: [id, ...], subject, body}\n"
    "- register_employee: {name, email, role, department, manager_id "
    "(ou null), start_date: 'AAAA-MM-JJ'}\n"
    "- delete_employee: {employee_id}\n"
    "- delete_calendar_event: {event_id}\n\n"
    "SUPPRESSIONS — irréversibles une fois approuvées, donc jamais "
    "d'employee_id ou d'event_id inventé. Avant de proposer "
    "delete_calendar_event, appelle list_calendar_events (filtre par "
    "employee_id et/ou title_contains) pour retrouver le bon event_id — "
    "ne devine jamais un identifiant. Si plusieurs événements "
    "correspondent, décris-les au RH et demande lequel avant de "
    "proposer la suppression.\n\n"
    "ERREURS — si un outil renvoie une erreur (champ 'error'), ne l'ignore "
    "pas et n'invente jamais de résultat à sa place : explique au RH ce "
    "qui a échoué et pourquoi, en termes clairs."
)


def _system_prompt() -> str:
    today = date.today()
    date_context = (
        f"Nous sommes le {today.isoformat()} ({_WEEKDAYS_FR[today.weekday()]}). "
        "Si le RH donne une date sans préciser l'année (ex: '20 septembre', "
        "'lundi prochain'), résous-la toi-même par rapport à aujourd'hui : "
        "choisis la prochaine occurrence à venir — cette année si la date "
        "n'est pas encore passée, sinon l'année suivante. Ne propose jamais "
        "une date déjà passée.\n\n"
    )
    return date_context + SYSTEM_PROMPT


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_employees",
            "description": (
                "Annuaire interne de l'entreprise. À utiliser SYSTÉMATIQUEMENT avant "
                "d'agir dès qu'un nom de personne est cité, pour retrouver son "
                "employee_id sans avoir à le demander à l'utilisateur. Si name_contains "
                "ne renvoie aucun résultat, la personne n'est pas encore dans le "
                "système : c'est un nouvel arrivant (utiliser register_employee, pas "
                "les outils de calendrier)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name_contains": {
                        "type": "string",
                        "description": "Filtre partiel sur le nom (insensible à la casse). Omettre pour lister tout le monde.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_availability",
            "description": (
                "Renvoie les créneaux libres d'une liste d'employés sur une plage de dates. "
                "date_range ne peut pas dépasser 31 jours (l'outil renvoie une erreur sinon) : "
                "pour une recherche plus large, préfère find_common_slot qui élargit lui-même "
                "sa recherche par petites tranches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_ids": {"type": "array", "items": {"type": "string"}},
                    "date_range": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "[date_debut, date_fin] au format AAAA-MM-JJ",
                    },
                    "duration_minutes": {"type": "integer", "default": 15},
                },
                "required": ["employee_ids", "date_range"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_common_slot",
            "description": (
                "Renvoie jusqu'à max_candidates créneaux communs entre plusieurs employés. "
                "Élargit automatiquement la recherche si rien n'est trouvé."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_ids": {"type": "array", "items": {"type": "string"}},
                    "date_range": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "[date_debut, date_fin] au format AAAA-MM-JJ",
                    },
                    "duration_minutes": {"type": "integer", "default": 30},
                    "max_candidates": {"type": "integer", "default": 3},
                },
                "required": ["employee_ids", "date_range"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": (
                "Liste les événements de calendrier existants (id, employé, titre, horaires). "
                "À utiliser pour retrouver l'event_id exact d'un événement avant de proposer "
                "delete_calendar_event — ne jamais deviner un event_id. Toujours plafonné à "
                "20 résultats : filtrer par employee_id et/ou title_contains si besoin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Ne renvoyer que les événements de cet employé."},
                    "title_contains": {
                        "type": "string",
                        "description": "Filtre partiel sur le titre (insensible à la casse).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_action",
            "description": (
                "Ajoute une action à effet de bord au plan, à l'état PROPOSEE. "
                "N'exécute rien : un humain doit approuver avant toute exécution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": [
                            "create_calendar_event",
                            "send_email",
                            "register_employee",
                            "delete_employee",
                            "delete_calendar_event",
                        ],
                    },
                    "args": {"type": "object", "description": "Arguments à passer à l'outil visé"},
                    "reason": {"type": "string"},
                    "depends_on": {
                        "type": ["integer", "null"],
                        "description": "action_id d'une action du même plan devant être exécutée avant",
                    },
                },
                "required": ["tool", "args", "reason"],
            },
        },
    },
]


MAX_HISTORY_MESSAGES = 12  # ~6 tours user/assistant, pour borner le cout des tours suivants


def run_planner(message: str, history: list[dict] | None = None) -> dict:
    messages = [
        {"role": "system", "content": _system_prompt()},
        *(history or [])[-MAX_HISTORY_MESSAGES:],
        {"role": "user", "content": message},
    ]
    proposed_ids: list[int] = []
    trace: list[dict] = []
    llm_calls: list[dict] = []

    for _ in range(MAX_TURNS):
        llm_started = time.perf_counter()
        response = _client.chat.completions.create(
            model=_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            # 4096 : assez pour laisser un modèle "reasoning" (gpt-oss) finir
            # son raisonnement interne sans se faire couper avant de produire
            # un appel d'outil (2048 par défaut ne suffisait pas), mais assez
            # bas pour rester sous la limite de débit de openai/gpt-oss-120b
            # sur ce compte (8000 tokens/minute, requête + réponse confondues).
            max_tokens=4096,
        )
        llm_calls.append(_llm_call_stats(response, time.perf_counter() - llm_started))
        reply = response.choices[0].message

        if not reply.tool_calls:
            return {
                "message": reply.content,
                "action_ids": proposed_ids,
                "plan": _plan_details(proposed_ids),
                "trace": trace,
                "llm_calls": llm_calls,
                "usage": _usage_summary(llm_calls),
            }

        messages.append(
            {
                "role": "assistant",
                "content": reply.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in reply.tool_calls
                ],
            }
        )

        for tool_call in reply.tool_calls:
            started = time.perf_counter()
            args = None
            try:
                args = json.loads(tool_call.function.arguments)
                result = _dispatch(tool_call.function.name, args)
                tool_content = _serialize(result)
                trace.append(
                    {
                        "tool": tool_call.function.name,
                        "args": args,
                        "ok": True,
                        "error": None,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                )
                if tool_call.function.name == "propose_action":
                    proposed_ids.append(result)
            except Exception as exc:
                tool_content = {"error": str(exc)}
                trace.append(
                    {
                        "tool": tool_call.function.name,
                        "args": args,
                        "ok": False,
                        "error": str(exc),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_content),
                }
            )
            if len(proposed_ids) >= MAX_ACTIONS_PER_PLAN:
                return {
                    "message": "Nombre maximal d'actions atteint.",
                    "action_ids": proposed_ids,
                    "plan": _plan_details(proposed_ids),
                    "trace": trace,
                    "llm_calls": llm_calls,
                    "usage": _usage_summary(llm_calls),
                }

    return {
        "message": "Nombre maximal de tours atteint.",
        "action_ids": proposed_ids,
        "plan": _plan_details(proposed_ids),
        "trace": trace,
        "llm_calls": llm_calls,
        "usage": _usage_summary(llm_calls),
    }


def _llm_call_stats(response, elapsed_seconds: float) -> dict:
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else None
    completion_tokens = usage.completion_tokens if usage else None
    total_tokens = usage.total_tokens if usage else None

    cost_usd = None
    price = PRICING_PER_MILLION_TOKENS.get(_model)
    if price and usage:
        cost_usd = round(
            (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000,
            6,
        )

    return {
        "model": _model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "duration_ms": round(elapsed_seconds * 1000, 1),
        "cost_usd": cost_usd,
    }


def _usage_summary(llm_calls: list[dict]) -> dict:
    costs = [c["cost_usd"] for c in llm_calls if c["cost_usd"] is not None]
    return {
        "total_tokens": sum(c["total_tokens"] or 0 for c in llm_calls),
        "total_duration_ms": round(sum(c["duration_ms"] for c in llm_calls), 1),
        "total_cost_usd": round(sum(costs), 6) if costs else None,
    }


def _dispatch(name: str, args: dict):
    if name in DISABLED_TOOLS:
        raise RuntimeError(f"L'outil '{name}' n'est pas disponible actuellement (désactivé).")
    if name == "list_employees":
        return list_employees(args.get("name_contains"))
    if name == "list_calendar_events":
        return list_calendar_events(args.get("employee_id"), args.get("title_contains"))
    if name == "get_employee_availability":
        start, end = args["date_range"]
        return get_employee_availability(
            args["employee_ids"],
            (date.fromisoformat(start), date.fromisoformat(end)),
            args.get("duration_minutes", 15),
        )
    if name == "find_common_slot":
        start, end = args["date_range"]
        return find_common_slot(
            args["employee_ids"],
            (date.fromisoformat(start), date.fromisoformat(end)),
            args.get("duration_minutes", 30),
            args.get("max_candidates", 3),
        )
    if name == "propose_action":
        return propose_action(args["tool"], args["args"], args["reason"], args.get("depends_on"))
    raise ValueError(f"outil inconnu : {name}")


def _serialize(value):
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _plan_details(action_ids: list[int]) -> list[dict]:
    if not action_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" * len(action_ids))
    rows = conn.execute(
        f"SELECT id, tool, args, reason, depends_on, status FROM actions WHERE id IN ({placeholders})",
        action_ids,
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "tool": row["tool"],
            "args": json.loads(row["args"]),
            "reason": row["reason"],
            "depends_on": row["depends_on"],
            "status": row["status"],
        }
        for row in rows
    ]
