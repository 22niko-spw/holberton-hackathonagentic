import json
import os
import time
from datetime import date

from dotenv import load_dotenv
from groq import Groq

from backend.db import get_connection
from backend.tools import find_common_slot, get_employee_availability, propose_action

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_TURNS = 6
MAX_ACTIONS_PER_PLAN = 8

# Tarifs Groq, USD / 1M tokens (console.groq.com/docs/model, relevé le 2026-08-19).
# Absent du dict => cout non calcule (affiche a None cote front) plutot que d'inventer un prix.
PRICING_PER_MILLION_TOKENS = {
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
}

SYSTEM_PROMPT = (
    "Tu es l'agent RH de l'entreprise. Tu ne peux ni écrire d'événement, ni "
    "envoyer d'email, ni enregistrer d'employé toi-même : ces fonctions ne "
    "te sont pas données. Pour qu'une de ces actions ait lieu, tu dois "
    "appeler propose_action avec le nom de l'outil visé, ses arguments et "
    "la raison. Un humain valide ensuite chaque action avant exécution. "
    "Utilise get_employee_availability et find_common_slot pour vérifier "
    "les disponibilités avant de proposer une réunion. Si un outil renvoie "
    "une erreur (champ 'error'), ne l'ignore pas et n'invente jamais de "
    "résultat à sa place : explique au RH ce qui a échoué et pourquoi, en "
    "des termes clairs."
)

TOOLS = [
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
                        "enum": ["create_calendar_event", "send_email", "register_employee"],
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


def run_planner(message: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
