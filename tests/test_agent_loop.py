"""Un outil qui échoue ne doit jamais faire planter run_planner, ni être
caché du modèle en inventant un résultat à la place — c'est le piège
explicite du palier 5 ("le try/except qui avale tout en silence"). Ce test
vérifie le comportement réel de la boucle agent sur ce point précis, sans
appeler de vraie API LLM (le client est simulé)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from backend import agent


def _usage():
    return SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=_usage())


def test_tool_error_surfaces_without_crashing_or_faking_success():
    failing_call = _tool_call(
        "call_1",
        "get_employee_availability",
        {
            "employee_ids": ["ne-existe-pas"],
            "date_range": ["2026-09-01", "2026-09-02"],
        },
    )
    responses = [
        _response(tool_calls=[failing_call]),
        _response(content="Cette personne n'existe pas dans le système."),
    ]

    with patch.object(agent._client.chat.completions, "create", side_effect=responses):
        result = agent.run_planner("dispo de quelqu'un qui n'existe pas ?", [])

    # L'erreur d'outil doit apparaître dans la trace, pas disparaître.
    assert len(result["trace"]) == 1
    call = result["trace"][0]
    assert call["tool"] == "get_employee_availability"
    assert call["ok"] is False
    assert "inconnu" in call["error"]

    # Aucune action n'a dû être proposée à partir d'un résultat en échec.
    assert result["action_ids"] == []

    # Le message final vient bien du modèle (2e réponse simulée), pas d'un
    # résultat fabriqué à partir de l'erreur.
    assert result["message"] == "Cette personne n'existe pas dans le système."


def test_disabled_tool_is_rejected_before_running():
    call = _tool_call("call_1", "find_common_slot", {
        "employee_ids": ["adam", "david"],
        "date_range": ["2026-09-01", "2026-09-02"],
    })
    responses = [
        _response(tool_calls=[call]),
        _response(content="Cet outil est désactivé pour le moment."),
    ]

    agent.DISABLED_TOOLS.add("find_common_slot")
    try:
        with patch.object(agent._client.chat.completions, "create", side_effect=responses):
            result = agent.run_planner("trouve un créneau", [])
    finally:
        agent.DISABLED_TOOLS.discard("find_common_slot")

    assert result["trace"][0]["ok"] is False
    assert "désactivé" in result["trace"][0]["error"]
